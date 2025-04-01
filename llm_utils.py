from google import genai
from rich.console import Console
import os
import sys
from dotenv import load_dotenv

console = Console() 

# Load environment variables from .env file
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")

if not API_KEY:
    print("Error: GOOGLE_API_KEY not found in environment variables or .env file.")
    sys.exit(1)

# Gemini models
GEMINI_2_FLASH = "gemini-2.0-flash"
GEMINI_2_5_PRO = "gemini-2.5-pro-exp-03-25"


def call_llm(prompt: str, purpose: str = "LLM Interaction",
             model_name=GEMINI_2_FLASH) -> str:
    """Calls the configured Google AI model."""
    console.print(f"[cyan]Calling LLM model {model_name} for: {purpose}...[/cyan]")
    # Assuming genai setup happens elsewhere or API_KEY is valid
    # Simplified for brevity - replace with your actual API call logic
    try:
        client = genai.Client(api_key=API_KEY)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        # Check for empty or blocked response
        if not response.candidates:
            # print("DEBUG: No candidates in response.")
            # print(f"DEBUG: Prompt feedback: {response.prompt_feedback}")
            return "Error: LLM response blocked or empty. Check safety settings or prompt."
        # Handle potential exceptions during text access if needed, though usually safe after candidate check
        return response.text
    except Exception as e:
        console.print(f"[bold red]LLM API call failed: {e}[/bold red]")
        # console.print_exception() # Optional: for more details
        return f"Error: LLM API call failed. Details: {e}"