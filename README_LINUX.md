# Jarvis FR sous Linux (Ubuntu 26.04 / GNOME Wayland)

Testé sur Ubuntu 26.04, GNOME 50, session Wayland, Python 3.13.

## Installation

```bash
git clone https://github.com/jeromecamilleri/jarvis-fr.git
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
`io.github.jeromecamilleri.JarvisFR`, requis par les portails XDG (raccourci push-to-talk, RemoteDesktop) :
**ne le renomme pas**.

Variables optionnelles : `JARVIS_PTT_CHORD` (ex. `ctrl+f9`, touche push-to-talk), `JARVIS_STATE_DIR`,
`JARVIS_LOG_DIR`.

Arrêt : dis « Jarvis, éteins-toi » ou ferme la fenêtre. Les traces d'arrêt sont dans
`~/.local/state/jarvis-fr/logs/`.

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

Détails dans `AUDIT_LINUX.md`. En résumé : pas de clics à coordonnées, de focus de fenêtre native,
d'enregistrement d'écran ni de presse-papiers pilotable ; ces fonctions répondent par un message explicite.
Le placement de fenêtres envoie un raccourci GNOME à la fenêtre active, sans vérification du résultat.

## Désinstallation

```bash
./uninstall.sh                    # retire le lanceur et l'icône, propose de supprimer .venv
./uninstall.sh --supprimer-venv   # supprime aussi .venv
```

Ne sont **jamais** supprimés : `config/`, `memory/`, `modeles/`, `uploads/`, `cerveau-modele/`, les journaux,
`~/.local/state/jarvis-fr/`, uv, Ollama, ni le dépôt.

## Dépannage

- `./install.sh --verifier` : diagnostic sans modification.
- `config/api_keys.json` en 664 : `chmod 600 config/api_keys.json` (install.sh le propose).
- Pas de son : vérifie `wpctl status` et que `libportaudio2` est installé.
- Push-to-talk inactif : vérifie que `~/.local/share/applications/io.github.jeromecamilleri.JarvisFR.desktop` existe.
