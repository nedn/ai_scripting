# AI Scripting Toolkit

A powerful toolkit for automating code refactoring and analysis using AI. This project provides utilities for searching, analyzing, and modifying codebases with the help of AI models.

## Features

- Advanced code search capabilities with context-aware results
- AI-powered code editing and refactoring
- Support for multiple file types (C, C++, Header files)
- Rich console output for better visualization
- Example-driven editing with customizable prompts

## Installation

1. Clone this repository:
```bash
git clone https://github.com/nedn/ai_scripting.git
cd ai_scripting
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your environment variables in `.env`:
```
GOOGLE_API_KEY=your_api_key_here
```

## Example: Refactoring RISE snprintf

The `rise_snprintf.py` script demonstrates how to use the AI Scripting toolkit to refactor code. This example specifically focuses on replacing `sprintf` calls with `snprintf` in the RISE codebase.

### Prerequisites

1. Clone the RISE repository:
```bash
git clone https://github.com/aravindkrishnaswamy/RISE
cd RISE
git checkout 297d0339a7f7acd1418e322a30a21f44c7dbbb1d
```

2. Return to the AI Scripting directory:
```bash
cd ../ai_scripting
```

### Running the Example

Execute the script with:
```bash
python3 samples/rise_snprintf.py
```

By default, the script will:
1. Search for all `sprintf` calls in the RISE codebase
2. Generate an edit plan to replace them with `snprintf`
3. Apply the edits to the files

### Customization

You can limit the number of files to edit using the `--max-files-to-apply-ai-edit` parameter:
```bash
python3 samples/rise_snprintf.py --max-files-to-apply-ai-edit 5
```

Set the value to 0 to apply edits to all matched files.

## Project Structure

- `ai_scripting/` - Core package containing the main functionality
- `samples/rise_snprintf.py` - Example script demonstrating code refactoring
- `samples/snprintf-edits.example` - Example file for edit patterns 
- `run_tests.py` - Test runner for the project
- `agentic_edit.py` - AI-powered editing commandline

## Dependencies

- google-genai - For AI model integration
- python-dotenv - Environment variable management
- rich - Enhanced console output
- tiktoken - Token counting for AI models

## License

This project is licensed under the terms specified in the LICENSE file.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

To run all the unittests:
```bash
run_tests.py
```

To run only the unittests whose name has substring `foo`

```bash
run_tests.py foo
```