"""
Refactors Python import statements in specified files to conform to the Google Python Style Guide.

This script uses ai_scripting.search_utils to find Python files containing import statements
and ai_scripting.ai_edit to apply AI-driven refactoring based on the Google Style Guide rules.
It operates by instructing the AI to rewrite the entire file content, focusing on the import section.
"""
import argparse
import os
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
    from ai_scripting import ai_edit
    from ai_scripting import llm_utils
    from ai_scripting import search_utils
except ImportError as e:
    print(f"Error importing ai_scripting modules: {e}")
    print(f"Ensure the ai_scripting directory ({AI_SCRIPTING_DIR}) is accessible and in your Python path.")
    sys.exit(1)

from rich import console as rich_console # Renamed to avoid conflict with the instance below

console = rich_console.Console()

# Based on https://google.github.io/styleguide/pyguide.html#22-imports
_PROMPT = """
Refactor the import statements in the provided Python code to strictly follow the
Google Python Style Guide.

2.2 Imports
Use import statements for packages and modules only, not for individual types, classes, or functions.

2.2.1 Definition
Reusability mechanism for sharing code from one module to another.

2.2.2 Pros
The namespace management convention is simple. The source of each identifier is indicated in a consistent way; x.Obj says that object Obj is defined in module x.

2.2.3 Cons
Module names can still collide. Some module names are inconveniently long.

2.2.4 Decision
Use `import x` for importing packages and modules.
Use `from x import y where x` is the package prefix and y is the module name with no prefix.
Use `from x import y as z` in any of the following circumstances:
Two modules named y are to be imported.
y conflicts with a top-level name defined in the current module.
y conflicts with a common parameter name that is part of the public API (e.g., features).
y is an inconveniently long name.
y is too generic in the context of your code (e.g., from storage.file_system import options as fs_options).
Use `import y as z` only when z is a standard abbreviation (e.g., import numpy as np).
For example the module sound.effects.echo may be imported as follows:

```python
from sound.effects import echo
...
echo.EchoFilter(input, output, delay=0.7, atten=4)
```

Do not use relative names in imports. Even if the module is in the same package, use the full package name. This helps prevent unintentionally importing a package twice.


2.2.4.1 Exemptions
Exemptions from this rule:

Symbols from the following modules are used to support static analysis and type checking:
typing module
collections.abc module
typing_extensions module
Redirects from the six.moves module.

2.3 Packages
Import each module using the full pathname location of the module.

2.3.1 Pros
Avoids conflicts in module names or incorrect imports due to the module search path not being what the author expected. Makes it easier to find modules.

2.3.2 Cons
Makes it harder to deploy code because you have to replicate the package hierarchy. Not really a problem with modern deployment mechanisms.

2.3.3 Decision
All new code should import each module by its full package name.

Imports should be as follows:

Yes:
```python
  # Reference absl.flags in code with the complete name (verbose).
  import absl.flags
  from doctor.who import jodie

  _FOO = absl.flags.DEFINE_string(...)
```

Yes:
```python
  # Reference flags in code with just the module name (common).
  from absl import flags
  from doctor.who import jodie

  _FOO = flags.DEFINE_string(...)
```
(assume this file lives in doctor/who/ where jodie.py also exists)

No:
```python
  # Unclear what module the author wanted and what will be imported.  The actual
  # import behavior depends on external factors controlling sys.path.
  # Which possible jodie module did the author intend to import?
  import jodie
```
The directory the main binary is located in should not be assumed to be in sys.path despite that happening in some environments. This being the case, code should assume that import jodie refers to a third-party or top-level package named jodie, not a local jodie.py.
"""

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
    example_file_path = os.path.join(SAMPLE_DIR, "google_imports.example")
    examples = ai_edit.load_example_file(example_file_path)

    console.print("Creating AI edit plan (this may take some time)...")

    try:
        edit_plan, token_tracker = ai_edit.create_ai_plan_for_editing_files(
            files=files_to_edit,
            prompt=_PROMPT,
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

    # --- 4. Print the token usage ---
    console.print(f"[yellow]Token usage: {token_tracker.get_usage_summary()}[/yellow]")
    console.print(f"[yellow]Estimated cost: ${token_tracker.get_approximate_cost()}[/yellow]")

    # --- 5. Apply the edits ---
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

