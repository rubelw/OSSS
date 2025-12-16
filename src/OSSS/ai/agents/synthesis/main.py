# ---------------------------------------------------------------------------
# Core OSSS framework imports
# ---------------------------------------------------------------------------

from OSSS.ai.context import AgentContext  # Shared execution context for agents

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------

import logging          # Structured logging for observability
import asyncio          # Async runtime support

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

from OSSS.ai.config.logging_config import setup_logging


async def run_synthesis(query: str) -> str:
    """
    Execute the SynthesisAgent asynchronously for a single query.

    This helper function is intentionally minimal and designed for:
    - CLI usage
    - Smoke testing the SynthesisAgent in isolation
    - Programmatic invocation from notebooks or scripts

    Parameters
    ----------
    query : str
        The input query to be synthesized.

    Returns
    -------
    str
        The synthesis output produced by the SynthesisAgent,
        or a fallback message if no output was generated.
    """

    # -----------------------------------------------------------------------
    # Deferred import to avoid unnecessary agent loading at module import time
    # -----------------------------------------------------------------------
    # This pattern:
    # - Reduces startup overhead
    # - Avoids circular import issues
    # - Keeps the module lightweight when imported elsewhere
    from OSSS.ai.agents.synthesis.agent import SynthesisAgent

    # -----------------------------------------------------------------------
    # Create the shared execution context
    # -----------------------------------------------------------------------
    # AgentContext carries:
    # - the original query
    # - agent outputs
    # - token usage
    # - execution traces
    context = AgentContext(query=query)

    # Instantiate the SynthesisAgent
    # (no explicit LLM injection here; defaults are resolved internally)
    agent = SynthesisAgent()

    # -----------------------------------------------------------------------
    # Execute the agent
    # -----------------------------------------------------------------------
    # The agent mutates the context in-place
    await agent.run(context)

    # Retrieve output by agent name
    # This relies on the agent registering its output under "Synthesis"
    return context.get_output("Synthesis") or "[No output]"


# ---------------------------------------------------------------------------
# Command-line entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    """
    Entry point for running the SynthesisAgent from the command line.

    This block:
    - Configures logging
    - Prompts the user for a query
    - Executes the SynthesisAgent asynchronously
    - Logs both input and output for traceability
    - Prints the final synthesis result to stdout

    The `pragma: no cover` comment excludes this block from test coverage,
    as it is intended solely for interactive / CLI execution.
    """

    # Initialize logging before any other operations
    setup_logging()

    # Prompt the user for input
    query = input("Enter a query: ").strip()

    # Log the received query for auditability
    logging.info(f"[SynthesisAgent] Received user query: {query}")

    # Execute the async synthesis pipeline using asyncio.run
    output = asyncio.run(run_synthesis(query))

    # Log the final synthesized output
    logging.info(f"[SynthesisAgent] Synthesis output: {output}")

    # Print the result to the console with a friendly header
    print("\n🔗 Synthesis Output:\n", output)
