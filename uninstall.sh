#!/usr/bin/env bash
# Remove o Lurdens instalado por install.sh.
#   ./uninstall.sh            mantém suas configurações (~/.config/lurdens)
#   ./uninstall.sh --purge    remove também as configurações
set -euo pipefail

DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
CONF="${XDG_CONFIG_HOME:-$HOME/.config}/lurdens"
ICONS="$DATA/icons/hicolor"


rm -rf "$DATA/lurdens"
rm -f "$HOME/.local/bin/lurdens" "$DATA/applications/lurdens.desktop"
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/lurdens.desktop"
for s in 16 22 24 32 48 64 128 256 512; do
  rm -f "$ICONS/${s}x${s}/apps/lurdens.png"
done
rm -f "$ICONS/scalable/apps/lurdens.svg"

if [[ "${1:-}" == "--purge" ]]; then
  rm -rf "$CONF" "${XDG_STATE_HOME:-$HOME/.local/state}/lurdens" "${XDG_CACHE_HOME:-$HOME/.cache}/lurdens"
  echo "Configurações, histórico salvo, tempo de uso e cache de capas removidos."
else
  echo "Configurações mantidas em $CONF (use --purge para apagar)."
fi

command -v update-desktop-database >/dev/null && update-desktop-database -q "$DATA/applications" || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t "$ICONS" 2>/dev/null || true
for k in kbuildsycoca6 kbuildsycoca5; do
  if command -v "$k" >/dev/null; then "$k" --noincremental >/dev/null 2>&1 || true; break; fi
done
echo "Lurdens desinstalado."
