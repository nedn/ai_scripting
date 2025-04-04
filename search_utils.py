import subprocess
import sys
import shlex
import re
from dataclasses import dataclass, field
from typing import List, Optional
from rich.console import Console
from llm_utils import call_llm, GeminiModel
from code_block import CodeMatchedResult, CodeBlock, Line, MatchedLine

console = Console()

# --- Helper Functions ---

def run_rg(
    rg_args: List[str], folder: str, check: bool = True
) -> subprocess.CompletedProcess:
    """Runs the rg command with given arguments in the specified folder."""
    # Ensure folder is treated as a positional argument at the end
    command = ["rg"] + rg_args + ["--", folder] # Use -- to prevent folder being misinterpreted as an option
    console.print(f"[dim]Executing: {' '.join(shlex.quote(c) for c in command)}[/dim]")
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,  # We will check return code manually to handle '1' (no matches)
            encoding="utf-8",
            errors='replace' # Handle potential decoding errors
        )

        # rg exits with 1 if no matches are found, which isn't an "error" for our purpose.
        # rg exits with 0 if matches are found.
        # rg exits with > 1 for actual errors.
        if result.returncode > 1:
             console.print(f"[bold red]rg Error (Exit Code {result.returncode}):[/bold red]\n{result.stderr}")
             # Optionally raise an exception or handle differently if needed
             # For now, we'll let the caller handle the empty/error result.
        elif result.stderr and result.returncode == 0 and check: # Print stderr only if exit code was 0 but check=True
             # Might contain warnings even if matches were found
             console.print(f"[yellow]rg Warnings:[/yellow]\n{result.stderr}")

        # If check=True and return code is 1 (no matches), raise CalledProcessError
        if check and result.returncode == 1:
            raise subprocess.CalledProcessError(result.returncode, command, output=result.stdout, stderr=result.stderr)
        # If check=True and return code > 1, raise CalledProcessError
        elif check and result.returncode > 1:
            raise subprocess.CalledProcessError(result.returncode, command, output=result.stdout, stderr=result.stderr)


    except FileNotFoundError:
        console.print_exception()
        console.print(
            "[bold red]Error: 'rg' (ripgrep) command not found.[/bold red]"
        )
        console.print(
            "Please install ripgrep: https://github.com/BurntSushi/ripgrep#installation"
        )
        sys.exit(1)
    except subprocess.CalledProcessError as e:
         # Re-raise if check=True requested it
         if check:
             raise e
         # Otherwise (check=False), treat code 1 as non-fatal 'no matches'
         elif e.returncode != 1:
             console.print(f"[bold red]rg returned unexpected error (exit code {e.returncode}):[/bold red]")
             console.print(f"[bold red]stderr:[/bold red]\n{e.stderr}")
             console.print(f"[bold yellow]stdout:[/bold yellow]\n{e.stdout}")

    except Exception as e:
        console.print_exception()
        console.print(f"[bold red]Error running rg: {e}[/bold red]")
        sys.exit(1) # Or handle more gracefully depending on context
    return result

def generate_rg_command(user_prompt: str, folder: str, model: GeminiModel) -> str:
    """Asks the LLM to suggest rg command arguments based on the user prompt."""
    prompt = (f"""
You are an expert programmer helping with code refactoring.
The user wants to perform the following refactoring task in the folder '{folder}':
"{user_prompt}"

Based *only* on this request, suggest a single `rg` (ripgrep) command's arguments to find the relevant lines of code AND a few lines of context around them.
Your goal is to find the lines that *might* need modification, along with surrounding code for context.
Focus on creating a pattern that accurately captures the code snippets the user wants to change.

Only use the following `rg` flags for this task:
--regexp=PATTERN: A pattern to search for. This option can be provided multiple times,
    where all patterns given are searched. Lines matching at least one of the provided patterns are printed.
--type=TYPE: This flag limits ripgrep to searching files matching TYPE. Multiple --type flags may be provided.
--fixed-strings: Treat all patterns as literals instead of as regular expressions. When this flag is used, 
    special regular expression meta characters such as .().* should not need be escaped.

Your output should be ONLY the `rg` command arguments, suitable for appending to `rg ... {folder}`.
Example output format: `--regexp="some_pattern.*" --type=py`
Another example: `--fixed-strings "exact string" --type=h --type=c`

Do not include the `rg` command itself or the folder path in your output. Just provide the arguments.
Start the arguments directly. 
Enclose regex patterns in double quotes if they contain spaces or special characters.
""")

    suggested_args_str = call_llm(prompt, "Suggesting rg command", model=model)

    if not suggested_args_str or suggested_args_str.startswith("Error:"):
         console.print("[bold red]LLM failed to provide a suggestion or returned an error. Please provide rg arguments manually.[/bold red]")
         return "" # Return empty string to signal failure

    # --- Argument Parsing and Cleanup ---
    cleaned_args = suggested_args_str.strip()

    # Remove surrounding backticks/markdown code blocks
    cleaned_args = re.sub(r'^```[a-zA-Z]*\s*', '', cleaned_args) # Start ``` optional lang
    cleaned_args = re.sub(r'\s*```$', '', cleaned_args)       # End ```
    cleaned_args = cleaned_args.strip('`')                     # Single backticks

    # Remove potential 'rg ' prefix (case-insensitive)
    if cleaned_args.lower().startswith("rg "):
        cleaned_args = cleaned_args[3:].strip()

    # Remove potential folder path suffix more robustly
    # This is tricky if the folder name appears elsewhere in args.
    # A simple suffix check might be too greedy. We'll rely on the LLM prompt
    # and maybe manually remove it if it looks like `rg args... /path/to/folder`
    # Let's try removesuffix for exact match only
    if cleaned_args.endswith(folder):
         temp_args = cleaned_args[:-len(folder)].strip()
         # Avoid removing if it was part of a quoted argument like -g '!{folder}/*'
         # Heuristic: if the character before the folder path was not whitespace, it might be part of an arg
         if len(cleaned_args) == len(folder) or cleaned_args[-len(folder)-1].isspace():
              cleaned_args = temp_args


    # --- Ensure required flags ---
    # Use shlex.split for robust parsing of existing args
    try:
        current_args_list = shlex.split(cleaned_args)
    except ValueError as e:
        console.print(f"[yellow]Warning: Could not properly parse suggested rg args: {e}. Proceeding with raw string, but flag check might be inaccurate.[/yellow]")
        current_args_list = cleaned_args.split() # Fallback

    # Ensure generated args only contain allowed flags
    allowed_flags = ["--regexp", "--type", "--fixed-strings"]
    for arg in current_args_list:
        if arg.startswith("--") and not any(arg.startswith(flag) for flag in allowed_flags):
            console.print("[bold red]Error: Generated rg args contain invalid flags.[/bold red]")
            raise ValueError("Invalid flag '" + arg + "' in LLM-generated rg command: " + suggested_args_str)

    # Add required flags if missing
    proper_context = "--context=5" # TODO: Make this dynamic based on the user prompt
    current_args_list += ["--stats", "--line-number", "--heading", proper_context]

    # Reconstruct the args string
    cleaned_args = " ".join(shlex.quote(arg) for arg in current_args_list)

    return cleaned_args.strip()


def gather_search_results(rg_args_str: str, folder: str) -> CodeMatchedResult:
    """
    Runs rg with context and stats, parses the output into a CodeMatchedResult object.

    Args:
        rg_args_str: The string of arguments for the rg command (excluding rg and folder).
        folder: The folder to search in.

    Returns:
        A CodeMatchedResult object containing parsed matches and stats.
    """
    args_list = shlex.split(rg_args_str)
    # Check required flags are present, raise error if not
    required_flags = ["--stats", "--line-number", "--heading", "--context"]
    for flag in required_flags:
        if not any(arg.startswith(flag) for arg in args_list):
            raise ValueError("Missing required flag '" + flag + "' in rg command: " + rg_args_str)

    rg_result = run_rg(args_list, folder, check=False) # Don't raise on exit code 1 (no matches)

    full_command = f"rg {' '.join(shlex.quote(a) for a in args_list)} {shlex.quote(folder)}"
    result = CodeMatchedResult(rg_command_used=full_command)

    if rg_result.returncode > 1:
        console.print(f"[bold red]rg command failed. Cannot gather results.[/bold red]")
        # Result object will be empty, indicating failure
        return result

    # Handle no matches case
    if rg_result.returncode == 1:
        console.print("[yellow]No matches found.[/yellow]")
        # Try to parse stats from stderr if stdout is empty
        if not rg_result.stdout.strip() and rg_result.stderr:
            result.rg_stats_raw = rg_result.stderr.strip()
            _parse_rg_stats(result.rg_stats_raw)
        return result

    # --- Parsing rg Output ---
    # Regex to capture filename, line number, separator (: or -), and content
    # Handles paths with colons/hyphens before the line number part
    # Example: 
    # /path/to/file.c:
    # 121: matched content
    # 122- content
    # 123- content 
    # --
    # 148- 
    # 149: content (with indentation)
    # 150: content (with indentation)
    # 151- 
    # 123 matches
    # 123 matched lines
    # 1 files contained matches
    # (actual rg output format)

    # Regex for stats lines (simple examples)
    stats_matches_regex = re.compile(r"^(\d+)\s+matches$")

    output_lines = rg_result.stdout.strip().split('\n')
    stats_section_start = -1

    # Find where the stats section begins 
    for i, line in reversed(list(enumerate(output_lines))):
        if stats_matches_regex.search(line):
            stats_section_start = i
            break

    if stats_section_start == -1:
        # If no stats lines or separators found, assume all lines are content
        stats_section_start = len(output_lines)
        result.rg_stats_raw = ""  # No stats section found
    else:
        result.rg_stats_raw = "\n".join(output_lines[stats_section_start:]).strip()
        # Update output_lines to only contain the code match section
        output_lines = output_lines[:stats_section_start]

    # --- Parse Match Lines ---
    _parse_match_lines(output_lines, result)

    # --- Parse Stats Section ---
    rg_files_matched, rg_lines_matched = _parse_rg_stats(result.rg_stats_raw)

    assert result.total_files_matched == rg_files_matched, f"Total files matched: result {result.total_files_matched} != rg {rg_files_matched}"
    assert result.total_lines_matched == rg_lines_matched, f"Total lines matched: result {result.total_lines_matched} != rg {rg_lines_matched}"

    # --- Display Summary ---
    console.print(f"\nFound [bold cyan]{result.total_files_matched}[/bold cyan] file(s) with [bold cyan]{result.total_lines_matched}[/bold cyan] matching lines, forming [bold cyan]{len(result.matched_blocks)}[/bold cyan] code blocks.")
    if result.matched_blocks:
        # Display info about the first block as a sample
        first_match = result.matched_blocks[0]
        console.print(f"[dim]First block found in: {first_match.filepath} (Lines {first_match.start_line}-{first_match.end_line})[/dim]")
        console.print(f"[dim]Code block:[/dim]")
        console.print(first_match.code_block_with_line_numbers)

    return result


def _parse_match_lines(match_lines: List[str], result: CodeMatchedResult):
    """Helper to parse the match lines and update the CodeMatchedResult."""

    current_filepath: Optional[str] = None
    current_match: Optional[CodeBlock] = None
    # Regex to capture line number, separator (: or -), and the line content
    # It allows for potential leading/trailing whitespace around the content
    line_regex = re.compile(r"^(\d+)([:-])(.*)$")

    def finalize_current_match():
        """Helper function to add the current match to results if it exists."""
        nonlocal current_match
        if current_match:
            result.matched_blocks.append(current_match)
            current_match = None

    for line in match_lines:
        line_strip = line.strip()

        # Skip empty lines
        if not line_strip:
            continue

        # 1. Check for separator
        if line_strip == "--":
            finalize_current_match()
            continue # Move to the next line

        # 2. Check for code line pattern
        match = line_regex.match(line)
        if match:
            if not current_filepath:
                # Should not happen with valid rg output, but handle defensively
                console.print(f"[yellow]Warning: Found code line '{line}' without preceding filepath.[/yellow]")
                raise RuntimeError("Found code line without preceding filepath.")

            line_number_str, separator, content = match.groups()
            line_number = int(line_number_str)
            is_match = (separator == ':')

            code_line = MatchedLine(
                line_number=line_number,
                content=content, # Keep original content including leading whitespace
                is_match=is_match
            )

            # If this is the first line of a new block (no current_match)
            if current_match is None:
                current_match = CodeBlock(
                    filepath=current_filepath,
                    start_line=line_number,
                    lines=[code_line]
                )
            else:
                # Append to existing block
                # Ensure file paths match (should always be true in valid rg output)
                if current_match.filepath != current_filepath:
                     console.print(f"[yellow]Warning: File path mismatch within block. Expected {current_match.filepath}, got {current_filepath}[/yellow]")
                     raise RuntimeError("File path mismatch within block.")
                current_match.lines.append(code_line)

        # 3. Check for file path (if it's not a separator or code line)
        else:
            # Finalize any previous match before starting a new file
            finalize_current_match()

            # Assume this line is a file path
            current_filepath = line # Store the full line as the path
            # Reset current_match as we are starting a new file context
            current_match = None

    # After the loop, add the last processed match if it exists
    finalize_current_match()


def _parse_rg_stats(stats_str: str):
    """Parse the stats section of rg output and update the result object."""
    if not stats_str:
        return 0, 0

    # Regex patterns for different stats lines
    matches_re = re.compile(r"^(\d+)\s+matches$")
    lines_re = re.compile(r"^(\d+)\s+matched lines$")
    files_re = re.compile(r"^(\d+)\s+files contained matches$")

    matches = 0
    lines = 0
    files = 0

    for line in stats_str.split('\n'):
        if matches_re.search(line):
            matches = int(matches_re.search(line).group(1))
        elif lines_re.search(line):
            lines = int(lines_re.search(line).group(1))
        elif files_re.search(line):
            files = int(files_re.search(line).group(1))
    return files, lines