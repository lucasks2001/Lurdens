"""Reconhecimento de "Ludens" (Bring Me The Horizon) para o easter egg.

Regras (todas obrigatórias): título normalizado == "ludens", algum artista
reconhecido como Bring Me The Horizon e reprodução ativa. O álbum é apenas
complementar: identifica a edição para diagnóstico, nunca ativa sozinho.
"""

from __future__ import annotations

import re
import unicodedata

from .state import PlayerState

ARTIST_ALIASES = {"bring me the horizon", "bmth"}
TITLE = "ludens"

# Edições conhecidas (comparação normalizada).
EDITIONS = {
    "death stranding timefall": "Death Stranding: Timefall",
    "post human survival horror": "POST HUMAN: SURVIVAL HORROR",
}

# Sufixos de apresentação aceitos ("Ludens - 2020", "Ludens (From Death Stranding…)").
# Versões que mudam a música (remix, ao vivo, acústica, cover…) NÃO ativam.
_REJECT_QUALIFIERS = re.compile(r"\b(remix|mix|live|ao vivo|acoustic|ac[uú]stic[ao]|cover|instrumental|"
                                r"karaoke|sped up|slowed|nightcore|reprise|demo)\b")
_QUALIFIER = re.compile(r"\s*(\(.*?\)|\[.*?\]|\s[-–—]\s.*)$")


def normalize(text: str) -> str:
    """Minúsculas, sem acentos, pontuação vira espaço, espaços colapsados."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", str(text))
    t = "".join(c for c in t if not unicodedata.combining(c)).casefold()
    t = t.replace("&", " and ")
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def title_matches(title: str) -> bool:
    raw = (title or "").strip()
    if not raw:
        return False
    base = raw
    while True:
        m = _QUALIFIER.search(base)
        if not m or m.start() == 0:
            break
        if _REJECT_QUALIFIERS.search(m.group(0).casefold()):
            return False
        base = base[:m.start()]
    return normalize(base) == TITLE


def artist_matches(artists) -> bool:
    for a in artists or ():
        # um campo pode trazer vários nomes: "Bring Me The Horizon, Fulano"
        for part in re.split(r"\s*(?:,|;|/| feat\.? | ft\.? | x )\s*", str(a), flags=re.IGNORECASE):
            if normalize(part) in ARTIST_ALIASES:
                return True
    return False


def edition(album: str) -> str:
    n = normalize(album)
    for key, label in EDITIONS.items():
        if key in n:
            return label
    return ""


def is_ludens(state: PlayerState) -> bool:
    """A faixa é Ludens/BMTH (independe de estar tocando)."""
    return state.connected and title_matches(state.title) and artist_matches(state.artists)


class EasterWatcher:
    """Converte o fluxo de estados no modo do fundo: "off" | "playing" | "paused".

    - Metadados incompletos (título vazio durante a troca de faixa) mantêm o
      modo anterior até chegar uma atualização válida.
    - O resultado só muda quando o modo realmente muda (sem piscar).
    - Nada é persistido: ao abrir o app, o modo depende só da faixa atual.
    """

    def __init__(self):
        self.mode = "off"
        self.edition = ""

    def update(self, state: PlayerState) -> bool:
        """Retorna True se o modo mudou."""
        if not state.connected:
            new = "off"
        elif state.has_track and not state.title:
            return False                     # metadados incompletos: espera
        elif is_ludens(state):
            new = "playing" if state.playing else "paused"
        else:
            new = "off"
        self.edition = edition(state.album) if new != "off" else ""
        if new == self.mode:
            return False
        self.mode = new
        return True
