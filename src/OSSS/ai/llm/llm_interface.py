from abc import ABC, abstractmethod
from typing import Any, Iterator, Optional, Callable, Union
from OSSS.ai.observability import get_logger

# Create a logger for this module
logger = get_logger(__name__)

class LLMResponse:
    """
    Structured response from an LLM.

    Attributes
    ----------
    text : str
        The generated text content.
    tokens_used : Optional[int]
        Total number of tokens consumed, if known (for backward compatibility).
    input_tokens : Optional[int]
        Number of input tokens consumed, if known.
    output_tokens : Optional[int]
        Number of output tokens generated, if known.
    model_name : Optional[str]
        Identifier of the model used.
    finish_reason : Optional[str]
        Reason the model stopped generation (e.g., 'length', 'stop').
    """

    def __init__(
        self,
        text: str,
        tokens_used: Optional[int] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        model_name: Optional[str] = None,
        finish_reason: Optional[str] = None,
    ) -> None:
        self.text = text
        self.tokens_used = tokens_used
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.model_name = model_name
        self.finish_reason = finish_reason

        # Log the initialization of the LLMResponse
        logger.debug(f"LLMResponse initialized with text length: {len(text)} characters.")
        if self.tokens_used is not None:
            logger.debug(f"Tokens used: {self.tokens_used}")
        if self.input_tokens is not None:
            logger.debug(f"Input tokens: {self.input_tokens}")
        if self.output_tokens is not None:
            logger.debug(f"Output tokens: {self.output_tokens}")
        if self.model_name:
            logger.debug(f"Model used: {self.model_name}")
        if self.finish_reason:
            logger.debug(f"Finish reason: {self.finish_reason}")


class LLMInterface(ABC):
    """
    Abstract base class for large language model (LLM) interfaces.

    This interface defines the standard contract for any LLM implementation,
    including real providers like OpenAI or mock/stub classes used for testing.
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        stream: bool = False,
        on_log: Optional[Callable[[str], None]] = None,
        **kwargs: Any,
    ) -> Union[LLMResponse, Iterator[str]]:
        """
        Generate a completion based on the given prompt.

        Parameters
        ----------
        prompt : str
            The prompt text to send to the LLM.
        system_prompt : str, optional
            System prompt to provide context/instructions to the LLM.
        stream : bool, optional
            Whether to yield partial output tokens (for streaming).
        on_log : Callable[[str], None], optional
            Callback for logging internal events (e.g., prompt, usage).
        **kwargs : dict
            Additional keyword arguments specific to the implementation
            (e.g., temperature, max_tokens).

        Returns
        -------
        LLMResponse or Iterator[str]
            The structured response from the model or a stream of partial strings.
        """
        pass


class ExampleLLM(LLMInterface):
    """
    An example implementation of the LLMInterface for testing purposes.
    """

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        stream: bool = False,
        on_log: Optional[Callable[[str], None]] = None,
        **kwargs: Any,
    ) -> Union[LLMResponse, Iterator[str]]:
        """
        Example implementation that simulates generating a response from an LLM.
        """
        logger.info(f"Generating response for prompt: {prompt[:100]}...")  # Log the start of the process

        # Log system prompt if provided
        if system_prompt:
            logger.debug(f"Using system prompt: {system_prompt[:100]}...")

        # Simulate LLM response
        generated_text = f"Generated response based on the prompt: {prompt}"

        # Log the parameters used for generation
        logger.debug(f"Stream mode: {stream}")
        logger.debug(f"Additional kwargs: {kwargs}")

        # Simulate token usage (for logging purposes)
        tokens_used = len(generated_text.split())
        input_tokens = len(prompt.split())
        output_tokens = tokens_used  # Simulate output token count

        # Log token usage
        logger.debug(f"Simulated token usage - input: {input_tokens}, output: {output_tokens}, total: {tokens_used}")

        # Create the LLMResponse object
        response = LLMResponse(
            text=generated_text,
            tokens_used=tokens_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_name="ExampleModel",
            finish_reason="length",  # Simulated finish reason
        )

        # Log completion
        logger.info(f"Generated response (tokens used: {tokens_used})")

        # Return the response
        return response


# Example usage of the ExampleLLM class
async def example_usage():
    llm = ExampleLLM()
    response = await llm.generate("What is the meaning of life?", system_prompt="Answer the question concisely.", stream=False)
    logger.info(f"Generated text: {response.text}")


# If you're running this script directly, you can call the example_usage function to test it.
if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
