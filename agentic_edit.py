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

SEARCH_ARGS_MODEL = GeminiModel.GEMINI_2_5_PRO_EXP
REPLACEMENT_MODEL = GeminiModel.GEMINI_2_5_PRO_EXP

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
    edited_blocks = edit_code_blocks(search_result.matches, user_prompt, model=REPLACEMENT_MODEL)

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

    console.print(Panel(f"[bold]Agentic Edit Initialized[/bold]\nFolder: {folder_path}\nPrompt: {user_prompt}\nSearch args generation model: {SEARCH_ARGS_MODEL}\nReplacement model: {REPLACEMENT_MODEL}", title="Configuration", expand=False))

    # --- Step 1: Plan & Search ---
    console.print("\n[bold]--- Step 1: Search Plan ---[/bold]")

    current_rg_args_str = args.rg_args
    if not current_rg_args_str:
        # Use the more capable model for rg command generation
        current_rg_args_str = generate_rg_command(user_prompt, folder_path, model=SEARCH_ARGS_MODEL)
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