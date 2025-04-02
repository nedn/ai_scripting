from typing import List
from code_block import CodeBlock
from llm_utils import call_llm, GeminiModel
from rich.console import Console

console = Console()

def edit_code_blocks(
    code_blocks: List[CodeBlock],
    edit_prompt: str,
    model: GeminiModel = GeminiModel.GEMINI_2_0_FLASH
) -> List[CodeBlock]:
    """
    Takes a list of CodeBlocks, an edit prompt, and a model to generate edited code blocks.
    
    Args:
        code_blocks: List of CodeBlock objects to edit
        edit_prompt: The prompt describing the desired code changes
        model: The Gemini model to use for generating edits (defaults to GEMINI_2_0_FLASH)
        
    Returns:
        List of edited CodeBlock objects with the same structure but potentially modified content
    """
    edited_blocks = []
    
    for i, block in enumerate(code_blocks):
        # Create a prompt that includes the block's context and the edit request
        block_prompt = f"""
You are an expert programmer helping with code refactoring.
The user's overall goal is: "{edit_prompt}"

You need to refactor a specific block of code from the file '{block.filepath}'.
The block contains lines plus some surrounding context lines.
Focus *only* on modifying the lines within this block according to the overall goal. Preserve indentation.

Code block to refactor:
```
{block.code_block_without_line_numbers}
```

Your task:
1. Analyze the entire code block provided above.
2. Apply the refactoring logic described in the user's goal ("{edit_prompt}") to the relevant lines *within this block*.
3. Output *only* the modified versions of ALL lines originally provided in the block.
4. Output each line exactly as it should appear in the code, preserving indentation and whitespace.
5. If a line does not need changing based on the refactoring goal, output it exactly as it was.
6. Do NOT include any explanations, introductions, summaries, or markdown formatting like ```.
7. Do NOT include line numbers in your output - just the code lines themselves.
8. Pay close attention to maintaining correct indentation for the modified lines, matching the original code style.
"""
        
        # Call the LLM to generate the edited code
        llm_output = call_llm(block_prompt, f"Generating replacement for block {i+1}", model=model)
        
        if llm_output.startswith("Error:"):
            console.print(f"[bold red]Error processing block {i+1}: {llm_output}[/bold red]")
            # Keep the original block if there's an error
            edited_blocks.append(block)
            continue
            
        # Parse the LLM output into a list of lines
        edited_lines_content = [line for line in llm_output.strip().split('\n') if line.strip()]

        # Create a new CodeBlock with the edited content, preserving line numbers and match status
        edited_lines = []
        for original_line, new_content in zip(block.lines, edited_lines_content):
            edited_lines.append(original_line.__class__(
                line_number=original_line.line_number,
                content=new_content,
                is_match=original_line.is_match
            ))
                
        edited_block = CodeBlock(
            filepath=block.filepath,
            start_line=block.start_line,
            end_line=block.end_line,
            lines=edited_lines
        )
        edited_blocks.append(edited_block)
    
    return edited_blocks


def edit_file_with_edited_block(block: CodeBlock):
    """
    Takes a CodeBlock and edits the file it represents.
    Uses line numbers to ensure the correct block is replaced even if similar code appears multiple times.
    """
    with open(block.filepath, 'r') as file:
        lines = file.readlines()
    
    # Replace the lines in the specified range with the edited block
    # Note: line numbers are 1-indexed, but list indices are 0-indexed
    start_idx = block.start_line - 1
    end_idx = block.end_line
    
    # Replace the lines in the range with the edited block
    lines[start_idx:end_idx] = [line.content + '\n' for line in block.lines]
    
    # Write the modified content back to the file
    with open(block.filepath, 'w') as file:
        file.writelines(lines)