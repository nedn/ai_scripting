from google import genai
from rich.console import Console
import os
import sys

import dataclasses
from typing import List, Optional, Dict, ClassVar
from dotenv import load_dotenv
import tiktoken

console = Console() 

# Load environment variables from .env file
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")

if not API_KEY:
    print("Error: GOOGLE_API_KEY not found in environment variables or .env file.")
    sys.exit(1)

@dataclasses.dataclass(frozen=True)
class _ModelData:
    """
    Internal dataclass to hold information about a specific Gemini model.
    Instances of this class are hashable due to frozen=True.
    """
    code_name: str
    input_tokens: int
    output_tokens: int
    version_family: str # Added for clarity, e.g., "2.5" or "2.0"

    def __str__(self):
        return self.code_name

    def __repr__(self):
        return (f"GeminiModel(code_name='{self.code_name}', "
                f"input_tokens={self.input_tokens}, "
                f"output_tokens={self.output_tokens}, "
                f"version_family='{self.version_family}')")

class GeminiModel:
    """
    Represents available Gemini 2.0 and 2.5 models and their properties.

    Each model is represented as a class attribute (e.g., GEMINI_2_5_PRO_EXP)
    which holds a hashable _ModelData object containing its details.
    """

    # Gemini 2.5 Models
    GEMINI_2_5_PRO_EXP: ClassVar[_ModelData] = _ModelData(
        code_name='gemini-2.5-pro-exp-03-25',
        input_tokens=1_000_000,
        output_tokens=64_000,
        version_family="2.5"
    )

    # Gemini 2.0 Models
    GEMINI_2_0_FLASH: ClassVar[_ModelData] = _ModelData(
        code_name='gemini-2.0-flash',
        input_tokens=1_048_576, # Often referred to as 1M
        output_tokens=65_536,   # Using the higher documented limit
        version_family="2.0"
    )
    GEMINI_2_0_FLASH_LITE: ClassVar[_ModelData] = _ModelData(
        code_name='gemini-2.0-flash-lite',
        input_tokens=1_000_000,
        output_tokens=8_192,
        version_family="2.0"
    )
    GEMINI_2_0_FLASH_THINKING_EXP: ClassVar[_ModelData] = _ModelData(
        code_name='gemini-2.0-flash-thinking-exp-01-21',
        input_tokens=1_000_000, # Assuming 1M based on family
        output_tokens=64_000,
        version_family="2.0"
    )

    # --- Helper methods ---

    _models: ClassVar[Dict[str, _ModelData]] = {
        m.code_name: m for m in [
            GEMINI_2_5_PRO_EXP,
            GEMINI_2_0_FLASH,
            GEMINI_2_0_FLASH_LITE,
            GEMINI_2_0_FLASH_THINKING_EXP,
        ]
    }

    @classmethod
    def list_models(cls) -> List[_ModelData]:
        """Returns a list of all defined model data objects."""
        return list(cls._models.values())

    @classmethod
    def get_by_code_name(cls, code_name: str) -> Optional[_ModelData]:
        """Retrieves a model data object by its code name."""
        return cls._models.get(code_name)

def count_tokens(text: str) -> int:
    """Count the number of tokens in a text string."""
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

DEBUG_LLM_CALLS = False

def call_llm(prompt: str, purpose: str, model: GeminiModel) -> str:
    """Calls the configured Google AI model."""
    console.print(f"[cyan]Calling LLM model {model.code_name} for: {purpose}...[/cyan]")

    if DEBUG_LLM_CALLS:
        llm_log_file = open("llm_log.txt", "a")
        llm_log_console = Console(file=llm_log_file)
    else:
        llm_log_file = None
        llm_log_console = None
        
    if llm_log_console:
        llm_log_console.print("==== PROMT ====")
        llm_log_console.print(prompt)
    
    # Count input tokens
    input_tokens = count_tokens(prompt)
    if input_tokens > model.input_tokens:
        console.print(f"[bold red]Input tokens: {input_tokens} exceeds the maximum allowed tokens: {model.input_tokens}[/bold red]")
        raise ValueError(f"Input tokens: {input_tokens} exceeds the maximum allowed tokens: {model.input_tokens}")
    
    console.print(f"[yellow]Input tokens: {input_tokens}[/yellow]")
    
    try:
        client = genai.Client(api_key=API_KEY)
        response = client.models.generate_content(
            model=model.code_name,
            contents=prompt,
        )
        # Check for empty or blocked response
        if not response.candidates:
            # print("DEBUG: No candidates in response.")
            # print(f"DEBUG: Prompt feedback: {response.prompt_feedback}")
            return "Error: LLM response blocked or empty. Check safety settings or prompt."
        
        # Get response text and count output tokens
        response_text = response.text
        output_tokens = count_tokens(response_text)
        console.print(f"[green]Output tokens: {output_tokens}[/green]")
        
        if llm_log_console:
            llm_log_console.print("==== RESPONSE ====")
            llm_log_console.print(response_text)

        return response_text
    except Exception as e:
        console.print(f"[bold red]LLM API call failed: {e}[/bold red]")
        # console.print_exception() # Optional: for more details
        return f"Error: LLM API call failed. Details: {e}"
    finally:
        if llm_log_file:
            llm_log_file.close()