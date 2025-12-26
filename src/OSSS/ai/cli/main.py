"""
CLI module entry point for `python -m OSSS.ai.cli` execution.

This module allows the CLI to be executed via `python -m OSSS.ai.cli main`
which is used by the Makefile for the `make run` command.
"""

import sys
from . import app

if __name__ == "__main__":
    # If called with arguments, pass them to the CLI app
    # This allows `python -m OSSS.ai.cli main "query" --agents refiner,critic`
    app()