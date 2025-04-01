import subprocess
import sys
import shlex
import re
from dataclasses import dataclass, field
from typing import List, Optional
from rich.console import Console
from llm_utils import call_llm, GEMINI_2_5_PRO

console = Console()

@dataclass
class CodeLine:
    """Represents a single line within a matched code block."""
    line_number: int
    content: str
    is_match: bool # True if this line directly matched the rg pattern, False if it's context

@dataclass
class CodeMatch:
    """Represents a contiguous block of code containing one or more matches."""
    filepath: str
    start_line: int # First line number in the block (including context)
    end_line: int   # Last line number in the block (including context)
    lines: List[CodeLine] = field(default_factory=list) # List of lines in the block

    @property
    def code_block(self) -> str:
        """Returns the full code block as a single string."""
        return "\n".join(line.content for line in self.lines)

    @property
    def matched_lines_numbers(self) -> List[int]:
        """Returns line numbers that directly matched the pattern."""
        return [line.line_number for line in self.lines if line.is_match]

@dataclass
class CodeMatchedResult:
    """Encapsulates the results of an rg search."""
    total_files_matched: int = 0
    total_lines_matched: int = 0 # Number of lines *directly* matching the pattern
    matches: List[CodeMatch] = field(default_factory=list) # List of matched code blocks
    rg_stats_raw: str = "" # Raw statistics output from rg --stats
    rg_command_used: str = "" # The full rg command executed

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

def generate_rg_command(user_prompt: str, folder: str) -> str:
    """Asks the LLM to suggest rg command arguments based on the user prompt."""
    prompt = (f"""
You are an expert programmer helping with code refactoring.
The user wants to perform the following refactoring task in the folder '{folder}':
"{user_prompt}"

Based *only* on this request, suggest a single `rg` (ripgrep) command's arguments to find the relevant lines of code AND a few lines of context around them.
Your goal is to find the lines that *might* need modification, along with surrounding code for context.
Focus on creating a pattern that accurately captures the code snippets the user wants to change.

Essential `rg` flags for this task:
- -e PATTERN or -F PATTERN: The search pattern (regex or fixed string).
- -t TYPE: (Recommended) Search only specific file types (e.g., `-t py`).
- -n: Show line numbers (required for parsing).
- --with-filename: Show filename for each match (required for parsing).
- -A NUM: Show NUM lines after each match.
- -B NUM: Show NUM lines before each match.
- OR -C NUM: Show NUM lines of context (equivalent to -A NUM -B NUM). A value of 3-5 is usually good.
- --stats: Include summary statistics (required for parsing).

Your output should be ONLY the `rg` command arguments, suitable for appending to `rg ... {folder}`.
Example output format: `-e "some_pattern" -t py -n --with-filename -C 3 --stats`
Another example: `-F "exact string" -w -i -n --with-filename -B 2 -A 2 --stats`

Do not include the `rg` command itself or the folder path in your output. Just provide the arguments.
Start the arguments directly. Ensure `-n`, `--with-filename`, `--stats`, and some context flag (-A/-B or -C) are included.
Enclose regex patterns in double quotes if they contain spaces or special characters.
""")

    suggested_args_str = call_llm(
         prompt, "Suggesting rg command", model_name=GEMINI_2_5_PRO # Use more capable model
    )

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

    required_flags_present = {
        "context": any(re.match(r"-[ABC]", arg) for arg in current_args_list),
        "line_number": "-n" in current_args_list or "--line-number" in current_args_list,
        "filename": "--with-filename" in current_args_list or "-H" in current_args_list,
        "stats": "--stats" in current_args_list
    }

    missing_flags = []
    if not required_flags_present["context"]:
        missing_flags.append("-C 3") # Default context
    if not required_flags_present["line_number"]:
        missing_flags.append("-n")
    if not required_flags_present["filename"]:
        missing_flags.append("--with-filename")
    if not required_flags_present["stats"]:
        missing_flags.append("--stats")

    if missing_flags:
        cleaned_args += " " + " ".join(missing_flags)
        console.print(f"[yellow]Info: Added missing required flags: {' '.join(missing_flags)}[/yellow]")

    # Remove flags that interfere with context/line parsing if present
    flags_to_remove = {'-l', '--files-with-matches', '--json', '-o', '--only-matching', '--count', '--files-without-match', '--count-matches'}
    final_args_list = [arg for arg in shlex.split(cleaned_args) if arg not in flags_to_remove]

    # Reconstruct the args string
    cleaned_args = " ".join(shlex.quote(arg) for arg in final_args_list)

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
    # Ensure required flags are present (redundant check, but safe)
    if "-n" not in args_list and "--line-number" not in args_list: args_list.append("-n")
    if "--with-filename" not in args_list and "-H" not in args_list: args_list.append("--with-filename")
    if "--stats" not in args_list: args_list.append("--stats")
    if not any(re.match(r"-[ABC]", arg) for arg in args_list): args_list.append("-C 3") # Add default context if missing

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
            _parse_rg_stats(result.rg_stats_raw, result)
        return result

    # --- Parsing rg Output ---
    # Regex to capture filename, line number, separator (: or -), and content
    # Handles paths with colons/hyphens before the line number part
    # Example: /path/to/file.c:123: content
    # Example: /path/to/file.c-122- content
    # Example: /path/to/file.c-122-    content (with spaces)
    # Example:    /path/to/file.c-122-    content (with indentation)
    # Example: 10-    def some_function():  (actual rg output format)
    line_regex = re.compile(r"^\s*(\d+)([:-])\s*(.*)$")
    # Regex for the block separator '--'
    separator_regex = re.compile(r"^--$")
    # Regex for stats lines (simple examples)
    stats_matches_regex = re.compile(r"(\d+)\s+matches")
    stats_lines_regex = re.compile(r"(\d+)\s+matched lines")
    stats_files_regex = re.compile(r"(\d+)\s+files contained matches")

    output_lines = rg_result.stdout.strip().split('\n')
    stats_section_start = -1

    # Find where the stats section begins (usually after the last '--')
    for i, line in reversed(list(enumerate(output_lines))):
        if stats_files_regex.search(line) or stats_matches_regex.search(line):
            # Rough heuristic: stats likely start around here
            # Look backwards for the preceding '--' or beginning of file if no '--' found
            found_separator = False
            for j in range(i, -1, -1):
                if separator_regex.match(output_lines[j]):
                    stats_section_start = j + 1
                    found_separator = True
                    break
            if not found_separator:
                # Stats might be the only output if e.g. only context matched
                # Find first line that looks like a stat
                for j in range(len(output_lines)):
                    if stats_files_regex.search(output_lines[j]) or \
                       stats_matches_regex.search(output_lines[j]) or \
                       re.search(r"\d+ files searched", output_lines[j]):
                        stats_section_start = j
                        break
                if stats_section_start == -1:
                    stats_section_start = 0  # Default to start if heuristics fail
            break
        elif separator_regex.match(line) and stats_section_start == -1:
            # If we hit a separator before finding stats, stats start after it
            stats_section_start = i + 1

    if stats_section_start == -1:
        # If no stats lines or separators found, assume all lines are content
        stats_section_start = len(output_lines)
        result.rg_stats_raw = ""  # No stats section found
    else:
        result.rg_stats_raw = "\n".join(output_lines[stats_section_start:]).strip()
        # Update output_lines to only contain the code match section
        output_lines = output_lines[:stats_section_start]

    # --- Process Code Match Lines ---
    current_filepath = None
    current_match = None
    blocks_by_file = {}  # Group blocks by file path
    
    for line in output_lines:
        # Skip empty lines
        if not line.strip():
            continue

        # Check if this is a file path line (doesn't match our line number pattern)
        match = line_regex.match(line)
        if not match:
            # If line doesn't match the number pattern and isn't empty, it's probably a file path
            if line.strip() and not separator_regex.match(line):
                current_filepath = line.strip()
                # Start a new match if we have a filepath
                if current_match:
                    if current_filepath not in blocks_by_file:
                        blocks_by_file[current_filepath] = []
                    blocks_by_file[current_filepath].append(current_match)
                    current_match = None
            # Skip separator lines without creating new blocks
            continue

        # Process a line with line number
        if match and current_filepath:
            lineno_str, separator, content = match.groups()
            try:
                lineno = int(lineno_str)
                is_match = (separator == ':')
                code_line = CodeLine(line_number=lineno, content=content, is_match=is_match)

                # Start a new block if:
                # 1. We don't have a current block
                # 2. The line number is not consecutive with the previous block
                if not current_match or (lineno > current_match.end_line + 1):
                    if current_match:
                        if current_filepath not in blocks_by_file:
                            blocks_by_file[current_filepath] = []
                        blocks_by_file[current_filepath].append(current_match)
                    current_match = CodeMatch(
                        filepath=current_filepath,
                        start_line=lineno,
                        end_line=lineno,
                        lines=[code_line]
                    )
                else:
                    # Continue the current block
                    current_match.lines.append(code_line)
                    current_match.end_line = lineno
            except ValueError:
                console.print(f"[yellow]Warning: Could not parse line number from rg output: {line}[/yellow]")

    # Add the last block if any
    if current_match:
        if current_filepath not in blocks_by_file:
            blocks_by_file[current_filepath] = []
        blocks_by_file[current_filepath].append(current_match)

    # Merge blocks for each file
    result.matches = []
    for filepath, blocks in blocks_by_file.items():
        if not blocks:
            continue
            
        # Sort blocks by start line
        blocks.sort(key=lambda b: b.start_line)
        
        # Merge overlapping or adjacent blocks
        current_block = blocks[0]
        for next_block in blocks[1:]:
            if next_block.start_line <= current_block.end_line + 1:
                # Merge blocks
                current_block.end_line = max(current_block.end_line, next_block.end_line)
                current_block.lines.extend(next_block.lines)
            else:
                # Start a new block
                result.matches.append(current_block)
                current_block = next_block
        
        # Add the last block
        result.matches.append(current_block)

    # --- Parse Stats Section ---
    _parse_rg_stats(result.rg_stats_raw, result)

    # --- Display Summary ---
    console.print(f"\nFound [bold cyan]{result.total_files_matched}[/bold cyan] file(s) with [bold cyan]{result.total_lines_matched}[/bold cyan] matching lines, forming [bold cyan]{len(result.matches)}[/bold cyan] code blocks.")
    if result.matches:
        # Display info about the first block as a sample
        first_match = result.matches[0]
        console.print(f"[dim]First block found in: {first_match.filepath} (Lines {first_match.start_line}-{first_match.end_line})[/dim]")

    return result


def _parse_rg_stats(stats_str: str, result: CodeMatchedResult):
    """Helper to parse the --stats output and update the CodeMatchedResult."""
    if not stats_str:
        return

    # Regex using non-capturing groups for flexibility
    stats_matches_regex = re.compile(r"(\d+)\s+(?:match|matches)")
    stats_lines_regex = re.compile(r"(\d+)\s+matched lines")
    stats_files_regex = re.compile(r"(\d+)\s+files contained matches")

    lines_matched = 0
    files_matched = 0

    # Search within the stats block
    lines_match = stats_lines_regex.search(stats_str)
    if lines_match:
        try:
            lines_matched = int(lines_match.group(1))
        except ValueError:
            pass

    files_match = stats_files_regex.search(stats_str)
    if files_match:
        try:
            files_matched = int(files_match.group(1))
        except ValueError:
            pass

    # If "matched lines" is missing, fall back to "matches" count
    if lines_matched == 0:
        matches_match = stats_matches_regex.search(stats_str)
        if matches_match:
            try:
                # Use this as a fallback, although it counts occurrences, not lines with occurrences
                lines_matched = int(matches_match.group(1))
            except ValueError:
                pass

    # Handle the case where we have no matches but stats are present
    if "0 matches" in stats_str or "0 matched lines" in stats_str:
        lines_matched = 0
        files_matched = 0

    result.total_lines_matched = lines_matched
    result.total_files_matched = files_matched