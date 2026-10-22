"""Temporizador para dormir e contador de tempo de uso (sem Qt, relógios injetáveis)."""

from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import date, datetime
from pathlib import Path


def boottime() -> float:
    """Relógio que continua contando durante a suspensão do computador."""
    try:
        return time.clock_gettime(time.CLOCK_BOOTTIME)
    except (AttributeError, OSError):
        return time.monotonic()


class SleepTimer:
    """Pausa o Spotify após uma duração.

    O tempo é medido por um prazo absoluto no relógio de boot, não por
    contagem de ticks: atrasos da interface ou suspensão não o desregulam.
    Quem usa chama ``poll()`` periodicamente (1 s basta); ``poll`` retorna
    True uma única vez, quando o prazo vence.
    """

    MIN_SECONDS = 60
    MAX_SECONDS = 12 * 3600

    def __init__(self, clock=boottime):
        self._clock = clock
        self.deadline: float | None = None
        self.duration = 0

    @property
    def active(self) -> bool:
        return self.deadline is not None

    def start(self, seconds: int) -> None:
        seconds = int(max(self.MIN_SECONDS, min(self.MAX_SECONDS, seconds)))
        self.duration = seconds
        self.deadline = self._clock() + seconds

    def restart(self) -> None:
        if self.duration:
            self.start(self.duration)

    def extend(self, seconds: int) -> None:
        if self.active:
            remaining = self.remaining() + int(seconds)
            self.duration = max(self.duration, remaining)
            self.deadline = self._clock() + min(self.MAX_SECONDS, max(self.MIN_SECONDS, remaining))

    def cancel(self) -> None:
        self.deadline = None

    def remaining(self) -> int:
        if self.deadline is None:
            return 0
        return max(0, int(round(self.deadline - self._clock())))

    def poll(self) -> bool:
        if self.deadline is not None and self._clock() >= self.deadline:
            self.deadline = None
            return True
        return False


class UsageTracker:
    """Tempo de execução do Lurdens.

    - Sessão: desde que o processo abriu (ou desde "reiniciar contadores"),
      contando também com a janela oculta na bandeja. Usa relógio monotônico:
      períodos com o computador suspenso NÃO contam (o processo não roda).
    - Hoje: soma das sessões no dia local atual, persistida em JSON se o
      registro estiver ativado. Na virada do dia o total recomeça do zero;
      apenas o dia atual é guardado (não há estatística histórica).
    """

    def __init__(self, path: Path | None, persist: bool = True,
                 mono=time.monotonic, now=datetime.now):
        self.path = path
        self.persist = persist
        self._mono = mono
        self._now = now
        self.session_started_at: datetime = now()
        self._session_mono = mono()
        self._last_tick = self._session_mono
        self.today: date = now().date()
        self.today_seconds = 0.0
        self.error = ""
        if persist:
            self._load()

    # ------------------------------------------------------------------
    def session_seconds(self) -> int:
        return int(self._mono() - self._session_mono)

    def today_total(self) -> int:
        self.tick()
        return int(self.today_seconds)

    def tick(self) -> None:
        """Acumula o tempo decorrido desde o último tick no dia corrente."""
        m = self._mono()
        delta = max(0.0, m - self._last_tick)
        self._last_tick = m
        current = self._now().date()
        if current != self.today:
            # virou o dia: o tempo após a meia-noite pertence ao novo dia
            midnight = datetime.combine(current, datetime.min.time())
            after = min(delta, max(0.0, (self._now() - midnight).total_seconds()))
            self.today_seconds += delta - after
            self._save()
            self.today = current
            self.today_seconds = after
        else:
            self.today_seconds += delta

    def reset_session(self) -> None:
        self.tick()
        self.session_started_at = self._now()
        self._session_mono = self._mono()

    def set_persist(self, on: bool) -> None:
        self.tick()
        self.persist = on
        if on:
            self._save()
        elif self.path and self.path.exists():
            try:
                self.path.unlink()
            except OSError as exc:
                self.error = str(exc)

    def flush(self) -> None:
        self.tick()
        self._save()

    # ------------------------------------------------------------------
    def _load(self) -> None:
        if not self.path:
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if raw.get("date") == self.today.isoformat():
                self.today_seconds = max(0.0, min(86400.0, float(raw.get("seconds", 0))))
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            self.error = f"registro de uso ilegível, recomeçando ({exc})"

    def _save(self) -> None:
        if not (self.persist and self.path):
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".usage-", dir=self.path.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"date": self.today.isoformat(), "seconds": round(self.today_seconds)}, fh)
            os.replace(tmp, self.path)
        except OSError as exc:
            self.error = str(exc)


def format_duration(seconds: int, with_seconds: bool = True) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}min" + (f" {s:02d}s" if with_seconds else "")
    if m:
        return f"{m}min {s:02d}s" if with_seconds else f"{m}min"
    return f"{s}s"


def format_clock(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
