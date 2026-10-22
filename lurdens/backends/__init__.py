"""Backends de reprodução por sistema operacional.

``create_backend`` escolhe a implementação do sistema atual. Os módulos de
cada sistema são importados só quando usados, para que dependências
específicas (por exemplo, o pacote ``winrt`` no Windows) não sejam exigidas
nos demais.
"""

from __future__ import annotations

import sys

from .base import PlayerBackend, StateCallback, next_loop_mode

__all__ = ["PlayerBackend", "StateCallback", "create_backend", "current_os", "next_loop_mode"]


def current_os(platform: str | None = None) -> str:
    """"linux", "windows", "macos" ou "other"."""
    p = platform or sys.platform
    if p.startswith("linux") or p.startswith("freebsd"):
        return "linux"
    if p in ("win32", "cygwin"):
        return "windows"
    if p == "darwin":
        return "macos"
    return "other"


def create_backend(on_state: StateCallback, *, platform: str | None = None,
                   address: str | None = None) -> PlayerBackend:
    """Backend do sistema atual.

    ``address`` só vale para o MPRIS (endereço de um barramento D-Bus de
    teste); os demais backends o ignoram.
    """
    os_name = current_os(platform)
    if os_name == "windows":
        from .smtc import SmtcBackend
        return SmtcBackend(on_state)
    # O backend do macOS entra no próximo passo; até lá, os demais sistemas
    # usam o MPRIS, que apenas fica "sem barramento" fora do Linux.
    from ..mpris import MprisClient
    return MprisClient(on_state, address=address)
