# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------

import logging          # Python logging framework for structured observability
import asyncio          # Async runtime support for agent execution

# ---------------------------------------------------------------------------
# OSSS / OSSS framework imports
# ---------------------------------------------------------------------------

# Centralized logging setup (formats, levels, handlers, etc.)
from OSSS.ai.config.logging_config import setup_logging

# The agent being executed in isolation
from OSSS.ai.agents.historian.agent import HistorianAgent

# Shared execution context used by all OSSS agents
from OSSS.ai.context import AgentContext


# ---------------------------------------------------------------------------
# Logging initialization
# ---------------------------------------------------------------------------

# Initialize logging as early as possible so all logs are consistently formatted
setup_logging()

# Module-level logger for this runner
logger = logging.getLogger(__name__)


async def run_historian(query: str) -> str:
    """
    Execute the HistorianAgent asynchronously for a single query.

    This helper function is designed to:
    - Run HistorianAgent in isolation
    - Support CLI and programmatic usage
    - Provide clear logging and trace visibility

    Parameters
    ----------
    query : str
        The input query string to be processed by the HistorianAgent.

    Returns
    -------
    str
        The output string produced by the HistorianAgent,
        or a fallback message if no output was generated.
    """

    # -----------------------------------------------------------------------
    # Instantiate agent and execution context
    # -----------------------------------------------------------------------

    # Create a new instance of HistorianAgent
    # (LLM selection and configuration are handled internally)
    agent = HistorianAgent()

    # Create a fresh AgentContext for this execution
    # The context carries:
    # - the original query
    # - agent outputs
    # - execution traces
    # - token usage metadata
    context = AgentContext(query=query)

    # Log the start of agent execution
    logger.info(f"[{agent.name}] Running agent with query: {query}")

    # -----------------------------------------------------------------------
    # Execute the agent
    # -----------------------------------------------------------------------

    # Agent execution mutates the context in-place
    await agent.run(context)

    # -----------------------------------------------------------------------
    # Extract and log agent output
    # -----------------------------------------------------------------------

    # Retrieve output registered under the agent's name
    output = context.get_output(agent.name)

    # Log the final output at INFO level
    logger.info(f"[{agent.name}] Output: {output}")

    # Emit detailed execution trace at DEBUG level for troubleshooting
    logger.debug(
        f"[{agent.name}] Trace: {context.agent_trace.get(agent.name, [])}"
    )

    # Defensive fallback if agent did not produce output
    return output or "[No output]"


# ---------------------------------------------------------------------------
# Command-line entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    """
    CLI entrypoint for running the HistorianAgent interactively.

    This block:
    - Prompts the user for a query
    - Executes the HistorianAgent asynchronously
    - Prints the result to stdout

    The `pragma: no cover` marker excludes this interactive path
    from automated test coverage.
    """

    # Prompt user for input
    query = input("Enter a query: ").strip()

    # Run the async agent pipeline using asyncio.run
    output = asyncio.run(run_historian(query))

    # Print the historian's response with a friendly label
    print("\n🕵️ Historian Output:\n", output)
