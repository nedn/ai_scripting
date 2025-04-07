# This file demonstrates a simple scripting that use ai_scripting.search_utils and ai_scripting.ai_edit
# to refactor the RISE snprintf code
# To reproduce this example, run the following command:
# git clone https://github.com/aravindkrishnaswamy/RISE
# cd RISE
# git checkout 297d0339a7f7acd1418e322a30a21f44c7dbbb1d
# python3 ai_scripting/rise_snprintf.py

import argparse
import os
import shlex
import sys

from rich import console

SAMPLE_DIR = os.path.abspath(os.path.dirname(__file__))
AI_SCRIPTING_DIR = os.path.abspath(os.path.join(SAMPLE_DIR, ".."))
sys.path.append(AI_SCRIPTING_DIR)

from ai_scripting import search_utils
from ai_scripting import ai_edit
from ai_scripting import llm_utils


console = console.Console()

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Refactor RISE snprintf code')
    parser.add_argument('--max-files', "-m", type=int, default=5,
                      help='Maximum number of files to apply AI edits to. Set to 0 to apply to all files.')
    args = parser.parse_args()

    # Change this to the path of the RISE repo depending on where you cloned it
    RISE_ROOT = os.path.abspath(os.path.join(AI_SCRIPTING_DIR, '..', "RISE"))


    # 1. search for all the sprintf calls from the root of the RISE repo

    # --- Search for sprintf calls ---
    # To search for sprintf calls, we use a regex that matches the word "sprintf"
    # surrounded by word boundaries, so as to avoid matching calls to sprintf
    # in comments or strings. The right most character "(" is escaped to ensure it is
    # not interpreted as a regex anchor.
    search_regex = shlex.quote(r"\bsprintf\(")

    search_results = search_utils.search(
        search_regex=search_regex, directory=RISE_ROOT,
        file_types=[search_utils.FileTypes.C, search_utils.FileTypes.CPP, search_utils.FileTypes.H],
        context_lines=5 # Add 5 lines of context before and after each match line
    )
    search_results.print_results()

    files_to_edit = search_results.matched_files
    if args.max_files > 0:
        files_to_edit = files_to_edit[:args.max_files]
        console.print(f"[yellow]Limiting AI edits to {len(files_to_edit)} files. Set --max-files to 0 to apply to all files.[/yellow]")

    # 2. Generate an edit plan for the matched files
    # In this case, since we are replacing sprintf with snprintf, we only need to edit the matched blocks
    # and not the whole file to minimize tokens used and improve the quality of the edits.
    edit_plan = ai_edit.create_ai_plan_for_editing_files(
            files_to_edit,
            prompt="Replace sprintf with snprintf",
            examples=ai_edit.load_example_file(os.path.join(SAMPLE_DIR, "snprintf-edits.example")),
            model=llm_utils.GeminiModel.GEMINI_2_5_PRO,
            edit_strategy=ai_edit.EditStrategy.REPLACE_MATCHED_BLOCKS)

    # 3. Print the edit plan
    edit_plan.print_plan()

    # 4. Apply the edits to the original files
    edit_plan.apply_edits()


if __name__ == "__main__":
    main()

