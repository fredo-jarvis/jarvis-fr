#!/usr/bin/env bash
# Lanceur Linux de Jarvis FR (terminal ou menu GNOME).
set -eu

DEPOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PY="$DEPOT/.venv/bin/python"

if [ ! -x "$PY" ]; then
    msg="Jarvis FR n'est pas installé : lance ./install.sh dans $DEPOT"
    echo "$msg" >&2
    command -v notify-send >/dev/null 2>&1 && notify-send "Jarvis FR" "$msg" || true
    exit 1
fi

cd "$DEPOT"
exec "$PY" main.py "$@"
