#!/usr/bin/env bash
# Installation de Jarvis FR sous Ubuntu / GNOME Wayland. Idempotente : peut être relancée sans risque.
#
# Ne touche jamais aux données (config/, memory/, modeles/, uploads/, cerveau-modele/, journaux,
# ~/.local/state/jarvis-fr/). Ne lit ni ne modifie aucune clé API. Ne télécharge aucun modèle.
#
# Options : --oui (confirmations ordinaires), --sans-apt, --verifier (diagnostic sans rien modifier), --aide
set -euo pipefail

DEPOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
APP_ID="io.github.fredo_jarvis.JarvisFR"   # identique à core/wayland_input.py et core/wayland_shortcuts.py
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
DESKTOP="$DATA_HOME/applications/$APP_ID.desktop"
ICONE="$DATA_HOME/icons/hicolor/256x256/apps/$APP_ID.png"
PY_VERSION="3.13"

# Paquets apt indispensables (audio, Qt, trousseau GNOME, notifications, ouverture d'URL).
APT_REQUIS=(libportaudio2 wireplumber libnotify-bin gnome-keyring libsecret-1-0
            libxcb-cursor0 libxkbcommon0 libegl1 libgl1 xdg-utils)
# Facultatifs : jamais installés automatiquement, seulement signalés.
APT_FACULTATIFS=(ffmpeg gnome-text-editor gnome-calculator nautilus brightnessctl)

OUI=0
SANS_APT=0
VERIFIER=0
AVERTISSEMENTS=0

for arg in "$@"; do
    case "$arg" in
        --oui) OUI=1 ;;
        --sans-apt) SANS_APT=1 ;;
        --verifier) VERIFIER=1 ;;
        --aide|-h|--help)
            sed -n '2,7p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "Option inconnue : $arg (voir --aide)" >&2; exit 2 ;;
    esac
done

info()  { printf '\033[1m==> %s\033[0m\n' "$*"; }
ok()    { printf '  [ok] %s\n' "$*"; }
warn()  { printf '  [!] %s\n' "$*" >&2; AVERTISSEMENTS=$((AVERTISSEMENTS + 1)); }
simule() { printf '  [verifier] %s\n' "$*"; }

# confirmer "question" : oui automatique avec --oui. Jamais utilisée pour les données.
confirmer() {
    [ "$OUI" -eq 1 ] && return 0
    [ -t 0 ] || { warn "Pas de terminal interactif : « $1 » ignoré (relance avec --oui)."; return 1; }
    local rep
    read -r -p "  $1 [o/N] " rep
    [[ "$rep" =~ ^([oO]|[oO][uU][iI]|[yY])$ ]]
}

# confirmer_strict : toujours une réponse explicite, même avec --oui.
confirmer_strict() {
    [ -t 0 ] || { warn "Pas de terminal interactif : « $1 » ignoré."; return 1; }
    local rep
    read -r -p "  $1 [o/N] " rep
    [[ "$rep" =~ ^([oO]|[oO][uU][iI]|[yY])$ ]]
}

cd "$DEPOT"
[ "$(uname -s)" = "Linux" ] || { echo "Ce script est réservé à Linux." >&2; exit 1; }
[ "$(id -u)" -ne 0 ] || { echo "Ne lance pas ce script en root : il installe dans ton profil." >&2; exit 1; }
[ -f main.py ] && [ -f requirements.txt ] || { echo "Lance install.sh depuis le dépôt Jarvis FR." >&2; exit 1; }

[ "$VERIFIER" -eq 1 ] && info "Mode --verifier : aucune modification ne sera faite."

# ── 0. Session ───────────────────────────────────────────────────────────────
info "Session"
if [ "${XDG_SESSION_TYPE:-}" = "wayland" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
    ok "Session Wayland détectée"
else
    warn "Session Wayland non détectée : capture, push-to-talk et frappes passeront par le repli X11 (non testé)."
fi
if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    ok "Système : ${PRETTY_NAME:-inconnu}"
fi

# ── 1. Paquets système ───────────────────────────────────────────────────────
info "Paquets système (apt)"
MANQUANTS=()
for p in "${APT_REQUIS[@]}"; do
    dpkg -s "$p" >/dev/null 2>&1 || MANQUANTS+=("$p")
done
if [ "${#MANQUANTS[@]}" -eq 0 ]; then
    ok "Tous les paquets requis sont installés"
elif [ "$VERIFIER" -eq 1 ]; then
    simule "Paquets manquants : ${MANQUANTS[*]}"
elif [ "$SANS_APT" -eq 1 ]; then
    warn "Paquets manquants (--sans-apt) : ${MANQUANTS[*]}"
    warn "Installation manuelle : sudo apt install ${MANQUANTS[*]}"
else
    echo "  Paquets manquants : ${MANQUANTS[*]}"
    if confirmer "Les installer avec sudo apt ?"; then
        sudo apt-get install -y "${MANQUANTS[@]}"
    else
        warn "Paquets non installés : certaines fonctions pourront échouer (${MANQUANTS[*]})."
    fi
fi
FACULTATIFS_MANQUANTS=()
for p in "${APT_FACULTATIFS[@]}"; do
    dpkg -s "$p" >/dev/null 2>&1 || FACULTATIFS_MANQUANTS+=("$p")
done
[ "${#FACULTATIFS_MANQUANTS[@]}" -eq 0 ] || echo "  Facultatifs absents (non installés par ce script) : ${FACULTATIFS_MANQUANTS[*]}"
command -v google-chrome >/dev/null 2>&1 || command -v chromium >/dev/null 2>&1 \
    || echo "  Aucun Chrome/Chromium détecté : la fenêtre Galaxie se rabattra sur une instance Firefox isolée (sinon sur le navigateur par défaut) ; les autres fonctions de navigateur en application auront besoin de Chrome ou Chromium."

# ── 2. uv ────────────────────────────────────────────────────────────────────
info "uv"
UV="$(command -v uv 2>/dev/null || true)"
if [ -z "$UV" ] && [ -x "$HOME/.local/bin/uv" ]; then
    UV="$HOME/.local/bin/uv"
fi
if [ -n "$UV" ]; then
    ok "uv trouvé : $UV"
elif [ "$VERIFIER" -eq 1 ]; then
    simule "uv absent : il faudrait le télécharger (https://astral.sh/uv/install.sh) dans ~/.local/bin"
else
    echo "  uv est absent. Installation proposée : téléchargement du script officiel https://astral.sh/uv/install.sh,"
    echo "  installation dans ~/.local/bin (sans sudo, uniquement dans ton profil)."
    if confirmer "Télécharger et installer uv ?"; then
        TMP_UV="$(mktemp)"
        curl -LsSf https://astral.sh/uv/install.sh -o "$TMP_UV"
        sh "$TMP_UV"
        rm -f "$TMP_UV"
        UV="$HOME/.local/bin/uv"
        [ -x "$UV" ] || { echo "uv n'a pas pu être installé." >&2; exit 1; }
    else
        echo "uv est nécessaire pour créer l'environnement Python $PY_VERSION. Installation interrompue." >&2
        exit 1
    fi
fi

# ── 3. Environnement virtuel Python 3.13 ─────────────────────────────────────
info "Environnement virtuel (.venv, Python $PY_VERSION)"
VENV_PY="$DEPOT/.venv/bin/python"
if [ -x "$VENV_PY" ]; then
    VERSION_VENV="$("$VENV_PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "?")"
    if [ "$VERSION_VENV" = "$PY_VERSION" ]; then
        ok ".venv existant en Python $VERSION_VENV : conservé"
    else
        echo ".venv existe mais utilise Python $VERSION_VENV (attendu $PY_VERSION)." >&2
        echo "Rien n'est supprimé. Renomme-le (mv .venv .venv.ancien) puis relance install.sh." >&2
        exit 1
    fi
elif [ "$VERIFIER" -eq 1 ]; then
    simule ".venv absent : il serait créé avec « uv venv --python $PY_VERSION »"
else
    if ! "$UV" python find "$PY_VERSION" >/dev/null 2>&1; then
        echo "  Python $PY_VERSION n'est pas disponible : uv peut le télécharger (environ 30 Mo, dans ~/.local/share/uv)."
        confirmer "Télécharger Python $PY_VERSION avec uv ?" || { echo "Installation interrompue." >&2; exit 1; }
    fi
    "$UV" venv --python "$PY_VERSION" .venv
    ok ".venv créé"
fi

# ── 4. Dépendances Python ────────────────────────────────────────────────────
info "Dépendances Python"
if [ "$VERIFIER" -eq 1 ]; then
    simule "uv pip install -r requirements.txt --overrides linux/overrides.txt (non exécuté)"
else
    "$UV" pip install --python "$VENV_PY" -r requirements.txt --overrides linux/overrides.txt
    ok "Dépendances installées"
fi

if [ -x "$VENV_PY" ]; then
    MODULES_MANQUANTS=()
    for m in PyQt6 sounddevice numpy google.genai jeepney keyring faster_whisper piper Xlib pyautogui; do
        PYTHONDONTWRITEBYTECODE=1 "$VENV_PY" -c "import $m" >/dev/null 2>&1 || MODULES_MANQUANTS+=("$m")
    done
    if [ "${#MODULES_MANQUANTS[@]}" -eq 0 ]; then
        ok "Imports principaux : OK"
    else
        warn "Modules Python non importables : ${MODULES_MANQUANTS[*]}"
    fi
    if "$UV" pip show --python "$VENV_PY" python3-xlib >/dev/null 2>&1; then
        warn "python3-xlib (0.15, périmé) est installé : il entre en conflit avec python-xlib."
        warn "Correction : $UV pip uninstall --python .venv/bin/python python3-xlib python-xlib && relance install.sh"
    fi
fi

# ── 5. Lanceur GNOME ─────────────────────────────────────────────────────────
info "Lanceur GNOME ($APP_ID)"
[ "$VERIFIER" -eq 1 ] || chmod +x jarvis.sh install.sh uninstall.sh 2>/dev/null || true
CONTENU="$(sed -e "s|@DEPOT@|$DEPOT|g" -e "s|@ICONE@|$ICONE|g" linux/jarvis.desktop.in)"
if [ "$VERIFIER" -eq 1 ]; then
    if [ -f "$DESKTOP" ] && [ "$(cat "$DESKTOP")" = "$CONTENU" ]; then
        ok "Lanceur à jour : $DESKTOP"
    else
        simule "Lanceur à créer ou mettre à jour : $DESKTOP"
    fi
else
    mkdir -p "$(dirname "$DESKTOP")" "$(dirname "$ICONE")"
    if [ -f "$DEPOT/config/jarvis.ico" ] && "$VENV_PY" - "$DEPOT/config/jarvis.ico" "$ICONE" >/dev/null 2>&1 <<'PY'
import sys
from PIL import Image
Image.open(sys.argv[1]).convert("RGBA").resize((256, 256)).save(sys.argv[2], "PNG")
PY
    then
        ok "Icône : $ICONE"
    else
        warn "Conversion de l'icône impossible : icône générique utilisée."
        ICONE="application-x-executable"
        CONTENU="$(sed -e "s|@DEPOT@|$DEPOT|g" -e "s|@ICONE@|$ICONE|g" linux/jarvis.desktop.in)"
    fi
    if [ -f "$DESKTOP" ] && [ "$(cat "$DESKTOP")" = "$CONTENU" ]; then
        ok "Lanceur déjà à jour : $DESKTOP"
    else
        if [ -f "$DESKTOP" ]; then
            SAUVEGARDE="$DESKTOP.bak.$(date +%Y%m%d%H%M%S)"
            cp -p "$DESKTOP" "$SAUVEGARDE"
            ok "Ancien lanceur sauvegardé : $SAUVEGARDE"
        fi
        printf '%s\n' "$CONTENU" > "$DESKTOP.tmp"
        mv "$DESKTOP.tmp" "$DESKTOP"
        ok "Lanceur écrit : $DESKTOP"
    fi
    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$(dirname "$DESKTOP")" 2>/dev/null || true
fi

# ── 6. Contrôles (lecture seule) ─────────────────────────────────────────────
info "Contrôles"
if [ -f config/api_keys.json ]; then
    MODE="$(stat -c '%a' config/api_keys.json)"
    if [ "$MODE" = "600" ]; then
        ok "config/api_keys.json : permissions 600"
    elif [ "$VERIFIER" -eq 1 ]; then
        simule "config/api_keys.json est en $MODE : chmod 600 proposé (contenu jamais lu ni modifié)"
    elif [ "$OUI" -eq 1 ]; then
        warn "config/api_keys.json est en $MODE. Commande conseillée : chmod 600 config/api_keys.json"
    elif confirmer_strict "config/api_keys.json est en $MODE : passer en 600 (le contenu n'est pas modifié) ?"; then
        chmod 600 config/api_keys.json
        ok "Permissions passées à 600"
    fi
else
    echo "  Aucune clé API configurée : Jarvis affichera son écran de configuration au premier lancement."
fi

if curl -s -m 3 http://localhost:11434/api/tags >/dev/null 2>&1; then
    ok "Ollama répond sur localhost:11434"
else
    echo "  Ollama ne répond pas : le cerveau local sera indisponible (Ollama n'est pas géré par ce script)."
fi

ls modeles/voix/*.onnx >/dev/null 2>&1 \
    && ok "Voix Piper présente (modeles/voix)" \
    || echo "  Aucune voix Piper dans modeles/voix : la voix locale sera indisponible (aucun téléchargement automatique)."
[ -d modeles/whisper ] \
    && ok "Dossier Whisper présent (modeles/whisper)" \
    || echo "  Aucun modèle Whisper : il sera téléchargé par Jarvis à la première utilisation de la reconnaissance locale."

# ── Résumé ───────────────────────────────────────────────────────────────────
info "Terminé"
if [ "$VERIFIER" -eq 1 ]; then
    echo "  Diagnostic uniquement : rien n'a été modifié."
else
    echo "  Lancer :  ./jarvis.sh      (ou « Jarvis FR » dans la grille des applications GNOME)"
fi
[ "$AVERTISSEMENTS" -eq 0 ] || echo "  $AVERTISSEMENTS avertissement(s) à examiner ci-dessus."
exit 0
