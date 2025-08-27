# OSSS/__main__.py
# ================================================================================================
# Entry point for the OSSS CLI (Command Line Interface).
#
# This file defines how the OSSS application behaves when executed directly via:
#   python -m OSSS
# or when installed as a package with an entrypoint (console script).
#
# It uses `typer` to build a friendly CLI with subcommands, while still supporting an
# interactive menu-driven mode if the user launches it without arguments.
#
# Key responsibilities:
#   • Wire up the Typer CLI app and commands
#   • Expose the JSON-driven interactive menu (`menu_engine.menu`)
#   • Decide between running interactive mode vs. subcommands based on sys.argv
# ================================================================================================

import sys
import typer

# Import the menu function that powers the JSON-driven interactive interface.
# This is where OSSS likely presents a structured, guided CLI menu instead of raw commands.
from .menu_engine import menu

# --------------------------------------------------------------------------------
# Create the Typer application instance.
#
# - `Typer` is similar to Click, but provides better developer ergonomics and type hints.
# - We give the app a descriptive help message so that `--help` shows context.
# --------------------------------------------------------------------------------
app = typer.Typer(help="OSSS CLI")

# --------------------------------------------------------------------------------
# Define a Typer command called `menu`.
#
# Usage:
#   osss menu
#
# Purpose:
#   - Provides a way to explicitly launch the interactive JSON-driven menu.
#   - This can be useful when OSSS is run with subcommands but the user wants to
#     force the menu-driven UX.
# ----------
