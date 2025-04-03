from typing import List
from code_block import CodeBlock, EditCodeBlock
from llm_utils import call_llm, GeminiModel, count_tokens
from rich.console import Console

console = Console()

def get_block_prompt(block: CodeBlock) -> str:
    return f"""
<code_block>
{block.code_block_without_line_numbers}
</code_block>
"""

def process_llm_output(llm_output: str, current_batch: List[tuple]) -> List[EditCodeBlock]:
    """
    Process LLM output to generate edited code blocks.
    
    Args:
        llm_output: The raw output from the LLM
        current_batch: List of tuples containing (original_block, block_prompt)
        
    Returns:
        List of edited EditCodeBlock objects
    """

    if llm_output.startswith("Error:"):
        console.print(f"[bold red]Error processing batch: {llm_output}[/bold red]")
        # Keep the original blocks if there's an error
        return [block for block, _ in current_batch]
    
    # Parse the LLM output into separate block outputs using XML tags
    block_outputs = []
    current_block = ""
    in_block = False
    
    for line in llm_output.strip().split('\n'):
        if "<code_block>" in line:
            in_block = True
            current_block = line.split("<code_block>")[1] if "<code_block>" in line else ""
        elif "</code_block>" in line:
            in_block = False
            current_block += line.split("</code_block>")[0] if "</code_block>" in line else ""
            block_outputs.append(current_block.strip())
            current_block = ""
        elif in_block:
            current_block += line + "\n"
    
    # Process each block's output
    edited_blocks = []
    for (original_block, _), block_output in zip(current_batch, block_outputs):
        edited_lines_content = [line for line in block_output.split('\n') if line.strip()]
        
        # Create a new CodeBlock with the edited content
        edited_lines = []
        for original_line, new_content in zip(original_block.lines, edited_lines_content):
            edited_lines.append(original_line.__class__(
                line_number=original_line.line_number,
                content=new_content,
                is_match=original_line.is_match
            ))
        
        edited_block = EditCodeBlock(
            filepath=original_block.filepath,
            start_line=original_block.start_line,
            original_end_line=original_block.end_line,
            end_line=original_block.start_line + len(edited_lines) - 1,
            lines=edited_lines
        )
        edited_blocks.append(edited_block)
    
    return edited_blocks

# Limits the number of blocks that can be processed in a single LLM call
# to avoid exceeding the model's output token limit and ensure the quality 
# of the output
MAX_BLOCKS_PER_CALL = 7

def edit_code_blocks(
    code_blocks: List[CodeBlock],
    edit_prompt: str,
    model: GeminiModel 
) -> List[CodeBlock]:
    """
    Takes a list of CodeBlocks, an edit prompt, and a model to generate edited code blocks.
    Batches multiple blocks into a single LLM call to optimize token usage.
    
    Args:
        code_blocks: List of CodeBlock objects to edit
        edit_prompt: The prompt describing the desired code changes
        model: The Gemini model to use for generating edits (defaults to GEMINI_2_0_FLASH_THINKING_EXP)
        
    Returns:
        List of edited CodeBlock objects with the same structure but potentially modified content
    """
    edited_blocks = []
    current_batch = []
    current_batch_tokens = 0
    
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

[Example]
The user's overall goal is: "Refactor the code to use snprintf instead of sprintf"

Code blocks to refactor:

<code_block>
int main() {{
    char buffer[100];
    sprintf(buffer, "Hello, world!");
    return 0;
}}
</code_block>
<code_block>
    // this is a comment
    sprintf( lightname, "light%d", i );
</code_block>

Output:
<code_block>
int main() {{
    char buffer[100];
    snprintf(buffer, sizeof(buffer), "Hello, world!");
    return 0;
}}
</code_block>
<code_block>
    // this is a comment
    snprintf( lightname, sizeof(lightname), "light%d", i );
</code_block>
[Example End]

The user's overall goal is: "{edit_prompt}"
Code blocks to refactor:
"""
    
    # Calculate the size of the base prompt
    base_prompt_tokens = count_tokens(base_prompt)
    
    for i, block in enumerate(code_blocks):
        # Create the block-specific prompt part
        block_prompt = get_block_prompt(block) 
        
        # Calculate tokens for this block
        block_tokens = count_tokens(block_prompt)
        
        # If adding this block would exceed the model's output token limit (accounting for potential output size)
        # or if we already have blocks in the batch, process the current batch
        if current_batch and (current_batch_tokens + block_tokens) * 5 > model.output_tokens or len(current_batch) >= MAX_BLOCKS_PER_CALL:
            # Process the current batch
            batch_prompt = base_prompt + "\n".join(bp for _, bp in current_batch)
            llm_output = call_llm(batch_prompt, f"Generating replacements for batch of {len(current_batch)} blocks", model=model)
            edited_blocks.extend(process_llm_output(llm_output, current_batch))
            
            # Reset batch
            current_batch = []
            current_batch_tokens = 0
        
        # Add this block to the current batch
        current_batch.append((block, block_prompt))
        current_batch_tokens += block_tokens
    
    # Process any remaining blocks in the final batch
    if current_batch:
        batch_prompt = base_prompt + "\n".join(bp for _, bp in current_batch)
        llm_output = call_llm(batch_prompt, f"Generating replacements for final batch of {len(current_batch)} blocks", model=model)
        edited_blocks.extend(process_llm_output(llm_output, current_batch))
    
    return edited_blocks