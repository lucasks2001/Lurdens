#!/usr/bin/env bash
# Instala o Lurdens para o usuário atual (sem sudo).
#
#   ./install.sh          usa o PySide6 do sistema (recomendado: sudo dnf install python3-pyside6)
#   ./install.sh --venv   cria um ambiente virtual isolado e instala o PySide6 do PyPI nele
#   ./install.sh --rollback  volta para a versão instalada antes desta (guardada em app.previous)
#
# Arquivos instalados:
#   ~/.local/share/lurdens/app/            código
#   ~/.local/share/lurdens/venv/           (só com --venv)
#   ~/.local/bin/lurdens                   lançador
#   ~/.local/share/applications/lurdens.desktop
#   ~/.local/share/icons/hicolor/*/apps/lurdens.{png,svg}
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
PREFIX="$DATA/lurdens"
BIN="$HOME/.local/bin"
APPS="$DATA/applications"
ICONS="$DATA/icons/hicolor"
USE_VENV=0
ROLLBACK=0

for arg in "$@"; do
  case "$arg" in
    --venv) USE_VENV=1 ;;
    --rollback) ROLLBACK=1 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "Opção desconhecida: $arg" >&2; exit 2 ;;
  esac
done

say() { printf '\033[1m▸ %s\033[0m\n' "$*"; }

app_version() {  # versão de uma cópia instalada
  sed -n 's/^__version__ = "\(.*\)"/\1/p' "$1/lurdens/__init__.py" 2>/dev/null
}

if [[ $ROLLBACK -eq 1 ]]; then
  if [[ ! -d "$PREFIX/app.previous" ]]; then
    echo "Não há versão anterior guardada em $PREFIX/app.previous." >&2
    exit 1
  fi
  say "Revertendo de $(app_version "$PREFIX/app" || echo '?') para $(app_version "$PREFIX/app.previous")"
  rm -rf "$PREFIX/app.swap"
  mv "$PREFIX/app" "$PREFIX/app.swap"
  mv "$PREFIX/app.previous" "$PREFIX/app"
  mv "$PREFIX/app.swap" "$PREFIX/app.previous"
  echo "Pronto. Reabra o Lurdens. (Rode --rollback de novo para desfazer.)"
  exit 0
fi

command -v python3 >/dev/null || { echo "python3 não encontrado. Instale com: sudo dnf install python3" >&2; exit 1; }

check_pyside() {
  "$1" - <<'PY'
import sys
try:
    import PySide6
    from PySide6 import QtQml, QtQuick, QtQuickControls2, QtNetwork, QtWidgets  # noqa: F401
except Exception as exc:
    print(f"  PySide6 indisponível: {exc}")
    sys.exit(1)
print(f"  PySide6 {PySide6.__version__} encontrado")
PY
}

if [[ $USE_VENV -eq 1 ]]; then
  say "Criando ambiente virtual em $PREFIX/venv"
  python3 -m venv "$PREFIX/venv"
  "$PREFIX/venv/bin/python" -m pip install --upgrade --quiet pip
  "$PREFIX/venv/bin/python" -m pip install --quiet -r "$SRC/requirements.txt"
  PY="$PREFIX/venv/bin/python"
else
  PY="$(command -v python3)"
fi

say "Verificando dependências"
if ! check_pyside "$PY"; then
  cat >&2 <<'MSG'

O PySide6 (Qt 6 para Python) não está instalado. Escolha uma opção:
  1) pacote do Fedora (recomendado):  sudo dnf install python3-pyside6
  2) ambiente virtual isolado:        ./install.sh --venv
MSG
  exit 1
fi

say "Copiando o aplicativo para $PREFIX/app"
rm -rf "$PREFIX/app.new"
mkdir -p "$PREFIX/app.new"
cp -r "$SRC/lurdens" "$PREFIX/app.new/"
find "$PREFIX/app.new" -name '__pycache__' -type d -prune -exec rm -rf {} +
if [[ -d "$PREFIX/app" ]]; then
  OLD="$(app_version "$PREFIX/app")"
  NEW="$(app_version "$PREFIX/app.new")"
  if [[ "$OLD" != "$NEW" ]]; then
    rm -rf "$PREFIX/app.previous"
    mv "$PREFIX/app" "$PREFIX/app.previous"
    echo "  versão anterior ($OLD) guardada; para voltar: ./install.sh --rollback"
  else
    rm -rf "$PREFIX/app"
  fi
fi
mv "$PREFIX/app.new" "$PREFIX/app"

say "Criando o lançador $BIN/lurdens"
mkdir -p "$BIN"
cat > "$BIN/lurdens" <<EOF
#!/bin/sh
# Lançador do Lurdens (gerado por install.sh)
export PYTHONPATH="$PREFIX/app\${PYTHONPATH:+:\$PYTHONPATH}"
export LURDENS_LAUNCHER="$BIN/lurdens"
exec "$PY" -P -m lurdens "\$@"
EOF
chmod +x "$BIN/lurdens"

say "Instalando ícones"
for s in 16 22 24 32 48 64 128 256 512; do
  install -Dm644 "$SRC/lurdens/resources/icons/lurdens-$s.png" "$ICONS/${s}x${s}/apps/lurdens.png"
done
install -Dm644 "$SRC/lurdens/resources/icons/lurdens.svg" "$ICONS/scalable/apps/lurdens.svg"

say "Registrando no menu de aplicativos"
mkdir -p "$APPS"
sed "s|@EXEC@|$BIN/lurdens|g" "$SRC/packaging/lurdens.desktop.in" > "$APPS/lurdens.desktop"
chmod 644 "$APPS/lurdens.desktop"

command -v update-desktop-database >/dev/null && update-desktop-database -q "$APPS" || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t "$ICONS" 2>/dev/null || true
for k in kbuildsycoca6 kbuildsycoca5; do
  if command -v "$k" >/dev/null; then "$k" --noincremental >/dev/null 2>&1 || true; break; fi
done

# inicialização automática já ativada: reescreve com o lançador atual
if [[ -f "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/lurdens.desktop" ]]; then
  sed -i "s|^Exec=.*|Exec=$BIN/lurdens --autostart|" "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/lurdens.desktop"
fi

if command -v fc-list >/dev/null && ! fc-list 2>/dev/null | grep -qi "JetBrains Mono"; then
  echo "Dica: a fonte JetBrains Mono não está instalada (o Lurdens usa outra monoespaçada)."
  echo "      Instale com: sudo dnf install jetbrains-mono-fonts-all"
fi

case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "Aviso: $BIN não está no PATH; use o menu de aplicativos ou $BIN/lurdens." ;;
esac

say "Pronto! Abra \"Lurdens\" pelo menu do KDE ou rode: lurdens"
echo "  Verificar a interface sem abrir janela:  lurdens --selftest"
