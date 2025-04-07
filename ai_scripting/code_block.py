import dataclasses
from typing import List
from rich import console

console = console.Console()

@dataclasses.dataclass
class Line:
    """Represents a single line within a code block."""
    line_number: int # Relative to the file which contains this line
    content: str


@dataclasses.dataclass
class MatchedLine(Line):
    def __init__(self, line_number: int, content: str, is_match: bool):
        super().__init__(line_number=line_number, content=content)
        self.is_match = is_match


@dataclasses.dataclass
class CodeBlock:
    """Represents a contiguous block of code which can contain matched lines.

    This abstraction is used to represent a code block that can be matched by the rg command or a block of code that is generated by an LLM.
    """
    filepath: str
    start_line: int # First line number in the block (including context)
    lines: List[Line] = dataclasses.field(default_factory=list) # List of lines in the block
    _original_file_content: str = None
    _matched_lines_numbers: List[int] = None

    @property
    def end_line(self) -> int:
        """Returns the last line number in the block (including context)."""
        return self.start_line + len(self.lines) - 1

    @property
    def code_block_with_line_numbers(self) -> str:
        """Returns the full code block as a single string with line numbers."""
        lines = [f"{line.line_number}: {line.content.rstrip()}" for line in self.lines]
        return "\n".join(lines) + "\n"

    @property
    def code_block_without_line_numbers(self) -> str:
        """Returns the full code block as a single string without line numbers."""
        lines = [line.content.rstrip() for line in self.lines]
        return "\n".join(lines) + "\n"

    @property
    def matched_lines_numbers(self) -> List[int]:
        """Returns line numbers that directly matched the pattern."""
        if self._matched_lines_numbers is None:
            self._matched_lines_numbers = [l.line_number for l in self.lines if l.is_match]
        return self._matched_lines_numbers

    @property
    def num_matched_lines(self) -> int:
        """Returns the number of lines that matched the pattern."""
        return len(self.matched_lines_numbers)

    @property
    def original_file_content(self) -> str:
        """Returns the full original file content as a single string."""
        if self._original_file_content is None:
            with open(self.filepath, 'r') as file:
                self._original_file_content = file.read()
        return self._original_file_content

    @property
    def len_lines(self) -> int:
        """Returns the number of lines in the code block."""
        return len(self.lines)

class EditCodeBlock(CodeBlock):
    """Represents a code block that represent a code that has been edited by an LLM.

    It has an original end line, which is the last line of the original code block.
    Its start line in the file is the same as the first line of the original code block.
    """

    def __init__(self, lines: List[Line], original_block: CodeBlock):
        super().__init__(filepath=original_block.filepath, start_line=original_block.start_line, lines=lines)
        self.original_block = original_block
        for i, line in enumerate(lines):
            line.line_number = self.original_block.start_line + i

    @property
    def original_end_line(self) -> int:
        """Returns the last line number in the original code block."""
        return self.original_block.end_line

    @property
    def len_lines_of_original_block(self) -> int:
        """Returns the number of lines in the original code block."""
        return self.original_block.len_lines


@dataclasses.dataclass
class TargetFile:
    """Represents a target file that can be edited."""
    filepath: str
    blocks_to_edit: List[EditCodeBlock]
    _edited_blocks: List[EditCodeBlock] = dataclasses.field(default_factory=list)
    _already_applied_edits: bool = False
    _edited_block_for_whole_file: EditCodeBlock = None
    _original_file_content: str = None

    def add_edited_block(self, edited_block: EditCodeBlock):
        """Adds an edited block to the list of edited blocks."""
        if self._already_applied_edits:
            raise ValueError("Edits already applied")
        self._edited_blocks.append(edited_block)

    @property
    def original_file_content(self) -> str:
        """Returns the full original file content as a single string."""
        if self._original_file_content is None:
            if self._already_applied_edits:
                raise ValueError("Edits already applied. Cannot get original file content.")
            with open(self.filepath, 'r') as file:
                self._original_file_content = file.read()
        return self._original_file_content

    @property
    def whole_file_as_edit_block(self) -> EditCodeBlock:
        """Returns the whole file as an edit block."""
        if self._edited_block_for_whole_file is None:
            self._edited_block_for_whole_file = CodeBlock(
                    filepath=self.filepath,
                    start_line=1,
                    lines=[Line(line_number=i+1, content=line) for i, line in enumerate(self.original_file_content.split("\n"))])
        return self._edited_block_for_whole_file

    def apply_edits(self):
        """Applies the edits to the file."""
        if self._already_applied_edits:
            raise ValueError("Edits already applied")
        _edit_file_with_edited_blocks(self.filepath, self._edited_blocks)
        self._already_applied_edits = True


DEBUG_CODE_BLOCKS_EDITING = False


def _edit_file_with_edited_blocks(filepath: str, edit_blocks: List[EditCodeBlock]):
    """
    Takes a list of edit CodeBlocks and edits the file they represent.

    Args:
        filepath: The path to the file to edit
        edit_blocks: List of CodeBlock objects containing the edits to apply

    Raises:
        ValueError: If any block's filepath doesn't match the target filepath
    """
    for b in edit_blocks:
        if (b.filepath != filepath):
            raise ValueError(f"Block {b.filepath} does not match filepath {filepath}")

    # Read the original file content
    with open(filepath, 'r') as file:
        lines = file.readlines()

    # Sort the blocks by start line
    edit_blocks.sort(key=lambda x: x.start_line)

    # Track the line offset caused by previous edits
    line_offset = 0

    if DEBUG_CODE_BLOCKS_EDITING:
        code_block_debugging_file =  open("code_blocks.txt", "a")
        debug_console = console.Console(file=code_block_debugging_file)
    else:
        code_block_debugging_file = None
        debug_console = None

    if debug_console:
        debug_console.print(f" ======== FILE PATH: {filepath} ======== ")

    # Apply each edit block
    for block in edit_blocks:
        if debug_console:
            debug_console.print(f" === ORIGINAL BLOCK:\n {block.original_block.code_block_with_line_numbers}\n=== ")
            debug_console.print(f" === EDITED BLOCK:\n {block.code_block_with_line_numbers}\n=== ")
        # Calculate the actual line numbers in the current file state
        lines_index_start_original_block = block.start_line + line_offset - 1
        lines_index_end_original_block = lines_index_start_original_block + block.len_lines_of_original_block

        # Replace the lines in the file with the edited content if the lines
        lines = lines[:lines_index_start_original_block] + [l.content + "\n" for l in block.lines] + lines[lines_index_end_original_block:]

        # Update the line offset for subsequent blocks
        line_offset += block.len_lines - block.len_lines_of_original_block

    # Write the modified content back to the file
    with open(filepath, 'w') as file:
        file.writelines(lines)

    if code_block_debugging_file:
        code_block_debugging_file.close()


def CreateEditCodeBlockFromCodeString(editted_code_string: str, original_block: CodeBlock=None) -> EditCodeBlock:
    """Creates an EditCodeBlock from a code string."""
    lines = [Line(line_number=i+1, content=line) for i, line in enumerate(editted_code_string.split("\n"))]
    return EditCodeBlock(lines=lines, original_block=original_block)


@dataclasses.dataclass
class CodeMatchedResult:
    """Encapsulates the results of an rg search."""
    _total_lines_matched: int = None # Number of lines *directly* matching the pattern
    _total_files_matches: int = None # Number of files that matched the pattern
    _matched_blocks: List[CodeBlock] = None
    matched_files: List[TargetFile] = dataclasses.field(default_factory=list) # List of matched files
    rg_stats_raw: str = "" # Raw statistics output from rg --stats
    rg_command_used: str = "" # The full rg command executed

    @property
    def matched_blocks(self) -> List[CodeBlock]:
        """Returns the list of matched blocks."""
        if self._matched_blocks is None:
            self._matched_blocks = []
            for file in self.matched_files:
                self._matched_blocks += file.blocks_to_edit
        return self._matched_blocks

    @property
    def total_files_matched(self) -> int:
        """Returns the number of files that matched the pattern."""
        if self._total_files_matches is None:
            files_matches = set()
            for b in self.matched_blocks:
                files_matches.add(b.filepath)
            self._total_files_matches = len(files_matches)
        return self._total_files_matches

    @property
    def total_lines_matched(self) -> int:
        """Returns the number of lines that matched the pattern."""
        if self._total_lines_matched is None:
            self._total_lines_matched = sum(b.num_matched_lines for b in self.matched_blocks)
        return self._total_lines_matched

    def print_results(self, print_matches: bool = True):
        """Prints the results of the search."""
        console.print(f"\nFound [bold cyan]{self.total_files_matched}[/bold cyan] file(s) with [bold cyan]{self.total_lines_matched}[/bold cyan] matching lines, forming [bold cyan]{len(self.matched_blocks)}[/bold cyan] code blocks.")
        if len(self.matched_blocks) > 0 and print_matches:
            example_matched_block = self.matched_blocks[0]
            console.print(f"[dim]First block found in: {example_matched_block.filepath} (Lines {example_matched_block.start_line}-{example_matched_block.end_line})[/dim]")
            console.print(f"[dim]Code block:[/dim]")
            console.print(example_matched_block.code_block_with_line_numbers)


