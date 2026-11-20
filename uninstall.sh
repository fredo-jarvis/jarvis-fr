#!/usr/bin/env bash
# Désinstallation de Jarvis FR (Linux) : retire le lanceur GNOME et son icône.
# Ne supprime JAMAIS les données (config/, memory/, modeles/, uploads/, cerveau-modele/, journaux,
# ~/.local/state/jarvis-fr/), ni uv, ni Ollama, ni les modèles, ni le dépôt lui-même.
#
# Options : --oui (confirmer le retrait du lanceur), --supprimer-venv (supprime aussi .venv), --aide
set -euo pipefail

DEPOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
APP_ID="io.github.fredo_jarvis.JarvisFR"   # identique à install.sh
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
DESKTOP="$DATA_HOME/applications/$APP_ID.desktop"
ICONE="$DATA_HOME/icons/hicolor/256x256/apps/$APP_ID.png"

OUI=0
VENV=0
for arg in "$@"; do
    case "$arg" in
        --oui) OUI=1 ;;
        --supprimer-venv) VENV=1 ;;
        --aide|-h|--help)
            sed -n '2,6p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "Option inconnue : $arg (voir --aide)" >&2; exit 2 ;;
    esac
done

confirmer() {
    [ "$OUI" -eq 1 ] && return 0
    [ -t 0 ] || { echo "  Pas de terminal interactif : « $1 » ignoré." >&2; return 1; }
    local rep
    read -r -p "  $1 [o/N] " rep
    [[ "$rep" =~ ^([oO]|[oO][uU][iI]|[yY])$ ]]
}

echo "==> Lanceur GNOME"
PROPRE=1
if [ -f "$DESKTOP" ]; then
    if grep -q '^X-Jarvis-FR-Installateur=true' "$DESKTOP"; then
        if confirmer "Supprimer $DESKTOP ?"; then
            rm -f "$DESKTOP"
            echo "  [ok] Lanceur supprimé"
        fi
    else
        PROPRE=0
        echo "  $DESKTOP n'a pas été créé par install.sh : conservé (supprime-le à la main si nécessaire)."
    fi
else
    echo "  Aucun lanceur installé."
fi
if [ "$PROPRE" -eq 1 ] && [ -f "$ICONE" ] && confirmer "Supprimer l'icône $ICONE ?"; then
    rm -f "$ICONE"
    echo "  [ok] Icône supprimée"
fi
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$(dirname "$DESKTOP")" 2>/dev/null || true

echo "==> Environnement virtuel"
if [ ! -d "$DEPOT/.venv" ]; then
    echo "  Aucun .venv."
elif [ "$VENV" -eq 1 ] || { [ "$OUI" -eq 0 ] && confirmer "Supprimer $DEPOT/.venv (réinstallable avec install.sh) ?"; }; then
    rm -rf "${DEPOT:?}/.venv"
    echo "  [ok] .venv supprimé"
else
    echo "  .venv conservé."
fi

echo "==> Données conservées : config/, memory/, modeles/, uploads/, cerveau-modele/, journaux, ~/.local/state/jarvis-fr/"
echo "    uv, Ollama et les modèles ne sont pas touchés."
