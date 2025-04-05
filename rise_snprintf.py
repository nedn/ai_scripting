# This file demonstrates a simple scripting that use ai_scripting.search_utils and ai_scripting.ai_edit
# to refactor the RISE snprintf code
# To reproduce this example, run the following command:
# git clone https://github.com/aravindkrishnaswamy/RISE
# cd RISE
# git checkout 297d0339a7f7acd1418e322a30a21f44c7dbbb1d
# python3 ../rise_snprintf.py

import ai_scripting.search_utils as search_utils
import ai_scripting.ai_edit as ai_edit

def main():
    # TODO: demonstrate a simple scripting that use ai_scripting.search_utils and ai_scripting.ai_edit
    # to refactor the RISE snprintf code

    # 1. search for all the snprintf calls from the root of the RISE repo
    RISE_ROOT = os.path.join(os.path.dirname(__file__), "RISE")
    search_results = search_utils.gather_search_results(RISE_ROOT, "snprintf")
    print(search_results)
    # 2. edit the snprintf calls to use the ai_scripting.ai_edit.edit_code_blocks function
    
    # 3. write the edited code to a new file


if __name__ == "__main__":
    main()