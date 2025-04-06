#! /usr/bin/env python3

import os
import argparse
import sys
from pathlib import Path

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
SAMPLE_DIR = os.path.abspath(os.path.join(ROOT_DIR, "samples"))
AI_SCRIPTING_DIR = os.path.abspath(os.path.join(ROOT_DIR, "ai_scripting"))
sys.path.append(AI_SCRIPTING_DIR)

import ai_scripting.llm_utils as llm_utils
from rich.console import Console

console = Console()

def generate_refactor_script(prompt: str, output_file: str) -> None:
    """
    Generate a refactoring script based on the user's prompt.
    
    Args:
        prompt: The user's description of the refactoring task
        output_file: The path where the generated script should be saved
    """
    # Create the prompt for the LLM
    llm_prompt = f"""Create a Python script that performs the following refactoring task:

{prompt}

The script should follow the same structure as the rise_snprintf.py example, which:
1. Uses search_utils to find relevant code patterns
2. Uses ai_edit to generate and apply edits
3. Has proper argument parsing
4. Includes helpful comments and documentation

The script should be saved to: {output_file}

[Example of rise_snprintf.py]
Create a Python script that performs the following refactoring task: replace sprintf with snprintf for the RISE project.
{open(os.path.join(SAMPLE_DIR, "rise_snprintf.py")).read()}
[Example of rise_snprintf.py End]

The following are content of search_util and ai_edit files:
[search_utils.py]
{open(os.path.join(AI_SCRIPTING_DIR, "search_utils.py")).read()}
[search_utils.py End]

[ai_edit.py]
{open(os.path.join(AI_SCRIPTING_DIR, "ai_edit.py")).read()}
[ai_edit.py End]
"""

    # Call the LLM to generate the script
    response = llm_utils.call_llm(
        prompt=llm_prompt,
        purpose="Generate refactoring script",
        model=llm_utils.GeminiModel.GEMINI_2_5_PRO
    )

    # Save the generated script
    with open(output_file, 'w') as f:
        f.write(response)

    console.print(f"[green]Generated refactoring script saved to: {output_file}[/green]")

def main():
    parser = argparse.ArgumentParser(description='Generate a refactoring script based on user prompt')
    parser.add_argument('prompt', type=str, help='Description of the refactoring task')
    parser.add_argument('--output', '-o', type=str, default=None,
                      help='Output file path (default: samples/<prompt_slug>.py)')
    args = parser.parse_args()

    # Generate output filename if not provided
    if args.output is None:
        # Create a slug from the prompt
        prompt_slug = args.prompt.lower().replace(' ', '_').replace('/', '_')[:15]
        output_file = os.path.join(SAMPLE_DIR, f"{prompt_slug}.py")
    else:
        output_file = args.output

    # Ensure the output directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    generate_refactor_script(args.prompt, output_file)

if __name__ == "__main__":
    main()
