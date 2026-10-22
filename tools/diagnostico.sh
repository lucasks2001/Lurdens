#!/usr/bin/env bash
# Diagnóstico do Lurdens: dependências, sessão, Spotify no D-Bus e autoteste da interface.
# Uso: tools/diagnostico.sh [PASTA_DAS_CAPTURAS]   (rode a partir da pasta do projeto)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${LURDENS_PYTHON:-python3}"
[[ -x "$HERE/.venv/bin/python" ]] && PY="$HERE/.venv/bin/python"
[[ -x "${XDG_DATA_HOME:-$HOME/.local/share}/lurdens/venv/bin/python" ]] && PY="${XDG_DATA_HOME:-$HOME/.local/share}/lurdens/venv/bin/python"

ok()   { printf '  \033[32m✔\033[0m %s\n' "$*"; }
bad()  { printf '  \033[31m✘\033[0m %s\n' "$*"; }
info() { printf '  · %s\n' "$*"; }

echo "== Sistema"
info "$(. /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-desconhecido}")"
info "Sessão: ${XDG_SESSION_TYPE:-?} / ${XDG_CURRENT_DESKTOP:-?}"
command -v plasmashell >/dev/null && info "$(plasmashell --version 2>/dev/null)"

echo "== Python e Qt"
if "$PY" -c 'import sys; print(sys.version.split()[0])' >/dev/null 2>&1; then ok "Python $("$PY" -c 'import sys; print(sys.version.split()[0])') ($PY)"; else bad "python3 não encontrado"; fi
if out=$("$PY" -c 'import PySide6; from PySide6.QtCore import qVersion; from PySide6 import QtQuick, QtQuickControls2; print(PySide6.__version__, qVersion())' 2>&1); then
  ok "PySide6 / Qt: $out"
else
  bad "PySide6 indisponível → sudo dnf install python3-pyside6   ($out)"
fi

echo "== Spotify"
command -v spotify >/dev/null && ok "binário: $(command -v spotify)" || info "binário 'spotify' não está no PATH"
if command -v flatpak >/dev/null && flatpak info com.spotify.Client >/dev/null 2>&1; then ok "Flatpak com.spotify.Client instalado"; else info "Flatpak do Spotify não instalado"; fi
if command -v busctl >/dev/null; then
  names=$(busctl --user list --no-legend 2>/dev/null | awk '{print $1}' | grep '^org\.mpris\.MediaPlayer2\.' || true)
  if echo "$names" | grep -q 'spotify'; then ok "Spotify publicado no D-Bus: $(echo "$names" | grep spotify | tr '\n' ' ')"
  else info "Spotify não está no D-Bus agora (aberto?). Players MPRIS: ${names:-nenhum}"; fi
  if echo "$names" | grep -q spotify; then
    busctl --user get-property org.mpris.MediaPlayer2.spotify /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player PlaybackStatus 2>/dev/null | sed 's/^/  · status: /'
  fi
fi

echo "== Configurações"
info "${XDG_CONFIG_HOME:-$HOME/.config}/lurdens/settings.json"

echo "== Autoteste da interface (offscreen)"
PYTHONPATH="$HERE${PYTHONPATH:+:$PYTHONPATH}" "$PY" -m lurdens --selftest "${1:-}"
