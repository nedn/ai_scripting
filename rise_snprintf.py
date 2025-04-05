# This file demonstrates a simple scripting that use ai_scripting.search_utils and ai_scripting.ai_edit
# to refactor the RISE snprintf code
# To reproduce this example, run the following command:
# git clone https://github.com/aravindkrishnaswamy/RISE
# cd RISE
# git checkout 297d0339a7f7acd1418e322a30a21f44c7dbbb1d
# python3 ai_scripting/rise_snprintf.py

import os   

import ai_scripting.search_utils as search_utils
import ai_scripting.ai_edit as ai_edit
import ai_scripting.llm_utils as llm_utils

def main():
    # TODO: demonstrate a simple scripting that use ai_scripting.search_utils and ai_scripting.ai_edit
    # to refactor the RISE snprintf code

    # 1. search for all the snprintf calls from the root of the RISE repo
    # Change this to the path of the RISE repo depending on where you cloned it
    RISE_ROOT = os.path.abspath(os.path.join("..", "RISE")) 
    search_results = search_utils.search(
        search_regex="snprintf", directory=RISE_ROOT, 
        file_types=[search_utils.FileTypes.C, search_utils.FileTypes.CPP, search_utils.FileTypes.H],
        context_lines=5 # Add 5 lines of context before and after each match line
    )
    search_results.print_results()

    # 2. edit the snprintf calls to use the ai_scripting.ai_edit.edit_code_blocks function
    files_to_edit = search_results.matched_files
    edit_plan = ai_edit.edit_files(files_to_edit, prompt="Replace sprintf with snprintf",
                                   examples=ai_edit.load_example_file("snprintf_examples.txt"), 
                                   model=llm_utils.GEMINI_2_5_PRO, 
                                   edit_strategy=ai_edit.EditStrategy.REPLACE_MATCHED_BLOCKS)
    # 3 print the edit plan
    edit_plan.print_plan()

    # 4. write the edited code to the original files
    edit_plan.apply_edits()


if __name__ == "__main__":
    main()