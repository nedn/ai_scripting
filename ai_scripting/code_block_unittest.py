import unittest
import os
import tempfile
from ai_scripting import code_block

class TestCodeLine(unittest.TestCase):
    def test_code_line_creation(self):
        line = code_block.Line(line_number=1, content="test line")
        self.assertEqual(line.line_number, 1)
        self.assertEqual(line.content, "test line")

class TestMatchedLine(unittest.TestCase):
    def test_matched_line_creation(self):
        line = code_block.MatchedLine(line_number=1, content="test line", is_match=True)
        self.assertEqual(line.line_number, 1)
        self.assertEqual(line.content, "test line")
        self.assertTrue(line.is_match)

class TestCodeBlock(unittest.TestCase):
    def setUp(self):
        self.code_block = code_block.CodeBlock(
            filepath="test.py",
            start_line=1,
            lines=[
                code_block.MatchedLine(line_number=1, content="def test():\n", is_match=True),
                code_block.MatchedLine(line_number=2, content="    print('hello')\n", is_match=True),
                code_block.MatchedLine(line_number=3, content="    return 42\n", is_match=True)
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
        self.code_block = code_block.CodeBlock(
            filepath="test.py",
            start_line=1,
            lines=[
                code_block.MatchedLine(line_number=1, content="def test():\n", is_match=True),
                code_block.MatchedLine(line_number=2, content="    print('hello')\n", is_match=True),
                code_block.MatchedLine(line_number=3, content="    return 42\n", is_match=False)
            ]
        )
        self.target_file = code_block.TargetFile(
            filepath="test.py",
            blocks_to_edit=[self.code_block]
        )
        self.result = code_block.CodeMatchedResult(
            matched_files=[self.target_file],
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
        empty_result = code_block.CodeMatchedResult(
            matched_files=[code_block.TargetFile(filepath="test.py", blocks_to_edit=[])],
            rg_stats_raw="0 matches\n0 matched lines\n0 files contained matches",
            rg_command_used="rg --regexp='test' --stats"
        )
        self.assertEqual(len(empty_result.matched_blocks), 0)
        self.assertEqual(empty_result.total_files_matched, 0)
        self.assertEqual(empty_result.total_lines_matched, 0)


class TestEditFileWithEditedBlocks(unittest.TestCase):
    def setUp(self):
        # Create a temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w+', suffix=".py")
        self.temp_file.write("""def test1():
    print('hello')
    return 42

# comment in the middle

def test2():
    return True
""")
        self.temp_file.close()
        self.temp_filepath = self.temp_file.name # Store the name

    def tearDown(self):
        # Clean up the temporary file
        if os.path.exists(self.temp_filepath):
             os.unlink(self.temp_filepath)

    def test_single_block_edit(self):
        """Test editing a single block in a file"""
        edited_block = code_block.EditCodeBlock(
            lines=[
                code_block.Line(line_number=1, content="def testFoo():"),
                code_block.Line(line_number=2, content="    print('modified')"),
                code_block.Line(line_number=3, content="    return 42")
            ],
            original_block=code_block.CodeBlock(
                filepath=self.temp_filepath,
                start_line=1,
                lines=[
                    code_block.MatchedLine(line_number=1, content="def test1():", is_match=True),
                    code_block.MatchedLine(line_number=2, content="    print('hello')", is_match=True),
                    code_block.MatchedLine(line_number=3, content="    return 42", is_match=True)
                ]
            )
        )

        code_block._edit_file_with_edited_blocks(self.temp_filepath, [edited_block])

        with open(self.temp_filepath, 'r') as f:
            content = f.read()
            expected_content = """def testFoo():
    print('modified')
    return 42

# comment in the middle

def test2():
    return True
"""
            self.assertEqual(content, expected_content, "Actual content: " + repr(content))

    def test_multiple_blocks_edit(self):
        """Test editing multiple blocks in a file"""
        edited_blocks = [
            code_block.EditCodeBlock(
                lines=[
                    code_block.Line(line_number=1, content="def test1():"),
                    code_block.Line(line_number=2, content="    print('modified1')"),
                    code_block.Line(line_number=3, content="    return 42")
                ],
                original_block=code_block.CodeBlock(
                    filepath=self.temp_filepath,
                    start_line=1,
                    lines=[
                        code_block.MatchedLine(line_number=1, content="def test1():", is_match=True),
                        code_block.MatchedLine(line_number=2, content="    print('hello')", is_match=True),
                        code_block.MatchedLine(line_number=3, content="    return 42", is_match=True)
                    ]
                )
            ),
            code_block.EditCodeBlock(
                lines=[
                    code_block.Line(line_number=7, content="def test2():"),
                    code_block.Line(line_number=8, content="    return False")
                ],
                original_block=code_block.CodeBlock(
                    filepath=self.temp_filepath,
                    start_line=7,
                    lines=[
                        code_block.MatchedLine(line_number=7, content="def test2():", is_match=True),
                        code_block.MatchedLine(line_number=8, content="    return True", is_match=True)
                    ]
                )
            )
        ]

        code_block._edit_file_with_edited_blocks(self.temp_filepath, edited_blocks)

        with open(self.temp_filepath, 'r') as f:
            content = f.read()
            expected_content = """def test1():
    print('modified1')
    return 42

# comment in the middle

def test2():
    return False
"""
            self.assertEqual(content, expected_content)

    def test_filepath_mismatch(self):
        """Test that filepath mismatch raises ValueError"""
        edited_block = code_block.EditCodeBlock(
            lines=[
                code_block.Line(line_number=1, content="def test1():"),
                code_block.Line(line_number=2, content="    print('modified')"),
                code_block.Line(line_number=3, content="    return 42")
            ],
            original_block=code_block.CodeBlock(
                filepath="wrong_file.py",
                start_line=1,
                lines=[
                    code_block.MatchedLine(line_number=1, content="def test1():", is_match=True),
                    code_block.MatchedLine(line_number=2, content="    print('hello')", is_match=True),
                    code_block.MatchedLine(line_number=3, content="    return 42", is_match=True)
                ]
            )
        )

        with self.assertRaises(ValueError):
            code_block._edit_file_with_edited_blocks(self.temp_filepath, [edited_block])

    def test_block_size_change(self):
        """Test editing a block that changes in size"""
        edited_block = code_block.EditCodeBlock(
            lines=[
                code_block.Line(line_number=1, content="def test1():"),
                code_block.Line(line_number=2, content="    print('modified')"),
                code_block.Line(line_number=3, content="    print('extra line')"),
                code_block.Line(line_number=4, content="    return 42")
            ],
            original_block=code_block.CodeBlock(
                filepath=self.temp_filepath,
                start_line=1,
                lines=[
                    code_block.MatchedLine(line_number=1, content="def test1():", is_match=True),
                    code_block.MatchedLine(line_number=2, content="    print('hello')", is_match=True),
                    code_block.MatchedLine(line_number=3, content="    return 42", is_match=True)
                ]
            )
        )

        code_block._edit_file_with_edited_blocks(self.temp_filepath, [edited_block])

        with open(self.temp_filepath, 'r') as f:
            content = f.read()
            expected_content = """def test1():
    print('modified')
    print('extra line')
    return 42

# comment in the middle

def test2():
    return True
"""
            self.assertEqual(content, expected_content)

if __name__ == '__main__':
    unittest.main()


