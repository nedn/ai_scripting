import unittest
from ai_scripting.code_block import Line, MatchedLine, CodeBlock, CodeMatchedResult

class TestCodeLine(unittest.TestCase):
    def test_code_line_creation(self):
        line = Line(line_number=1, content="test line")
        self.assertEqual(line.line_number, 1)
        self.assertEqual(line.content, "test line")

class TestMatchedLine(unittest.TestCase):
    def test_matched_line_creation(self):
        line = MatchedLine(line_number=1, content="test line", is_match=True)
        self.assertEqual(line.line_number, 1)
        self.assertEqual(line.content, "test line")
        self.assertTrue(line.is_match)

class TestCodeBlock(unittest.TestCase):
    def setUp(self):
        self.code_block = CodeBlock(
            filepath="test.py",
            start_line=1,
            lines=[
                MatchedLine(line_number=1, content="def test():\n", is_match=True),
                MatchedLine(line_number=2, content="    print('hello')\n", is_match=True),
                MatchedLine(line_number=3, content="    return 42\n", is_match=True)
            ]
        )

    def test_code_block_creation(self):
        self.assertEqual(self.code_block.filepath, "test.py")
        self.assertEqual(self.code_block.start_line, 1)
        self.assertEqual(self.code_block.end_line, 3)
        self.assertEqual(len(self.code_block.lines), 3)

    def test_code_block_with_line_numbers(self):
        expected = "1: def test():\n2:     print('hello')\n3:     return 42\n"
        self.assertEqual(self.code_block.code_block_with_line_numbers, expected)

    def test_code_block_without_line_numbers(self):
        expected = "def test():\n    print('hello')\n    return 42\n"
        self.assertEqual(self.code_block.code_block_without_line_numbers, expected)

    def test_matched_lines_numbers(self):
        self.assertEqual(self.code_block.matched_lines_numbers, [1, 2, 3])

class TestCodeMatchedResult(unittest.TestCase):
    def setUp(self):
        self.code_block = CodeBlock(
            filepath="test.py",
            start_line=1,
            lines=[
                MatchedLine(line_number=1, content="def test():\n", is_match=True),
                MatchedLine(line_number=2, content="    print('hello')\n", is_match=True),
                MatchedLine(line_number=3, content="    return 42\n", is_match=False)
            ]
        )
        self.result = CodeMatchedResult(
            matched_blocks=[self.code_block],
            rg_stats_raw="2 matches\n2 matched lines\n1 files contained matches",
            rg_command_used="rg --regexp='test' --stats"
        )

    def test_code_matched_result_creation(self):
        """Test creating a CodeMatchedResult with matches."""
        self.assertEqual(len(self.result.matched_blocks), 1)
        self.assertEqual(self.result.total_files_matched, 1)
        self.assertEqual(self.result.total_lines_matched, 2)
        self.assertEqual(self.result.rg_stats_raw, "2 matches\n2 matched lines\n1 files contained matches")
        self.assertEqual(self.result.rg_command_used, "rg --regexp='test' --stats")

    def test_empty_code_matched_result(self):
        """Test creating an empty CodeMatchedResult."""
        empty_result = CodeMatchedResult(
            matched_blocks=[],
            rg_stats_raw="0 matches\n0 matched lines\n0 files contained matches",
            rg_command_used="rg --regexp='test' --stats"
        )
        self.assertEqual(len(empty_result.matched_blocks), 0)
        self.assertEqual(empty_result.total_files_matched, 0)
        self.assertEqual(empty_result.total_lines_matched, 0)

if __name__ == '__main__':
    unittest.main()
