from google import genai
from rich.console import Console
import os
import sys
from dotenv import load_dotenv
import tiktoken

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

def count_tokens(text: str) -> int:
    """Count the number of tokens in a text string."""
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

def call_llm(prompt: str, purpose: str = "LLM Interaction",
             model_name=GEMINI_2_FLASH) -> str:
    """Calls the configured Google AI model."""
    console.print(f"[cyan]Calling LLM model {model_name} for: {purpose}...[/cyan]")
    
    # Count input tokens
    input_tokens = count_tokens(prompt)
    console.print(f"[yellow]Input tokens: {input_tokens}[/yellow]")
    
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
        
        # Get response text and count output tokens
        response_text = response.text
        output_tokens = count_tokens(response_text)
        console.print(f"[green]Output tokens: {output_tokens}[/green]")
        
        return response_text
    except Exception as e:
        console.print(f"[bold red]LLM API call failed: {e}[/bold red]")
        # console.print_exception() # Optional: for more details
        return f"Error: LLM API call failed. Details: {e}"