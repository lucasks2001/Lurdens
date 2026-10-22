"""Ponto de entrada do executável empacotado (PyInstaller)."""

import sys

from lurdens.__main__ import run

if __name__ == "__main__":
    sys.exit(run())
