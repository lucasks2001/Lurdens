"""Ponto de entrada: python3 -m lurdens"""

import sys


def run() -> int:
    if "--version" in sys.argv[1:]:
        from . import __version__
        print(f"Lurdens {__version__}")
        return 0
    try:
        import PySide6  # noqa: F401
    except ImportError:
        sys.stderr.write(
            "Lurdens precisa do PySide6 (Qt 6 para Python).\n"
            "No Fedora:  sudo dnf install python3-pyside6\n"
            "Ou reinstale com:  ./install.sh --venv\n")
        return 2
    from .qt.app import main
    return main()


if __name__ == "__main__":
    sys.exit(run())
