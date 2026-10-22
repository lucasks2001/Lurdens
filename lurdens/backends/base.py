"""Contrato comum dos backends que conversam com o Spotify.

Cada sistema tem um jeito diferente de enxergar e controlar o Spotify:

- Linux: MPRIS pelo D-Bus de sessão (``lurdens.mpris``), orientado a sinais;
- Windows: controles de mídia do sistema (SMTC);
- macOS: dicionário AppleScript do próprio Spotify.

A interface (Qt/QML), o histórico, as notificações e o temporizador só
conhecem este contrato e o ``PlayerState`` imutável que ele publica pelo
callback ``on_state``. Nenhum método bloqueia: comandos entram numa fila e
são executados na thread do backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from ..state import PlayerState

StateCallback = Callable[[PlayerState], None]


class PlayerBackend(ABC):
    #: identificador estável ("mpris", "smtc", "applescript"…)
    kind: str = ""
    #: nome legível, mostrado em Configurações › Sistema e no diagnóstico
    label: str = ""
    #: ordem do ciclo de repetição suportada pelo backend
    loop_modes: tuple[str, ...] = ("None", "Playlist", "Track")

    last_error: str = ""

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self, timeout: float = 2.0) -> None: ...

    @property
    @abstractmethod
    def state(self) -> PlayerState: ...

    # ------------------------------------------------------------ comandos
    @abstractmethod
    def play_pause(self) -> None: ...

    @abstractmethod
    def pause(self) -> None:
        """Pausa sem alternar (usado pelo temporizador para dormir)."""

    @abstractmethod
    def next(self) -> None: ...

    @abstractmethod
    def previous(self) -> None: ...

    @abstractmethod
    def seek_to(self, position_us: int) -> None: ...

    @abstractmethod
    def seek_by(self, offset_us: int) -> None: ...

    @abstractmethod
    def set_volume(self, volume: float) -> None:
        """Volume de 0.0 a 1.0; ignorado se ``state.volume`` for None."""

    @abstractmethod
    def toggle_shuffle(self) -> None: ...

    @abstractmethod
    def cycle_loop(self) -> None: ...

    @abstractmethod
    def raise_player(self) -> None:
        """Traz a janela do Spotify para frente, se o sistema permitir."""

    @abstractmethod
    def refresh(self) -> None:
        """Procura o Spotify de novo e recarrega o estado completo."""


def next_loop_mode(current: str | None, modes: tuple[str, ...]) -> str:
    """Próximo modo de repetição dentro dos modos que o backend suporta."""
    if current not in modes:
        return modes[1] if len(modes) > 1 else modes[0]
    return modes[(modes.index(current) + 1) % len(modes)]
