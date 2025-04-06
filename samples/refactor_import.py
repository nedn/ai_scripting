"""
Refactors Python import statements in specified files to conform to the Google Python Style Guide.

This script uses ai_scripting.search_utils to find Python files containing import statements
and ai_scripting.ai_edit to apply AI-driven refactoring based on the Google Style Guide rules.
It operates by instructing the AI to rewrite the entire file content, focusing on the import section.
"""
import os
import argparse
import shlex
import sys

# --- Add ai_scripting to the Python path ---
# Assume the script is in samples/, and ai_scripting/ is one level up
SAMPLE_DIR = os.path.abspath(os.path.dirname(__file__))
AI_SCRIPTING_DIR = os.path.abspath(os.path.join(SAMPLE_DIR, ".."))
if AI_SCRIPTING_DIR not in sys.path:
    sys.path.append(AI_SCRIPTING_DIR)
# --- End ai_scripting path setup ---

try:
    import ai_scripting.search_utils as search_utils
    import ai_scripting.ai_edit as ai_edit
    import ai_scripting.llm_utils as llm_utils
except ImportError as e:
    print(f"Error importing ai_scripting modules: {e}")
    print(f"Ensure the ai_scripting directory ({AI_SCRIPTING_DIR}) is accessible and in your Python path.")
    sys.exit(1)

import rich.console as console

console = console.Console()

def main():
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(
        description='Refactor Python import statements to Google Style Guide format.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--directory', "-d", type=str, required=True,
        help='The root directory to search for Python files.'
    )
    parser.add_argument(
        '--max-files', "-m", type=int, default=5,
        help='Maximum number of files to apply AI edits to. Set to 0 to apply to all found files.'
    )
    args = parser.parse_args()

    target_directory = os.path.abspath(args.directory)
    if not os.path.isdir(target_directory):
        console.print(f"[bold red]Error: Directory not found: {target_directory}[/bold red]")
        sys.exit(1)

    # --- 1. Search for Python files containing import statements ---
    # We search for lines starting with 'import' or 'from' to identify files
    # that likely need import refactoring. We use REPLACE_WHOLE_FILE strategy later,
    # so precise line matching isn't critical here, just finding the relevant files.
    # Context lines are set to 0 as we'll process the whole file.
    search_regex = shlex.quote(r"^(?:import|from)\s+")
    console.print(f"Searching for Python files with imports in: {target_directory}")
    console.print(f"Using search regex: {search_regex}")

    try:
        search_results = search_utils.search(
            search_regex=search_regex,
            directory=target_directory,
            file_types=[search_utils.FileTypes.PYTHON],
            context_lines=0 # We will edit the whole file, context isn't needed here
        )
    except Exception as e:
        console.print(f"[bold red]Error during search:[/bold red] {e}")
        sys.exit(1)

    if not search_results.matched_files:
        console.print("[yellow]No Python files containing import statements found.[/yellow]")
        return

    search_results.print_results(print_matches=False) # Don't print matches as we edit whole file

    # --- Filter files based on --max-files-to-apply-ai-edit ---
    files_to_edit = search_results.matched_files
    if args.max_files > 0 and len(files_to_edit) > args.max_files:
        files_to_edit = files_to_edit[:args.max_files]
        console.print(
            f"[yellow]Limiting AI edits to the first {len(files_to_edit)} files. "
            f"Use --max-files 0 to apply to all ({len(search_results.matched_files)}) found files.[/yellow]"
        )
    else:
         console.print(f"Preparing to edit {len(files_to_edit)} files.")

    # --- 2. Generate an AI edit plan ---
    # We use the REPLACE_WHOLE_FILE strategy because import ordering and grouping
    # often requires looking at all imports in a file together.
    prompt = (
        "Refactor the import statements in the provided Python code to strictly follow the "
        "Google Python Style Guide. Ensure imports are grouped correctly (standard library, "
        "third-party, application-specific) with blank lines between groups, and sorted "
        "alphabetically within each group. Preserve the rest of the code exactly as it is."
    )
    example_file_path = os.path.join(SAMPLE_DIR, "google_imports.example")
    examples = ai_edit.load_example_file(example_file_path)

    if not examples:
        console.print(f"[bold red]Error: Could not load example file: {example_file_path}[/bold red]")
        console.print("[yellow]Proceeding without examples, but results may be less accurate.[/yellow]")

    console.print("Creating AI edit plan (this may take some time)...")

    try:
        edit_plan = ai_edit.create_ai_plan_for_editing_files(
            files=files_to_edit,
            prompt=prompt,
            examples=examples,
            model=llm_utils.GeminiModel.GEMINI_2_5_PRO,
            edit_strategy=ai_edit.EditStrategy.REPLACE_WHOLE_FILE # Edit whole file for imports
        )
    except Exception as e:
         console.print(f"[bold red]Error creating AI edit plan:[/bold red] {e}")
         # Potentially print more details if needed, e.g., traceback
         # import traceback
         # traceback.print_exc()
         sys.exit(1)


    # --- 3. Print the edit plan ---
    console.print("\n--- AI Edit Plan ---")
    edit_plan.print_plan() # This currently just lists files, could be enhanced to show diffs later

    # --- 4. Apply the edits ---
    confirm = input("\nApply these edits? (y/N): ")
    if confirm.lower() == 'y':
        console.print("Applying edits...")
        try:
            edit_plan.apply_edits()
            console.print("[bold green]Edits applied successfully.[/bold green]")
        except Exception as e:
            console.print(f"[bold red]Error applying edits:[/bold red] {e}")
            # Potentially print traceback
            sys.exit(1)
    else:
        console.print("Edits were not applied.")


if __name__ == "__main__":
    main()