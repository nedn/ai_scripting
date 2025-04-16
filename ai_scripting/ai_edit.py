import enum
from typing import List, Optional, Tuple

from rich import console

from ai_scripting import code_block
from ai_scripting import llm_utils


console_instance = console.Console()

def load_example_file(example_file: str) -> Optional[str]:
    """Load an example file if it exists."""
    try:
        with open(example_file, 'r') as f:
            return f.read()
    except Exception as e:
        console_instance.print(f"[yellow]Warning: Could not load example file {example_file}: {e}[/yellow]")
        return None

_CODE_BLOCK_START = "<code_block>"
_CODE_BLOCK_END = "</code_block>"

def _get_block_prompt(block: code_block.CodeBlock) -> str:
    return f"""
{_CODE_BLOCK_START}
{block.code_block_without_line_numbers}
{_CODE_BLOCK_END}
"""

def _process_llm_output(llm_output: str, current_batch: List[tuple]) -> List[code_block.EditCodeBlock]:
    """
    Process LLM output to generate edited code blocks.

    Args:
        llm_output: The raw output from the LLM
        current_batch: List of tuples containing (original_block, block_prompt)

    Returns:
        List of edited EditCodeBlock objects
    """

    if llm_output.startswith("Error:"):
        console_instance.print(f"[bold red]Error processing batch: {llm_output}[/bold red]")
        # Keep the original blocks if there's an error
        return [code_block.EditCodeBlock(block.lines, block) for block, _ in current_batch]

    # Parse the LLM output into separate block outputs using XML tags
    block_outputs = []
    current_block = ""
    in_block = False

    for line in llm_output.strip().split('\n'):
        if _CODE_BLOCK_START in line:
            in_block = True
            current_block = line.split(_CODE_BLOCK_START)[1]
        elif _CODE_BLOCK_END in line:
            in_block = False
            current_block += line.split(_CODE_BLOCK_END)[0]
            block_outputs.append(current_block)
            current_block = ""
        elif in_block:
            current_block += line + "\n"

    # Process each block's output
    edited_blocks = []
    for (original_block, _), edit_block_str in zip(current_batch, block_outputs):
        edited_block = code_block.CreateEditCodeBlockFromCodeString(edit_block_str, original_block)
        edited_blocks.append(edited_block)

    return edited_blocks

class EditPlan:
    def __init__(self, files: List[code_block.TargetFile]):
        self._files = files

    @property
    def files(self) -> List[code_block.TargetFile]:
        return self._files

    def print_plan(self):
        console_instance.print(f"[bold green]Edit Plan:[/bold green]")
        console_instance.print(f"[bold green]Files to edit:[/bold green]")
        for file in self._files:
            console_instance.print(f"[bold green]{file.filepath}[/bold green]")

    def apply_edits(self):
        for file in self._files:
            file.apply_edits()

def edit_code_blocks(
    code_blocks: List[code_block.CodeBlock],
    edit_prompt: str,
    model: llm_utils.GeminiModel,
    example_content: Optional[str] = None,
    max_blocks_per_ai_call=20,
    token_tracker: llm_utils.TokensTracker = None
) -> List[code_block.EditCodeBlock]:
    """
    Takes a list of CodeBlocks, an edit prompt, and a model to generate edited code blocks.
    Batches multiple blocks into a single LLM call to optimize token usage.

    Args:
        code_blocks: List of CodeBlock objects to edit
        edit_prompt: The prompt describing the desired code changes
        model: The Gemini model to use for generating edits (defaults to GEMINI_2_0_FLASH_THINKING_EXP)
        example_content: Optional example content showing the desired refactoring pattern
        max_blocks_per_ai_call: The maximum number of blocks to include in a single AI call.
            Note: while the large context window of the LLM can handle a lot more, increasing this
            number will result in slower response times and lower quality edits (see
            the paper "NoLiMa: Long-Context Evaluation Beyond Literal Matching" https://arxiv.org/abs/2502.05167)
        token_tracker: A TokensTracker object to track the token usage of the LLM calls.

    Returns:
        List of edited CodeBlock objects with the same structure but potentially modified content
    """
    edited_blocks = []
    current_batch = []
    current_batch_tokens = 0

    if not example_content:
        example_content = load_example_file("snprintf-edits.example")

    # Base prompt template that will be reused for each batch
    base_prompt = f"""
You are an expert programmer helping with code refactoring.

You need to refactor multiple blocks of code according to the overall goal.
For each block, focus *only* on modifying the lines within that block. Preserve indentation.

Your task:
1. Analyze each code block provided above.
2. Apply the refactoring logic described in the user's goal ("{edit_prompt}") to the relevant lines *within each block*.
3. Output *only* the modified versions of ALL lines originally provided in each block.
4. Output each line exactly as it should appear in the code, preserving indentation and whitespace.
5. If a line does not need changing based on the refactoring goal, output it exactly as it was.
6. Do NOT include any explanations, introductions, summaries, or markdown formatting like ```.
7. Do NOT include line numbers in your output - just the code lines themselves.
8. Pay close attention to maintaining correct indentation for the modified lines, matching the original code style.
9. Enclose each block's output in XML tags: <code_block> and </code_block>

Here is an example of the desired refactoring pattern:
[Example]
{example_content}
[Example End]


The user's overall goal is: "{edit_prompt}"

[Input Code Blocks]
%%input_code_blocks%%

[Output Code Blocks]
"""

    # Calculate the size of the base prompt
    base_prompt_tokens = llm_utils.count_tokens(base_prompt)

    for i, block in enumerate(code_blocks):
        # Create the block-specific prompt part
        block_prompt = _get_block_prompt(block)

        # Calculate tokens for this block
        block_tokens = llm_utils.count_tokens(block_prompt)

        # If adding this block would exceed the model's output token limit (accounting for potential output size)
        # or if we already have blocks in the batch, process the current batch
        if len(current_batch) >= max_blocks_per_ai_call or (current_batch and (current_batch_tokens + block_tokens) * 5 > model.output_tokens):
            # Process the current batch
            batch_prompt = base_prompt + "\n".join(bp for _, bp in current_batch)
            llm_output = llm_utils.call_llm(batch_prompt, f"Generating replacements for batch of {len(current_batch)} blocks",
                                  model=model, token_tracker=token_tracker)
            edited_blocks.extend(_process_llm_output(llm_output, current_batch))

            # Reset batch
            current_batch = []
            current_batch_tokens = 0

        # Add this block to the current batch
        current_batch.append((block, block_prompt))
        current_batch_tokens += block_tokens

    # Process any remaining blocks in the final batch
    if current_batch:
        input_code_blocks = "\n".join(bp for _, bp in current_batch)
        batch_prompt = base_prompt.replace("%%input_code_blocks%%", input_code_blocks)
        llm_output = llm_utils.call_llm(batch_prompt, f"Generating replacements for final batch of {len(current_batch)} blocks",
                              model=model, token_tracker=token_tracker)
        edited_blocks.extend(_process_llm_output(llm_output, current_batch))

    return edited_blocks

class EditStrategy(enum.Enum):
    REPLACE_MATCHED_BLOCKS = "replace_matched_blocks"
    REPLACE_WHOLE_FILE = "replace_whole_file"

def create_ai_plan_for_editing_files(
    files: List[code_block.TargetFile],
    prompt: str,
    examples: Optional[str] = None,
    model: llm_utils.GeminiModel = llm_utils.GeminiModel.GEMINI_2_5_PRO,
    edit_strategy: EditStrategy = EditStrategy.REPLACE_MATCHED_BLOCKS
) -> Tuple[EditPlan, llm_utils.TokensTracker]:
    """
    Edit multiple files based on a given prompt and strategy.

    Args:
        files: List of TargetFile objects containing the files and blocks to edit
        prompt: The prompt describing the desired code changes
        examples: Optional examples showing the desired refactoring pattern
        model: The Gemini model to use for generating edits
        edit_strategy: The strategy to use for editing the files

    Returns:
        List of EditCodeBlock objects containing the proposed changes
    """
    token_tracker = llm_utils.TokensTracker()
    all_blocks_to_edit = []
    max_blocks_per_ai_call = 20

    if edit_strategy == EditStrategy.REPLACE_MATCHED_BLOCKS:
        for target_file in files:
            all_blocks_to_edit.extend(target_file.blocks_to_edit)
    elif edit_strategy == EditStrategy.REPLACE_WHOLE_FILE:
        max_blocks_per_ai_call = 1
        for target_file in files:
            all_blocks_to_edit.append(target_file.whole_file_as_edit_block)

    edited_blocks = edit_code_blocks(all_blocks_to_edit, prompt, model, examples,
                                     max_blocks_per_ai_call=max_blocks_per_ai_call,
                                     token_tracker=token_tracker)

    for target_file in files:
        for block in edited_blocks:
            if block.filepath == target_file.filepath:
                target_file.add_edited_block(block)

    plan = EditPlan(files)
    return plan, token_tracker

