#! /usr/bin/env python3
import argparse
import subprocess
import os
import shlex
import sys
import re
from pathlib import Path
from code_block import CodeBlock, Line, CodeMatchedResult, edit_file_with_edited_blocks
from typing import Dict
from search_utils import gather_search_results, generate_rg_command
from llm_utils import GeminiModel
from ai_edit import edit_code_blocks

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

# Rich console for better output
console = Console()

# (generate_replacement_prompt needs changes later to accept a CodeMatch object)
# def generate_replacement_prompt(user_prompt: str, filename: str, matched_lines: List[Tuple[int, str]]) -> str:
def generate_replacement_prompt(user_prompt: str, code_match: CodeBlock) -> str:
    """Creates the prompt for the LLM to generate replacement code for a CodeMatch block."""
    # Format the input block for the LLM, indicating matched lines clearly
    lines_str_parts = []
    for line in code_match.lines:
        prefix = f"{line.line_number}:" # Standard prefix
        # Optional: Add a marker for lines that originally matched the rg pattern
        # marker = "*" if line.is_match else " "
        # lines_str_parts.append(f"{prefix}{marker} {line.content}")
        lines_str_parts.append(f"{prefix}{line.content}") # Keep it simple for now

    lines_str = "\n".join(lines_str_parts)

    prompt = f"""
You are an expert programmer helping with code refactoring.
The user's overall goal is: "{user_prompt}"

You need to refactor a specific block of code from the file '{code_match.filepath}'.
The block contains lines that matched a search pattern related to the user's goal, plus some surrounding context lines.
Focus *only* on modifying the lines within this block according to the overall goal. Preserve indentation.

Code block to refactor (format: <line_number>:<original_content>):
```
{lines_str}
```

Your task:
1. Analyze the entire code block provided above.
2. Apply the refactoring logic described in the user's goal ("{user_prompt}") to the relevant lines *within this block*.
3. Output *only* the modified versions of ALL lines originally provided in the block.
4. Preserve the original line numbers. The output format must be exactly:
   <line_number>:<modified_content>
   <line_number>:<modified_content>
   ...
   (Include ALL line numbers from the input block, from {code_match.start_line} to {code_match.end_line})
5. Each line number from the input block must have a corresponding output line with the same line number and its potentially modified content.
6. If a line does not need changing based on the refactoring goal, output it exactly as it was (including its original content and indentation), prefixed by its line number.
7. Do NOT include any explanations, introductions, summaries, or markdown formatting like ```. Output only the `<line_number>:<modified_content>` lines.
8. Pay close attention to maintaining correct indentation for the modified lines, matching the original code style.

Example Input Block:
```
9: def old_function(a, b):
10:   # Some calculation
11:   result = a + b
12:   return result
13:
14: # Call the function
15: x = old_function(1, 2)
```
Example User Goal: "Rename old_function to new_function and change the calculation to multiplication"
Example Output:
```
9: def new_function(a, b):
10:   # Some calculation
11:   result = a * b
12:   return result
13:
14: # Call the function
15: x = new_function(1, 2)
```

Now, refactor the code block provided above based on the user's goal. Output all lines from {code_match.start_line} to {code_match.end_line}.
"""
    return prompt


def parse_llm_replacement_output(llm_output: str, original_block_lines: Dict[int, Line]) -> Dict[int, str]:
    """
    Parses the LLM's replacement output for a block (line_number:new_content).

    Args:
        llm_output: The raw string output from the LLM.
        original_block_lines: A dictionary mapping line number to the original Line object
                                for the block that was sent to the LLM.

    Returns:
        A dictionary mapping line number to its new content string. Includes unchanged lines.
    """
    replacements = {}
    llm_lines_raw = llm_output.strip().split('\n')
    parsed_line_numbers = set()
    original_line_numbers = set(original_block_lines.keys())

    for line in llm_lines_raw:
        if not line.strip(): # Skip empty lines from LLM output
            continue
        parts = line.split(':', 1)
        if len(parts) == 2:
            lineno_str, new_content = parts
            try:
                lineno = int(lineno_str.strip())
                if lineno in original_line_numbers:
                    # LLM provided a line that was in the original block
                    replacements[lineno] = new_content # Keep original indentation / whitespace from LLM
                    parsed_line_numbers.add(lineno)
                else:
                    # This case should be less common with the new prompt asking for all lines
                    console.print(f"[yellow]Warning: LLM returned replacement for line {lineno}, which was not in the original block sent ({min(original_line_numbers)}-{max(original_line_numbers)}). Ignoring.[/yellow]")
            except ValueError:
                console.print(f"[yellow]Warning: Could not parse line number from LLM output line: '{line}'. Ignoring.[/yellow]")
        else:
            # Handle cases where LLM might output explanations or lines without the expected format
             if len(original_line_numbers) > 0 and \
                line.strip().startswith(str(min(original_line_numbers))) and \
                line.strip().endswith(str(max(original_line_numbers))):
                 # Heuristic: ignore summary lines like "Processing lines 10-20"
                 pass
             else:
                 console.print(f"[yellow]Warning: Could not parse LLM output line format (expected 'number:content'): '{line}'. Ignoring.[/yellow]")

    # Check if LLM missed any lines it was supposed to process
    missing_lines = original_line_numbers - parsed_line_numbers
    if missing_lines:
        console.print(f"[yellow]Warning: LLM did not provide output for original lines: {sorted(list(missing_lines))}. These lines will remain unchanged.[/yellow]")
        # Add them back as unchanged using the original content
        for lineno in missing_lines:
            replacements[lineno] = original_block_lines[lineno].content

    # Ensure the dictionary covers all lines from the original block
    final_replacements = {}
    for lineno in sorted(original_line_numbers):
        if lineno in replacements:
             final_replacements[lineno] = replacements[lineno]
        else:
             # This shouldn't happen based on the missing_lines check above, but as a safeguard
             console.print(f"[red]Error: Line {lineno} was missing from LLM output and fallback logic. Keeping original.[/red]")
             final_replacements[lineno] = original_block_lines[lineno].content


    return final_replacements


def apply_changes(filepath: str, replacements: Dict[int, str]) -> bool:
    """Reads a file, applies replacements line by line, and writes back."""
    try:
        path = Path(filepath)
        # Read lines carefully, preserving original line endings if possible
        content = path.read_text(encoding='utf-8')
        lines = content.splitlines() # Keeps line content without endings
        # Detect line ending (simple check for first occurrence)
        line_ending = os.linesep # Default
        if "\r\n" in content:
             line_ending = "\r\n"
        elif "\n" in content:
             line_ending = "\n"
        elif "\r" in content:
             line_ending = "\r"


        new_lines = []
        modified = False
        for i, original_line in enumerate(lines):
            lineno = i + 1
            if lineno in replacements:
                new_line_content = replacements[lineno]
                if new_line_content != original_line:
                    modified = True
                new_lines.append(new_line_content)
            else:
                new_lines.append(original_line) # Keep lines outside the replaced blocks

        if not modified:
            console.print(f"[dim]No actual changes needed for {filepath} (LLM output matched original). Skipping write.[/dim]")
            return False # Indicate no changes were written

        # Write back using detected line endings
        # Ensure trailing newline if original file had one (splitlines() removes it)
        trailing_newline = line_ending if content.endswith(('\n', '\r')) else ""
        path.write_text(line_ending.join(new_lines) + trailing_newline, encoding='utf-8')
        console.print(f"[green]Changes applied to {filepath}[/green]")
        return True # Indicate changes were written

    except FileNotFoundError:
        console.print(f"[bold red]Error: File not found during replacement: {filepath}[/bold red]")
        return False
    except IOError as e:
        console.print(f"[bold red]Error reading/writing file {filepath}: {e}[/bold red]")
        return False
    except Exception as e:
        console.print_exception()
        console.print(f"[bold red]An unexpected error occurred while applying changes to {filepath}: {e}[/bold red]")
        return False

def process_ai_edits(search_result: CodeMatchedResult, user_prompt: str, auto_confirm: bool = False) -> bool:
    """
    Process AI edits for the search results.
    
    Args:
        search_result: The search results containing matched code blocks
        user_prompt: The user's refactoring request
        auto_confirm: Whether to automatically confirm changes
        
    Returns:
        bool: True if changes were applied successfully, False otherwise
    """
    console.print(f"\n[bold]--- Step 2: Generate Replacements (LLM) ---[/bold]")
    console.print(f"Will process [bold cyan]{len(search_result.matches)}[/bold cyan] code block(s) across [bold cyan]{search_result.total_files_matched}[/bold cyan] file(s).")

    # Use the edit_code_blocks function from ai_edit.py
    edited_blocks = edit_code_blocks(search_result.matches, user_prompt, model=GeminiModel.GEMINI_2_0_FLASH_THINKING_EXP)

    # --- Step 3: Review and Apply ---
    console.print("\n[bold]--- Step 3: Review and Apply Changes ---[/bold]")

    table = Table(title="Proposed Changes Summary (File Level)")
    table.add_column("File", style="cyan", max_width=60)
    table.add_column("Lines to Change", style="magenta")
    table.add_column("Example Change (First Affected Line)", style="green")

    # Consolidate changes per file for review
    files_to_change = set()
    for block in edited_blocks:
        if not block.lines:
            continue

        lines_to_change_nums = [line.line_number for line in block.lines]
        
        # Find the first line that is actually different
        first_changed_lineno = -1
        original_line_content = "[Original line not available for comparison]"
        new_content = "[No changes parsed?]"
        try:
            original_file_content = Path(block.filepath).read_text(encoding='utf-8').splitlines()
            found_diff = False
            for line in block.lines:
                if line.line_number > 0 and line.line_number <= len(original_file_content):
                    original_content_for_line = original_file_content[line.line_number-1]
                    if original_content_for_line != line.content:
                        first_changed_lineno = line.line_number
                        original_line_content = original_content_for_line
                        new_content = line.content
                        found_diff = True
                        break
                else:
                    console.print(f"[yellow]Warning: Line {line.line_number} for {block.filepath} is out of bounds for original file read.[/yellow]")

            if not found_diff and lines_to_change_nums:
                first_changed_lineno = lines_to_change_nums[0]
                if first_changed_lineno > 0 and first_changed_lineno <= len(original_file_content):
                    original_line_content = original_file_content[first_changed_lineno-1]
                else:
                    original_line_content = "[Line out of bounds]"
                new_content = block.lines[0].content

        except Exception as e:
            console.print(f"[yellow]Warning: Could not read original file {block.filepath} for diff: {e}[/yellow]")
            if lines_to_change_nums:
                first_changed_lineno = lines_to_change_nums[0]
                new_content = block.lines[0].content

        # Format example change
        example_change = "[No changes detected or error reading file]"
        if first_changed_lineno != -1:
            if original_line_content != new_content:
                example_change = f"[red]- {first_changed_lineno}: {original_line_content.strip()}[/red]\n[green]+ {first_changed_lineno}: {new_content.strip()}[/green]"
            else:
                example_change = f"{first_changed_lineno}: {original_line_content.strip()} [dim](No change)[/dim]"

        # Display line numbers concisely (e.g., 10-15, 25, 30-32)
        line_ranges = []
        if lines_to_change_nums:
            start_range = lines_to_change_nums[0]
            end_range = start_range
            for i in range(1, len(lines_to_change_nums)):
                if lines_to_change_nums[i] == end_range + 1:
                    end_range = lines_to_change_nums[i]
                else:
                    if start_range == end_range:
                        line_ranges.append(str(start_range))
                    else:
                        line_ranges.append(f"{start_range}-{end_range}")
                    start_range = lines_to_change_nums[i]
                    end_range = start_range
            # Add the last range
            if start_range == end_range:
                line_ranges.append(str(start_range))
            else:
                line_ranges.append(f"{start_range}-{end_range}")

        line_summary = ", ".join(line_ranges)

        table.add_row(
            block.filepath,
            line_summary,
            example_change
        )
        files_to_change.add(block.filepath)

    console.print(table)

    if auto_confirm:
        console.print("[yellow]--yes flag provided, automatically applying all changes.[/yellow]")
        confirm_apply = True
    elif files_to_change:
        confirm_apply = Confirm.ask(f"\nApply these changes to {len(files_to_change)} file(s)?", default=False)
    else:
        console.print("[yellow]No files identified with actual changes to apply.[/yellow]")
        confirm_apply = False

    if confirm_apply:
        console.print("\n[bold]Applying changes...[/bold]")
        files_successfully_changed = set()
        files_with_errors = set()
        edited_blocks_by_file = {}
        for block in edited_blocks:
            edited_blocks_by_file.setdefault(block.filepath, []).append(block)

        for filepath, blocks in edited_blocks_by_file.items():
            try:
                edit_file_with_edited_blocks(filepath, blocks)
                files_successfully_changed.add(filepath)
                console.print(f"[green]Changes applied to {filepath}[/green]")
            except Exception as e:
                console.print(f"[bold red]Error applying changes to {filepath}: {e}[/bold red]")
                files_with_errors.add(filepath)

        console.print(f"\n[bold green]Finished applying changes.[/bold green]")
        console.print(f"Successfully modified {len(files_successfully_changed)} file(s).")
        if files_with_errors:
            console.print(f"[bold yellow]Could not apply changes to {len(files_with_errors)} file(s) due to errors during write.[/bold yellow]")
        # Calculate files skipped because no effective change was made or due to errors
        skipped_no_change = len(files_to_change) - len(files_successfully_changed) - len(files_with_errors)
        if skipped_no_change > 0:
            console.print(f"[dim]{skipped_no_change} file(s) were skipped as the proposed changes matched the original content.[/dim]")
        return True
    else:
        console.print("[bold yellow]Changes discarded by user or no changes to apply.[/bold yellow]")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Agentic Edit: Interactively refactor code using rg and LLM.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "folder", help="The folder location to search and refactor code within."
    )
    parser.add_argument(
        "-p", "--prompt", required=True, help="The natural language refactoring request."
    )
    parser.add_argument(
        "--rg-args",
        default=None,
        help="Optionally skip LLM suggestion and provide initial rg arguments directly. Ensure they include context (-C N or -A N -B N), -n, --with-filename, and --stats.",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Automatically confirm all steps (Use with caution!)."
    )

    args = parser.parse_args()

    folder_path = args.folder
    user_prompt = args.prompt

    if not Path(folder_path).is_dir():
        console.print(f"[bold red]Error: Folder not found: {folder_path}[/bold red]")
        sys.exit(1)

    console.print(Panel(f"[bold]Agentic Edit Initialized[/bold]\nFolder: {folder_path}\nPrompt: {user_prompt}\nSearch args generation model: {GeminiModel.GEMINI_2_5_PRO_EXP}\nReplacement model: {GeminiModel.GEMINI_2_0_FLASH}", title="Configuration", expand=False))

    # --- Step 1: Plan & Search ---
    console.print("\n[bold]--- Step 1: Search Plan ---[/bold]")

    current_rg_args_str = args.rg_args
    if not current_rg_args_str:
        # Use the more capable model for rg command generation
        current_rg_args_str = generate_rg_command(user_prompt, folder_path)
        if not current_rg_args_str: # Handle LLM failure to suggest
             current_rg_args_str = Prompt.ask("[yellow]LLM suggestion failed. Please enter rg arguments manually (e.g., -e 'pattern' -t py -C 3 -n --with-filename --stats):[/yellow]")
             if not current_rg_args_str: # User didn't provide args either
                  console.print("[bold red]No rg arguments provided. Aborting.[/bold red]")
                  sys.exit(1)
        else:
             console.print(f"Suggested rg args: [cyan]{current_rg_args_str}[/cyan]")

    search_result: CodeMatchedResult = CodeMatchedResult() # Initialize empty result

    while True:
        console.print(Panel(f"rg {current_rg_args_str} {shlex.quote(folder_path)}", title="Current Search Command", expand=False))
        search_result = gather_search_results(current_rg_args_str, folder_path)

        if not search_result.matches:
             # No matches found, stats might still be present in search_result
             console.print("[yellow]No code blocks matched the current rg arguments.[/yellow]")
             # If stats indicate files *were* searched, it confirms no matches.
             if search_result.rg_stats_raw and " 0 files contained matches" in search_result.rg_stats_raw:
                 pass # Expected outcome
             elif not search_result.rg_stats_raw:
                 console.print("[yellow]Warning: rg did not produce statistics output.[/yellow]")

        if args.yes:
            console.print("[yellow]--yes flag provided, automatically proceeding with search results.[/yellow]")
            break

        action = Prompt.ask(
             f"\nFound {len(search_result.matches)} code blocks in {search_result.total_files_matched} files. Choose action (proceed, modify `rg` args, or abort):",
             choices=["p", "m", "a"],
             default="p",
             show_choices=True,
         ).lower()

        if action == 'p':
            if not search_result.matches:
                console.print("[yellow]Cannot proceed without any matched code blocks. Modify args or abort.[/yellow]")
                continue
            break
        elif action == 'm':
            new_args = Prompt.ask("Enter new rg arguments", default=current_rg_args_str)
            current_rg_args_str = new_args
        elif action == 'a':
            console.print("[bold yellow]Aborted by user.[/bold yellow]")
            sys.exit(0)

    if not search_result.matches:
        console.print("[bold yellow]No code blocks matched the final search criteria. Exiting.[/bold yellow]")
        sys.exit(0)

    # Process AI edits
    process_ai_edits(search_result, user_prompt, args.yes)

    console.print("\n[bold]Agentic Edit finished.[/bold]")

if __name__ == "__main__":
    main()