import collections
import dataclasses
import os
import sys
from typing import List, Optional, Dict, ClassVar

import dotenv
from google import genai
from rich import console
import tiktoken


console = console.Console()

# Load environment variables from .env file
dotenv.load_dotenv()

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

    Each model is represented as a class attribute (e.g., GEMINI_2_5_PRO)
    which holds a hashable _ModelData object containing its details.
    """

    # Gemini 2.5 Models
    GEMINI_2_5_PRO: ClassVar[_ModelData] = _ModelData(
        code_name='gemini-2.5-pro-preview-03-25',
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

    # --- Helper methods ---

    _models: ClassVar[Dict[str, _ModelData]] = {
        m.code_name: m for m in [
            GEMINI_2_5_PRO,
            GEMINI_2_0_FLASH,
            GEMINI_2_0_FLASH_LITE,
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


# Define pricing structures based on the provided image
# Using _ModelData instances as keys makes it easy to link pricing to models
# Prices are per 1 Million tokens in USD
MODEL_PRICING = {
    GeminiModel.GEMINI_2_5_PRO: {
        'input': {
            'threshold_tokens': 200_000,
            'price_below_threshold_per_1M': 1.25,
            'price_above_threshold_per_1M': 2.50,
        },
        'output': { # Includes thinking tokens
            'threshold_tokens': 200_000, # Threshold is based on input prompt size
            'price_below_threshold_per_1M': 10.00,
            'price_above_threshold_per_1M': 15.00,
        }
    },
    GeminiModel.GEMINI_2_0_FLASH: {
        'input': {'price_per_1M': 0.1}, # Hypothetical example price
        'output': {'price_per_1M': 0.5} # Hypothetical example price
    },
    GeminiModel.GEMINI_2_0_FLASH_LITE: {
        'input': {'price_per_1M': 0.075}, # Hypothetical example price
        'output': {'price_per_1M': 0.3} # Hypothetical example price
    },
}


class TokensTracker:
    """
    Keeps track of input and output token usage for different Gemini models
    and calculates the approximate cost based on known pricing.
    """
    def __init__(self):
        """Initializes the token tracker with zero usage."""
        # Stores usage: key = _ModelData instance, value = {'input': total_input, 'output': total_output}
        self._usage: Dict[_ModelData, Dict[str, int]] = collections.defaultdict(lambda: {'input': 0, 'output': 0})

    def track_usage(self, model: _ModelData, input_tokens: int, output_tokens: int):
        """
        Records token usage for a specific model instance.

        Args:
            model: The _ModelData instance representing the model used.
            input_tokens: The number of input tokens consumed in the request.
            output_tokens: The number of output tokens generated (including thinking tokens if applicable).

        Raises:
            TypeError: If the model is not a valid _ModelData instance.
            ValueError: If token counts are negative.
        """
        # Find the canonical _ModelData instance from GeminiModel class attributes
        # This ensures we use the hashable instance defined in GeminiModel
        canonical_model = None
        for attr_name in dir(GeminiModel):
             attr_value = getattr(GeminiModel, attr_name)
             if isinstance(attr_value, _ModelData) and attr_value.code_name == model.code_name:
                 canonical_model = attr_value
                 break

        if canonical_model is None:
             # Allow tracking even if not predefined, but cost calculation might fail
             print(f"Warning: Tracking usage for model '{model.code_name}' which is not predefined in GeminiModel.")
             canonical_model = model # Use the provided model object directly as key

        if not isinstance(canonical_model, _ModelData):
             raise TypeError(f"Model must be an instance of _ModelData, got {type(model)}")
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("Token counts cannot be negative")

        self._usage[canonical_model]['input'] += input_tokens
        self._usage[canonical_model]['output'] += output_tokens

    def get_usage_summary(self) -> Dict[str, Dict[str, int]]:
        """
        Returns a summary of total token usage per model code name.

        Returns:
            A dictionary where keys are model code names (str) and values are
            dictionaries {'input': total_input_tokens, 'output': total_output_tokens}.
        """
        summary = {}
        for model_data, counts in self._usage.items():
            summary[model_data.code_name] = counts.copy()
        return summary

    def reset_usage(self):
        """Resets all tracked token counts to zero."""
        self._usage.clear()

    def get_approximate_cost(self) -> float:
        """
        Calculates the approximate total cost in USD based on tracked usage and known pricing.

        Note:
        - Uses pricing defined in the global `MODEL_PRICING` dictionary.
        - For models with tiered pricing (like Gemini 2.5 Pro Preview), the tier
          is determined based on the *total accumulated input tokens* for that model
          in the tracker. This is an *approximation*. Accurate cost calculation
          would require applying the tier based on the input size of *each individual request*.
        - If pricing information is missing for a tracked model, its usage will
          not contribute to the cost, and a warning will be printed.

        Returns:
            The estimated total cost in USD.
        """
        total_cost = 0.0
        unpriced_models: Set[str] = set()

        for model_data, counts in self._usage.items():
            if model_data in MODEL_PRICING:
                pricing_info = MODEL_PRICING[model_data]
                input_count = counts['input']
                output_count = counts['output']

                # Calculate Input Cost
                input_cost = 0.0
                input_pricing = pricing_info.get('input', {})
                if 'price_per_1M' in input_pricing: # Simple pricing
                    input_price_per_1M = input_pricing['price_per_1M']
                    input_cost = (input_count / 1_000_000) * input_price_per_1M
                elif 'threshold_tokens' in input_pricing: # Tiered pricing
                    threshold = input_pricing['threshold_tokens']
                    # Approximation: Apply tier based on *total* accumulated input
                    if input_count <= threshold:
                        input_price_per_1M = input_pricing['price_below_threshold_per_1M']
                    else:
                        input_price_per_1M = input_pricing['price_above_threshold_per_1M']
                    input_cost = (input_count / 1_000_000) * input_price_per_1M
                else:
                     # Handle case where 'input' key exists but has no recognized pricing structure
                     unpriced_models.add(f"{model_data.code_name} (input pricing invalid)")


                # Calculate Output Cost
                output_cost = 0.0
                output_pricing = pricing_info.get('output', {})
                if 'price_per_1M' in output_pricing: # Simple pricing
                     output_price_per_1M = output_pricing['price_per_1M']
                     output_cost = (output_count / 1_000_000) * output_price_per_1M
                elif 'threshold_tokens' in output_pricing: # Tiered pricing (threshold based on *input*)
                     threshold = output_pricing['threshold_tokens']
                     # Approximation: Apply tier based on *total* accumulated input
                     if input_count <= threshold:
                          output_price_per_1M = output_pricing['price_below_threshold_per_1M']
                     else:
                          output_price_per_1M = output_pricing['price_above_threshold_per_1M']
                     output_cost = (output_count / 1_000_000) * output_price_per_1M
                else:
                     # Handle case where 'output' key exists but has no recognized pricing structure
                     unpriced_models.add(f"{model_data.code_name} (output pricing invalid)")
                total_cost += input_cost + output_cost

        return total_cost

    def add_other_token_tracker(self, other: 'TokensTracker') -> 'TokensTracker':
        """
        Combines the usage of another TokensTracker object into the current one.

        Args:
            other: The TokensTracker object to combine with the current one.    
        Returns:
            A new TokensTracker object with combined usage.
        """
        for model_data, counts in other._usage.items():
            self._usage[model_data]['input'] += counts['input']
            self._usage[model_data]['output'] += counts['output']
        return self


def count_tokens(text: str) -> int:
    """Count the number of tokens in a text string."""
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

DEBUG_LLM_CALLS = False

def call_llm(prompt: str, purpose: str, model: GeminiModel, token_tracker: TokensTracker=None) -> str:
    """Calls the configured Google AI model."""
    console.print(f"[cyan]Calling LLM model {model.code_name} for: {purpose}...[/cyan]")

    if DEBUG_LLM_CALLS:
        llm_log_file = open("llm_log.txt", "a", encoding='utf-8')
        llm_log_console = console.Console(file=llm_log_file)
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
    if token_tracker:
        token_tracker.track_usage(model, input_tokens, 0)
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
        if token_tracker:
            token_tracker.track_usage(model, 0, output_tokens)
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


