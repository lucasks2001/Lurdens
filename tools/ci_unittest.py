"""Roda os testes como `python -m unittest discover -s tests -v` e anota falhas na CI.

No GitHub Actions, cada falha ou erro vira uma anotação (::error::) com o
traceback, visível no resumo da execução e na aba "Files changed" do PR sem
precisar abrir o log completo. Fora da CI, a saída é a mesma do unittest.
"""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _escape(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main() -> int:
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        for kind, items in (("FALHA", result.failures), ("ERRO", result.errors)):
            for test, tb in items:
                tail = "\n".join(tb.strip().splitlines()[-25:])
                print(f"::error title={kind} {test.id()}::{_escape(tail)}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
