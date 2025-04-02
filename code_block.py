from dataclasses import dataclass, field
from typing import List

@dataclass
class CodeLine:
    """Represents a single line within a matched code block."""
    line_number: int
    content: str
    is_match: bool # True if this line directly matched the rg pattern, False if it's context

@dataclass
class CodeBlock:
    """Represents a contiguous block of code containing one or more matches."""
    filepath: str
    start_line: int # First line number in the block (including context)
    end_line: int   # Last line number in the block (including context)
    lines: List[CodeLine] = field(default_factory=list) # List of lines in the block

    @property
    def code_block(self) -> str:
        """Returns the full code block as a single string with line numbers."""
        return "\n".join(f"{line.line_number}: {line.content}" for line in self.lines)

    @property
    def matched_lines_numbers(self) -> List[int]:
        """Returns line numbers that directly matched the pattern."""
        return [line.line_number for line in self.lines if line.is_match]


@dataclass
class CodeMatchedResult:
    """Encapsulates the results of an rg search."""
    total_files_matched: int = 0
    total_lines_matched: int = 0 # Number of lines *directly* matching the pattern
    matches: List[CodeBlock] = field(default_factory=list) # List of matched code blocks
    rg_stats_raw: str = "" # Raw statistics output from rg --stats
    rg_command_used: str = "" # The full rg command executed
