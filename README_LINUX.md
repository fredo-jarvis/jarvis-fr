# Jarvis FR sous Linux (Ubuntu / GNOME Wayland)

Ce portage vise **Ubuntu avec GNOME**, en priorité en session **Wayland**. Il n'est pas prévu pour d'autres
distributions ou bureaux : `install.sh` repose sur `apt`, `dpkg`, le trousseau GNOME et `gio`.

| Système | État |
|---|---|
| Ubuntu 26.04, GNOME 50, Wayland, Python 3.13 | testé |
| Ubuntu 24.04 (GNOME 46) | essais partiels, **non validé** intégralement |
| Autres distributions, KDE, X11 seul | non testé, non pris en charge |

## Installation

```bash
git clone https://github.com/fredo-jarvis/jarvis-fr.git
cd jarvis-fr
./install.sh
```

`install.sh` est **idempotent** : on peut le relancer sans risque. Il :

1. liste les paquets `apt` manquants et propose de les installer avec `sudo` ;
2. propose d'installer [uv](https://docs.astral.sh/uv/) dans `~/.local/bin` s'il est absent (sans `sudo`) ;
3. crée `.venv` en Python 3.13 (uv peut télécharger Python 3.13 après confirmation) ;
4. installe `requirements.txt` avec `linux/overrides.txt` ;
5. crée le lanceur GNOME et son icône ;
6. fait des contrôles sans rien modifier (clé API, Ollama, voix, Whisper).

| Option | Effet |
|---|---|
| `--oui` | accepte les confirmations ordinaires (apt, uv, Python) ; jamais celle de `chmod` sur les clés |
| `--sans-apt` | n'utilise pas `apt`, liste seulement les paquets manquants |
| `--verifier` | diagnostic complet **sans aucune modification** |

Paquets `apt` indispensables : `libportaudio2 wireplumber libnotify-bin gnome-keyring libsecret-1-0
libxcb-cursor0 libxkbcommon0 libegl1 libgl1 xdg-utils`. Facultatifs, jamais installés automatiquement :
`ffmpeg gnome-text-editor gnome-calculator nautilus brightnessctl`, ainsi que Google Chrome ou Chromium.

### Pourquoi `linux/overrides.txt` ?

`pyautogui` exige `python3-Xlib`, une très ancienne version (0.15) qui fournit le même module `Xlib` que
`python-xlib` et entre en conflit avec lui. `install.sh` l'exclut ; `python-xlib` 0.33 est installé à sa place.
N'installe donc pas les dépendances avec un simple `pip install -r requirements.txt`.

## Lancement

```bash
./jarvis.sh
```

ou **« Jarvis FR »** dans la grille des applications GNOME. Le lanceur utilise l'identifiant
`io.github.fredo_jarvis.JarvisFR`, requis par les portails XDG (raccourci push-to-talk, RemoteDesktop) :
**ne le renomme pas**.

Variables optionnelles : `JARVIS_PTT_CHORD` (ex. `ctrl+f9`, touche push-to-talk), `JARVIS_STATE_DIR`,
`JARVIS_LOG_DIR`.

Arrêt : dis « Jarvis, éteins-toi » ou ferme la fenêtre. Les traces d'arrêt sont dans
`~/.local/state/jarvis-fr/logs/`.

### Arrêt de Jarvis et fenêtre Galaxie

- **À l'arrêt**, le processus Python, Galaxie et le Dashboard sont arrêtés.
- **Avec Chrome ou Chromium** : fenêtre applicative dédiée (profil `.fenetre-chrome`), refermée par Jarvis.
- **Sans Chrome ni Chromium, avec Firefox** : Jarvis lance sa propre instance Firefox (`--no-remote`, profil dédié
  `~/snap/firefox/common/jarvis-fr-galaxie` pour le snap, sinon `~/.local/state/jarvis-fr/firefox-galaxie`). Ton profil
  et tes fenêtres Firefox ne sont pas touchés. À l'arrêt, Jarvis ferme uniquement cette instance (son propre groupe de
  processus). Fermer cette fenêtre éteint Jarvis, comme avec Chrome.
- **Sans aucun des deux** (ou si Firefox ne démarre pas) : navigateur par défaut, hors de portée de Jarvis. L'onglet reste
  ouvert avec « ARRÊTÉ » : ferme-le à la main. Jarvis ne ferme jamais les autres fenêtres du navigateur.

## Premier lancement

- La clé Gemini se saisit dans l'écran de configuration de Jarvis. L'installateur ne la demande ni ne la lit.
- GNOME demande une autorisation au premier usage de la capture d'écran et de la saisie clavier
  (RemoteDesktop). Le jeton est conservé dans `~/.local/state/jarvis-fr/remotedesktop.json` (droits 600).
- **Cerveau local** : Ollama n'est pas installé par ce script. Installe-le toi-même, puis
  `ollama pull qwen3:8b`.
- **Voix locale** : place un modèle Piper (par exemple `fr_FR-tom-medium.onnx` et son `.json`) dans
  `modeles/voix/`. Rien n'est téléchargé automatiquement.
- **Reconnaissance locale** : le modèle Whisper est téléchargé par Jarvis à la première utilisation,
  dans `modeles/whisper/`.

## Limites sous Wayland

En résumé : pas de clics à coordonnées, de focus de fenêtre native,
d'enregistrement d'écran ni de presse-papiers pilotable ; ces fonctions répondent par un message explicite.
Le placement de fenêtres envoie un raccourci GNOME à la fenêtre active, sans vérification du résultat.

## Désinstallation

```bash
./uninstall.sh                    # retire le lanceur et l'icône, propose de supprimer .venv
./uninstall.sh --supprimer-venv   # supprime aussi .venv
```

Seul un lanceur créé par `install.sh` (marqueur `X-Jarvis-FR-Installateur=true`) est supprimé, même avec `--oui`.

Ne sont **jamais** supprimés : `config/`, `memory/`, `modeles/`, `uploads/`, `cerveau-modele/`, les journaux,
`~/.local/state/jarvis-fr/`, uv, Ollama, ni le dépôt.

## Dépannage

- `./install.sh --verifier` : diagnostic sans modification.
- `config/api_keys.json` en 664 : `chmod 600 config/api_keys.json` (install.sh le propose).
- Pas de son : vérifie `wpctl status` et que `libportaudio2` est installé.
- Push-to-talk inactif : vérifie que `~/.local/share/applications/io.github.fredo_jarvis.JarvisFR.desktop` existe.
