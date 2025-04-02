import unittest
from code_block import CodeLine, MatchedLine, CodeBlock, CodeMatchedResult

class TestCodeLine(unittest.TestCase):
    def test_code_line_creation(self):
        line = CodeLine(line_number=1, content="test line")
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
        self.lines = [
            MatchedLine(line_number=1, content="context line", is_match=False),
            MatchedLine(line_number=2, content="matched line", is_match=True),
            MatchedLine(line_number=3, content="another context", is_match=False)
        ]
        self.code_block = CodeBlock(
            filepath="test.py",
            start_line=1,
            end_line=3,
            lines=self.lines
        )

    def test_code_block_creation(self):
        self.assertEqual(self.code_block.filepath, "test.py")
        self.assertEqual(self.code_block.start_line, 1)
        self.assertEqual(self.code_block.end_line, 3)
        self.assertEqual(len(self.code_block.lines), 3)

    def test_code_block_property(self):
        expected = "1: context line\n2: matched line\n3: another context"
        self.assertEqual(self.code_block.code_block, expected)

    def test_matched_lines_numbers(self):
        self.assertEqual(self.code_block.matched_lines_numbers, [2])

class TestCodeMatchedResult(unittest.TestCase):
    def setUp(self):
        self.lines = [
            MatchedLine(line_number=1, content="matched line", is_match=True),
            MatchedLine(line_number=2, content="another match", is_match=True)
        ]
        self.code_block = CodeBlock(
            filepath="test.py",
            start_line=1,
            end_line=2,
            lines=self.lines
        )
        self.result = CodeMatchedResult(
            total_files_matched=1,
            total_lines_matched=2,
            matches=[self.code_block],
            rg_stats_raw="2 matches",
            rg_command_used="rg test"
        )

    def test_code_matched_result_creation(self):
        self.assertEqual(self.result.total_files_matched, 1)
        self.assertEqual(self.result.total_lines_matched, 2)
        self.assertEqual(len(self.result.matches), 1)
        self.assertEqual(self.result.rg_stats_raw, "2 matches")
        self.assertEqual(self.result.rg_command_used, "rg test")

    def test_empty_code_matched_result(self):
        empty_result = CodeMatchedResult()
        self.assertEqual(empty_result.total_files_matched, 0)
        self.assertEqual(empty_result.total_lines_matched, 0)
        self.assertEqual(len(empty_result.matches), 0)
        self.assertEqual(empty_result.rg_stats_raw, "")
        self.assertEqual(empty_result.rg_command_used, "")

if __name__ == '__main__':
    unittest.main()
