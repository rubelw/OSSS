# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------

import asyncio        # Async runtime support for agent execution
import argparse       # Command-line argument parsing
import sys            # System exit handling and I/O
from typing import Optional, Dict, Any

# ---------------------------------------------------------------------------
# OSSS / OSSS framework imports
# ---------------------------------------------------------------------------

# Centralized logging configuration (JSON / structured logging, levels, etc.)
from OSSS.ai.config.logging_config import setup_logging

# The agent under test: RefinerAgent
from OSSS.ai.agents.refiner.agent import RefinerAgent

# Shared execution context passed between agents
from OSSS.ai.context import AgentContext

# Factory responsible for selecting and constructing an LLM implementation
# (respects environment variables like OSSS_LLM)
from OSSS.ai.llm.factory import LLMFactory

# Configuration helper for OpenAI-backed LLMs (used for debug metadata)
from OSSS.ai.config.openai_config import OpenAIConfig


# ---------------------------------------------------------------------------
# Initialize logging as early as possible
# ---------------------------------------------------------------------------

# This ensures all logs (including from imports) use the configured format
setup_logging()


async def run_refiner(
    query: str,
    debug: bool = False,
) -> tuple[str, Optional[Dict[str, Any]]]:
    """
    Run the RefinerAgent asynchronously with the given query.

    This function exists primarily to:
    - Allow RefinerAgent to be run in isolation
    - Support CLI and programmatic usage
    - Provide optional debug metadata without polluting AgentContext

    Parameters
    ----------
    query : str
        The input query to refine.
    debug : bool, optional
        Whether to collect and return debug information.

    Returns
    -------
    tuple[str, Optional[Dict[str, Any]]]
        - Refined output string produced by RefinerAgent
        - Optional debug metadata dictionary (None if debug=False)
    """

    # -----------------------------------------------------------------------
    # Create an LLM instance using the factory
    # -----------------------------------------------------------------------
    # The factory abstracts:
    # - OpenAI vs local vs stub LLMs
    # - Environment-based configuration
    # - Test-friendly injection
    llm = LLMFactory.create()

    # Optional debug metadata container
    debug_info = None

    if debug:
        # Attempt to determine which model is in use
        # This is best-effort only and should never break execution
        try:
            llm_config = OpenAIConfig.load()
            model_name = llm_config.model
        except Exception:
            # Fallback paths for non-OpenAI or stub LLMs
            model_name = "stub-llm" if hasattr(llm, "model_name") else "unknown"

        # Populate initial debug metadata
        debug_info = {
            "model": model_name,
            "original_query": query,
            "system_prompt_used": True,
        }

    # -----------------------------------------------------------------------
    # Instantiate agent and execution context
    # -----------------------------------------------------------------------

    # Create RefinerAgent with the selected LLM
    agent = RefinerAgent(llm=llm)

    # AgentContext carries query, agent outputs, token usage, and trace data
    context = AgentContext(query=query)

    # Optional CLI debug output
    if debug:
        print(f"[DEBUG] Input query: '{query}'")
        # debug_info is guaranteed to exist when debug=True
        assert debug_info is not None
        print(f"[DEBUG] Model: {debug_info['model']}")
        print("[DEBUG] Running RefinerAgent...")

    # -----------------------------------------------------------------------
    # Execute the agent
    # -----------------------------------------------------------------------

    # Agents mutate the context in-place
    await agent.run(context)

    # Retrieve agent output by agent name
    output = context.get_output(agent.name)

    # Defensive fallback in case no output was produced
    refined_output = output or "[No output]"

    # -----------------------------------------------------------------------
    # Debug metadata extraction and logging
    # -----------------------------------------------------------------------

    if debug and output:
        # Normalize refined output for debug readability
        if output.startswith("Refined query: "):
            # Strip known prefix for clean display
            actual_refinement = output[15:]
        elif output.startswith("[Unchanged] "):
            # Preserve unchanged marker
            actual_refinement = output
        else:
            actual_refinement = output

        # debug_info is guaranteed to exist when debug=True
        assert debug_info is not None

        debug_info.update(
            {
                "raw_output": output,
                "refined_query": actual_refinement,
                # Token usage is tracked in AgentContext but not surfaced here yet
                "tokens_used": (
                    "Available in LLM response "
                    "(not captured in current implementation)"
                ),
            }
        )

        print(f"[DEBUG] Raw agent output: {output}")
        print("[DEBUG] Processing complete")

    return refined_output, debug_info


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for the RefinerAgent CLI.

    Returns
    -------
    argparse.Namespace
        Parsed arguments with attributes:
        - query
        - debug
    """
    parser = argparse.ArgumentParser(
        description=(
            "Run RefinerAgent in isolation for prompt testing and experimentation"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  poetry run python -m OSSS.ai.agents.refiner.main --query "What is cognition?"
  poetry run python -m OSSS.ai.agents.refiner.main --query "AI and society" --debug
  poetry run python -m OSSS.ai.agents.refiner.main  # Interactive mode
        """.strip(),
    )

    # Optional query argument (enables non-interactive usage)
    parser.add_argument(
        "--query",
        "-q",
        type=str,
        help="Query to refine. If not provided, enters interactive mode.",
    )

    # Debug flag enables verbose logging and metadata output
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug mode to show detailed processing information",
    )

    return parser.parse_args()


async def main() -> None:
    """
    Main CLI entrypoint.

    Responsibilities:
    - Parse arguments
    - Collect query (CLI or interactive)
    - Run RefinerAgent
    - Display results
    - Handle errors cleanly
    """
    args = parse_args()

    # -----------------------------------------------------------------------
    # Determine query source
    # -----------------------------------------------------------------------

    if args.query:
        # Query provided via CLI argument
        query = args.query.strip()
    else:
        # Interactive prompt mode
        try:
            query = input("Enter a query: ").strip()
        except (KeyboardInterrupt, EOFError):
            # Graceful exit for Ctrl+C / Ctrl+D
            print("\nExiting...")
            sys.exit(0)

    # Validate query
    if not query:
        print("❌ Error: No query provided")
        sys.exit(1)

    try:
        # -------------------------------------------------------------------
        # Run the RefinerAgent
        # -------------------------------------------------------------------

        output, debug_info = await run_refiner(
            query,
            debug=args.debug,
        )

        # Spacing after debug logs
        if args.debug:
            print()

        # -------------------------------------------------------------------
        # Display refined output
        # -------------------------------------------------------------------

        print("🧠 Refiner Output:")
        print()

        # Clean up known output prefixes for user display
        if output.startswith("Refined query: "):
            clean_output = output[15:]
        else:
            clean_output = output

        print(clean_output)

    except KeyboardInterrupt:
        print("\n❌ Interrupted by user")
        sys.exit(1)

    except Exception as e:
        # Catch-all to ensure CLI never crashes silently
        print(f"❌ Error: {e}")

        if args.debug:
            # Full traceback only in debug mode
            import traceback

            traceback.print_exc()

        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI bootstrap
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    # asyncio.run handles event loop creation and teardown
    asyncio.run(main())
