import unittest
import os
from typing import List
# Assuming these imports are correct relative to your project structure
from ai_scripting.ai_edit import _process_llm_output
from ai_scripting.code_block import CodeBlock, EditCodeBlock, Line, MatchedLine

class TestProcessLLMOutput(unittest.TestCase):
    def setUp(self):
        # Create a sample code block for testing
        self.sample_block = CodeBlock(
            filepath="test.py",
            start_line=1,
            lines=[
                MatchedLine(line_number=1, content="def test():\n", is_match=True),
                MatchedLine(line_number=2, content="    print('hello')\n", is_match=True),
                MatchedLine(line_number=3, content="    return 42\n", is_match=True)
            ]
        )
        self.current_batch = [(self.sample_block, "block_prompt")]

    def test_error_case(self):
        """Test that error cases return original blocks"""
        llm_output = "Error: Something went wrong"
        result = _process_llm_output(llm_output, self.current_batch)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], self.sample_block) # Original block should be returned

    def test_single_block_processing(self):
        """Test processing a single code block"""
        llm_output = """
<code_block>
def test():
    print('modified')
    return 42
</code_block>
"""
        result = _process_llm_output(llm_output, self.current_batch)
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], EditCodeBlock) # Check if it's the right type
        self.assertEqual(len(result[0].lines), 4)
        self.assertEqual(result[0].lines[1].content, "    print('modified')")

    def test_multiple_blocks_processing(self):
        """Test processing multiple code blocks"""
        block2 = CodeBlock(
            filepath="test2.py",
            start_line=1,
            lines=[
                MatchedLine(line_number=1, content="def test2():\n", is_match=True),
                MatchedLine(line_number=2, content="    return True\n", is_match=True)
            ]
        )
        current_batch = [(self.sample_block, "block1"), (block2, "block2")]

        llm_output = """
<code_block>
def test():
    print('modified1')
    return 42
</code_block>
<code_block>
def test2():
    return False
</code_block>
"""
        result = _process_llm_output(llm_output, current_batch)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], EditCodeBlock)
        self.assertIsInstance(result[1], EditCodeBlock)
        self.assertEqual(len(result[0].lines), 4)
        self.assertEqual(len(result[1].lines), 3)
        self.assertEqual(result[0].lines[1].content, "    print('modified1')")
        self.assertEqual(result[0].lines[2].content, "    return 42")
        self.assertEqual(result[1].lines[1].content, "    return False")

    def test_empty_block_processing(self):
        """Test processing empty code blocks (expecting original block back)"""
        llm_output = "<code_block></code_block>"
        result = _process_llm_output(llm_output, self.current_batch)
        self.assertEqual(result, [])




if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False) # Use exit=False if running in interactive env