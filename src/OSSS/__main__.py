# osss_cli/__main__.py
import sys
import typer

from .menu_engine import menu  # your JSON-driven menu
app = typer.Typer(help="OSSS CLI")

@app.command("menu")
def menu_cmd():
    """Open the interactive menu."""
    menu()

def _main():
    # Run interactive menu if no args; otherwise run subcommands (incl. `menu`)
    if len(sys.argv) == 1:
        menu()
    else:
        app()

if __name__ == "__main__":
    _main()
