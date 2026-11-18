# Audit du portage Linux de Jarvis FR (étape 1)

Branche : `linux-installer` · Cible : Ubuntu 26.04.1 (GNOME 50, Wayland) · Date de l'audit : 17/11/2026
Statut : **analyse seulement.** Aucun fichier du projet modifié, aucun paquet installé, aucun commit.
Ce rapport est le seul fichier créé.

**Légende des statuts**

| Sigle | Sens |
|---|---|
| ✅ **Constaté** | Exécuté ou mesuré sur cette machine pendant l'audit |
| 📖 **Lu** | Établi en lisant le code ou la source d'une dépendance, sans l'exécuter |
| ⚠️ **Risque** | Plausible mais non vérifié : à tester à l'étape indiquée |

Le démarrage réel de Jarvis n'a **pas** été tenté, car il demande l'environnement de l'étape 2. Tout ce qui touche à l'exécution est donc 📖 ou ⚠️, sauf mention contraire.

---

## 1. Synthèse exécutive

1. **Le portage est faisable et de taille raisonnable.** Le projet est déjà en partie multiplateforme : `requirements.txt` filtre par OS, et `computer_settings`, `browser_control`, `reminder`, `open_app`, la création de raccourci bureau et le démarrage automatique ont déjà une branche Linux (📖).
2. **Il n'y a pas de bloc Windows « global ».** Il y a une quarantaine d'appels Windows épars, dont une dizaine seulement sur le chemin de démarrage ou de fonctionnement courant.
3. **Python 3.14 n'est pas bloqué par les dépendances** (✅). La résolution `uv pip compile` réussit en 3.14 comme en 3.13, avec des wheels pour les paquets lourds (NumPy, OpenCV, PyQt6, CTranslate2, onnxruntime, av, cryptography). Je recommande quand même **Python 3.13** pour le premier portage : c'est la version maximale annoncée comme testée, et `uv` a déjà un 3.13.14 sur ta machine.
4. **Le vrai sujet est Wayland, pas Python.**
   - ✅ **Ubuntu 26.04 n'a plus de session « Ubuntu on Xorg »** : `/usr/share/xsessions` ne contient qu'`openbox`, et `/usr/share/wayland-sessions` qu'`ubuntu.desktop`. Je retire donc la piste « basculer en Xorg » que j'avais mentionnée. Wayland est la cible, pas une option.
   - Les portails `GlobalShortcuts`, `Screenshot`, `ScreenCast`, `RemoteDesktop`, `InputCapture` et `Camera` sont présents (✅). Ce sont les voies propres pour les raccourcis globaux et la capture d'écran.
5. **Ce qui plantera ou dégradera dès le premier lancement** (✅ pour les mécanismes, 📖 pour leur enchaînement) :
   - Les `subprocess.Popen(..., creationflags=0x08000000)` des plugins `cerveau_*` et de `galaxie/cerveau_carte.py` lèvent `ValueError` sous Linux.
   - Le chemin de Chrome est codé en dur (`C:\Program Files\...`). Sous Linux, l'interface « galaxie » s'ouvre donc dans le navigateur par défaut (Firefox snap ici), sans placement d'écran et sans lien de vie avec Jarvis. Elle devrait s'ouvrir dans `/usr/bin/google-chrome`, qui est installé.
   - Le raccourci Échap et le push-to-talk globaux n'existent que sous Windows.
6. **Limites propres à ta machine** (✅) :
   - Pas de rétroéclairage (`/sys/class/backlight` vide), donc `brightnessctl` n'a aucun intérêt ici.
   - `pactl` est absent alors que PipeWire tourne ; `wpctl` est présent.
   - Le modèle `qwen3.5:9b` n'est pas installé dans Ollama. Il y a `qwen3:8b` et `llama3.2:3b`.
7. **Recommandation d'architecture** : une petite couche `core/plateforme/` **additive**, pas une refonte. Les branches Windows existantes restent identiques. Le diff reste petit, ce qui compte si une PR doit être proposée au mainteneur.
8. **Plan** : 9 lots indépendants (§7). Le lot 1 vise « l'interface démarre sous Ubuntu 26.04 ». L'installateur vient en dernier, séparé du portage fonctionnel.

---

## 2. Résultats détaillés de l'audit

### 2.1 Vérifications exécutées

| # | Constat | Statut |
|---|---|---|
| 1 | `ctypes.windll` n'existe pas sous Linux : `AttributeError` à l'appel | ✅ |
| 2 | `subprocess.Popen(..., creationflags=<non nul>)` lève `ValueError: creationflags is only supported on Windows platforms`. `creationflags=0` passe. | ✅ |
| 3 | `os.startfile`, `subprocess.CREATE_NO_WINDOW` et `DETACHED_PROCESS` n'existent pas sous Linux. `from ctypes import wintypes` s'importe sans erreur. | ✅ |
| 4 | Tous les `.py` du projet (hors tests) sont syntaxiquement valides sous Python 3.14 | ✅ |
| 5 | `requirements.txt` se résout en 3.14 **et** en 3.13 (Linux x86-64, wheels exigées pour les paquets lourds) | ✅ |
| 6 | Pas de session Xorg GNOME sous Ubuntu 26.04 (seulement Wayland) | ✅ |
| 7 | Portails XDG disponibles : `GlobalShortcuts`, `Screenshot`, `ScreenCast`, `RemoteDesktop`, `InputCapture`, `Camera` | ✅ |
| 8 | `google-chrome` installé (`/usr/bin/google-chrome`), Firefox en snap, `xdg-settings` et `xdg-user-dir` présents | ✅ |
| 9 | `pactl`, `brightnessctl`, `scrot`, `gnome-screenshot`, `espeak-ng` et `at` absents. `wpctl`, `spd-say`, `notify-send`, `nmcli`, `xdotool`, `wmctrl`, `ffmpeg` et `systemd-run` présents. | ✅ |
| 10 | Aucun rétroéclairage exposé (PC fixe) | ✅ |
| 11 | Python : 3.14.4 système, plus 3.13.14 et 3.12.13 gérés par `uv`. `apt` n'a pas de `python3.13`. | ✅ |
| 12 | Ollama installé avec `qwen3:8b`, `llama3.2:3b` et `bge-m3`, mais pas `qwen3.5:9b` (le défaut de `cerveau_local.py`) | ✅ |
| 13 | GPU : GTX 1070, 8 Go, pilote 580.178 ; micro Jabra et webcam Logitech C930e détectés ; `/dev/video0-3` présents | ✅ |
| 14 | Bibliothèques Qt/audio du système déjà installées : `libxcb-cursor0`, `libxkbcommon-x11-0`, `libxcb-xinerama0`, `libxcb-icccm4`, `libxcb-keysyms1`, `libxcb-shape0`, `libegl1`, `libgl1`, `libportaudio2`, `libasound2t64`, `libnotify-bin`, `speech-dispatcher` | ✅ |
| 15 | PyQt6 système 6.10.2 / Qt 6.10.2 avec les plugins `xcb` et `wayland` ; `uv` résout PyQt6 6.9.1 pour le `.venv` | ✅ |
| 16 | `pygetwindow` 0.0.9 : le code n'a de backend que pour `win32` et `darwin`. Aucune fonction de fenêtres sous Linux (`getAllWindows` n'est pas défini). | 📖 (source lue) |
| 17 | `PIL.ImageGrab.grab()` sous Wayland se rabat sur `gnome-screenshot` (puis `grim`) ; sans eux, il ne capture rien | 📖 (source lue) |
| 18 | `mss` 10.2 sous Linux n'a que des backends X11 (xcb, xlib), pas de Wayland natif | 📖 (source lue) |
| 19 | `pyautogui` 0.9.54 sous Linux charge `_pyautogui_x11` (Xlib + XTest), donc X11 / XWayland seulement | 📖 (source lue) |

### 2.2 Problèmes prioritaires demandés, examinés dans leur contexte

| Élément | Constat | Bloquant ? |
|---|---|---|
| `ui.py:428-444` `_flou_derriere` (`windll…SetWindowCompositionAttribute`) | Dans un `try/except` qui affiche seulement un message. Appelé seulement si le réglage `flou` est vrai (désactivé depuis le 28/10), via `QTimer` (`ui.py:3205`). | 🟢 Non : mort sous Linux, sans erreur |
| `ui.py:451-484` `_au_premier_plan` (`comtypes`, `windll…SetWindowPos`) | Dans un `try/except` externe et interne. Le commentaire `ui.py:5907` indique que la fonction n'est plus appelée (« reste disponible »). | 🟢 Non : code dormant |
| `galaxie/placement.py` (5 `windll`) | Fonctions sans garde, appelées depuis `main.py:2915` (fermeture), `main.py:2925` (démarrage) et `galaxie/server.py:390`. `fermer_fenetre_jarvis` est enveloppée dans un `try`. `poser()`, `Fenetre` et `amener_devant()` ne le sont pas, mais `poser()` n'est atteinte que si Chrome Windows existe. | 🟠 Contourné aujourd'hui par `CHROME.exists()` faux, mais à remplacer (cf. 2.3) |
| `plugins/youtube_controle.py:147` `SetProcessDPIAware` | Dans un `try/except` : sans effet sous Linux. | 🟢 Non |
| `plugins/youtube_controle.py:154-` (`pygetwindow`) | `gw.getAllWindows()` est inexistant sous Linux. L'appel est dans un `try/except`, d'où le message « Couldn't enumerate active windows ». Le plugin ne trouve donc jamais la fenêtre YouTube sous Linux. | 🟠 Fonction cassée (silencieusement) |
| `plugins/enregistrer_ecran.py:424` `RegisterHotKey` | Dans `_hotkey_message_loop`, appelée seulement si `platform.system() == "Windows"` (`:459`). Les raccourcis Win+Alt+R/P n'existent donc pas sous Linux. | 🟢 Non bloquant, 🟠 fonction absente |
| `core/cerveau_local.py` | (a) `PROGRAMME_STUDIO` pointe vers `AppData\…\VoiceStudio.exe`, absent sous Linux : `ouvrir_studio` retourne faux avant le `ctypes.windll` (`:326`), donc pas d'erreur. (b) `pret()` cherche `AppData\…\ollama.exe`, sinon lance `ollama serve` du `PATH` : OK sous Linux. (c) `VoixLocale` (secours) lance `powershell.exe` : échoue sous Linux. (d) Le texte de repli fait exister Piper avant Hortense, ce qui est correct. | 🟠 (c) à remplacer ; le reste fonctionne |
| `Lancer-Jarvis.bat`, `index_pc.py` | `.venv\Scripts\python.exe` : le chemin Linux est `.venv/bin/python`. `index_pc.py` indexe `.lnk`, `.exe`, `C:/`, `D:/` : rend un index presque vide sous Linux. Aucun `.desktop` indexé. | 🟠 Fonction « ouvre un fichier ou une appli par son nom » dégradée |
| `core/coffre.py` | DPAPI seulement. Hors Windows, `chiffrer()` rend `None` et l'appelant garde l'ancien comportement (fichier lisible par l'utilisateur seulement). Le module fait `import ctypes` en haut mais n'utilise `windll` qu'après `disponible()` : sûr. | 🟠 Pas de plantage ; secret Gmail en clair sur disque |
| `ui.py:3825+` création de raccourci bureau | Trois branches (Windows, macOS, Linux `.desktop`). `_get_desktop_dir` gère déjà le bureau XDG localisé. | 🟢 Prêt : à tester |
| `ui.py:5230-5290` démarrage automatique | Trois branches. Linux : `~/.config/autostart/jarvis.desktop`. | 🟢 Prêt : à tester |
| `ui.py` raccourcis Qt | `F2`, `F3`, `F4`, `F11`, `Échap` et le push-to-talk (`QShortcut`) ne fonctionnent que si la fenêtre Qt a le focus. Or elle « ne s'affiche plus jamais » (`ui.py:5888`) : l'interface est la page galaxie. | 🟠 Aucun raccourci clavier utilisable sous Linux (cf. 2.4) |

### 2.3 Chemin de démarrage sous Linux (📖)

1. `main.py` : `main()` crée `JarvisUI` (Qt), attend la clé API, puis `_relier_galaxie()`.
2. `_galaxie.demarrer_dans_jarvis(pont)` lance le serveur HTTP local (`localhost:4719`). Rien de Windows dans cette partie.
3. `ouvrir()` appelle `_galaxie.ouvrir_fenetre()`. Sous Linux, `CHROME.exists()` est faux : la fonction appelle `webbrowser.open(ADRESSE)` et rend `False` ; `ouvrir()` s'arrête donc **avant** `placement.poser` et avant `_eteindre_tout`.
4. **Conséquences** : la galaxie s'ouvre dans Firefox (navigateur par défaut) ; elle n'est pas posée sur l'écran voulu ; fermer la page n'éteint pas Jarvis ; la page `/api/jarvis/couper` et `/muet` reste le seul moyen de couper la parole ou le micro depuis l'écran.
5. `ouvrir_adresse()` (connexion Google, `galaxie/server.py:386`) appelle `ctypes.windll` sans garde : `AttributeError` sous Linux, remonté comme erreur 503 par le serveur.
6. `plugins/cerveau_tableau.py` : tant que le serveur tourne (c'est le cas dans Jarvis), il n'appelle pas `Popen`. S'il doit le lancer, `creationflags` lève `ValueError`. Le repli `CHROME.exists()` faux passe par `webbrowser.open` : OK.

### 2.4 Wayland : ce qui marche et ce qui ne marche pas

Classement par capacité sous GNOME 50 / Wayland (Mutter) :

| Classe | Fonctions Jarvis concernées | Détail |
|---|---|---|
| **Compatibles Wayland natif** | Interface Qt (plugin `wayland`, sinon `xcb` via XWayland) ; audio PipeWire (`sounddevice` via PortAudio/Pulse) ; webcam (`cv2.VideoCapture`, V4L2) ; Playwright / Chrome ; `xdg-open`, `notify-send`, `nmcli`, `systemd-run --user`, `loginctl lock-session`, `wpctl`/`pactl` ; Ollama ; serveurs HTTP locaux | Rien à contourner |
| **Via XWayland seulement** | `pyautogui` (clavier, souris : XTest) ; `mss` ; `xdotool` ; `wmctrl` ; Chrome si lancé en mode X11 | Ces outils n'agissent que sur les fenêtres **X11/XWayland**. Les fenêtres natives Wayland (Nautilus, Terminal GNOME, Éditeur de texte…) ne reçoivent pas les événements injectés et n'apparaissent pas dans `wmctrl`. La capture d'écran XWayland ne contient pas les fenêtres natives (⚠️ à confirmer à l'étape 6 : image noire ou partielle). |
| **Impossibles sans portail ou API dédiée** | Raccourcis clavier globaux (push-to-talk, Échap, Win+Alt+R) ; capture d'écran complète fiable ; clic ou frappe dans une fenêtre native ; activation d'une fenêtre native par son titre | Portails disponibles ici : `GlobalShortcuts` (raccourcis), `Screenshot`/`ScreenCast` (capture, avec une autorisation de l'utilisateur), `RemoteDesktop` (injection d'entrées, avec autorisation). L'activation d'une fenêtre par son titre n'a **aucune** API standard sous GNOME. |
| **Nécessitant Xorg** | Rien d'indispensable | Et Xorg n'est de toute façon **pas offert** (✅ cf. 1.4). |

**Évaluation des deux stratégies**

| | Rester sous Wayland (recommandé) | Imposer XWayland / Xorg |
|---|---|---|
| Faisabilité sur Ubuntu 26.04 | ✅ C'est la session par défaut et la seule | ❌ Pas de session Xorg ; XWayland seul laisse les limites ci-dessus |
| Raccourcis globaux | Portail `GlobalShortcuts` (nécessite D-Bus, autorisation utilisateur, code de portage) | Inchangé (inutile : indisponible) |
| Capture d'écran | Portail `Screenshot` (retour d'un fichier) ou `gnome-screenshot` | `mss` sur XWayland : incomplet |
| Souris et clavier | `RemoteDesktop` (portail) ou `ydotool` (droits `uinput`) ; ou limitation assumée | `pyautogui` : seulement fenêtres XWayland |
| Effort | Moyen à élevé, lots 6 et 7 | Faible mais résultat dégradé |
| Impact Windows | Nul (code additif) | Nul |

**Décision proposée** : rester sous Wayland, annoncer clairement les limites (« mode dégradé » signalé à l'utilisateur plutôt qu'échec silencieux) et traiter les portails dans un lot dédié (lot 6), sans en faire un prérequis du démarrage.

### 2.5 Python 3.13 ou 3.14 ?

Résolution `uv pip compile` (Linux x86-64) ✅ : mêmes versions sous 3.13 et 3.14.

| Dépendance | Version résolue | Wheel 3.14 | Remarque |
|---|---|---|---|
| PyQt6 / PyQt6-Qt6 | 6.9.1 / 6.9.2 | oui (abi3) | Qt est embarqué dans la wheel |
| NumPy | 2.5.5 | oui (cp314) | |
| opencv-python | 4.14.0.94 | oui (abi3) | ⚠️ voir note OpenCV ci-dessous |
| sounddevice | 0.5.6 | oui (py3) | **Ne contient pas PortAudio** : `libportaudio2` du système (✅ installé) |
| PyAutoGUI / pygetwindow | 0.9.54 / 0.0.9 | sdist pur Python | Résolus ; fonctionnement sous Wayland limité (cf. 2.4) |
| Playwright | 1.65.2 | oui (py3) | ⚠️ Ubuntu 26.04 non listée officiellement : `playwright install --with-deps` peut échouer. Chrome système en repli (`channel`). |
| faster-whisper | 1.2.1 | oui | Dépend de `ctranslate2` 4.9.0 (cp314), `onnxruntime` 1.32.0 (cp314), `av` 19.0.2 (cp314) |
| piper-tts | 1.8.0 | oui | Résolu avec openwakeword 0.4.0 |
| google-genai | 2.34.0 | oui | Borne du projet `<3` ; la 3.x n'est pas sélectionnée |
| cryptography, psutil, pillow, mss, pynvml | 49.0.0, 7.2.2, 12.3.0, 10.2.0, 13.0.1 | oui | |

**Conclusion** : 3.14 est résoluble mais **non testé à l'exécution** par le projet (`setup.py` : `MAX_PY = (3, 13)`, simple avertissement au-delà). Le premier portage se fait en **3.13** (déjà présent via `uv`) pour ne pas mélanger deux inconnues ; un test en 3.14 vient ensuite en lot 1b, non bloquant.

⚠️ **Note OpenCV** : les wheels `opencv-python` embarquent leurs propres plugins Qt et peuvent entrer en conflit avec PyQt6 sous Linux (erreur « could not load the Qt platform plugin xcb »). Le projet n'appelle ni `imshow` ni `waitKey` (✅ grep) : seuls `VideoCapture` et l'encodage sont utilisés. `opencv-python-headless` serait donc un remplacement sûr sous Linux ; à confirmer à l'étape 2.

### 2.6 Constats par catégorie

**Actions système** (`actions/computer_settings.py`, `reminder.py`, `open_app.py`, `browser_control.py`) : les branches Linux existent. Ce qui manque est l'outil sur ta machine, pas le code.
- Volume : appelle `pactl` (absent ici). `wpctl` est présent, et `pactl` est fourni par `pulseaudio-utils`. Deux options : installer le paquet, ou ajouter un repli `wpctl`.
- Luminosité : `brightnessctl` (absent, et ta machine n'a pas de rétroéclairage). À laisser en mode « non supporté » avec un message clair.
- Capture d'écran : `scrot` ou `gnome-screenshot` (absents), sinon `Ctrl+PrintScreen` via `pyautogui`.
- Verrouillage : `loginctl lock-session` en dernier recours (présent).
- Rappels : `systemd-run --user --on-calendar` (présent) ; notification `notify-send` (présent).
- `open_app` : table de noms avec colonne Linux (`gedit` n'existe plus sous Ubuntu 26.04 : c'est `gnome-text-editor`) ; repli `xdg-open`.
- `game_updater` : `winreg` et `tasklist` ; Steam et Epic sous Linux ne sont pas pris en charge (📖).
- `file_controller` : restauration depuis la corbeille réservée à Windows ; le code le dit et propose un message de repli (📖).

**Voix** : sous Linux, `cerveau_local.nouvelle_voix()` essaie VoiceStudio (absent) puis Piper (voix `.onnx` à télécharger) puis `VoixLocale` (PowerShell : échoue). Il faut donc un repli Linux fiable (Piper, puis `spd-say` ou `espeak-ng`).

**Audio** : `core/audio_devices.py` prévoit déjà `("pulse", "pipewire", "jack", "alsa")` pour Linux (📖). La logique est écrite, mais jamais exécutée ici.

**Vision** : `cv2.VideoCapture(index, CAP_ANY)` sous Linux (📖), webcam `/dev/video0` présente. La capture d'écran passe par `mss` (limitée sous Wayland, cf. 2.4).

**Indexation** : `index_pc.py` est entièrement Windows (menu Démarrer, `.exe`, `C:`/`D:`). Il faut une version Linux : lecture des `.desktop` (`/usr/share/applications`, `~/.local/share/applications`, snaps et flatpaks) et un dossier utilisateur XDG.

**Dashboard distant** : `dashboard/server.py` a une branche Linux (`pkexec` puis `sudo -n`, sinon commande manuelle). Sous Ubuntu, `ufw` est inactif par défaut : probablement rien à faire (⚠️ à tester).

**Cerveau / Obsidian** : `plugins/_cerveau_commun.py` retombe sur `~/Documents/Cerveau` si l'API Windows échoue (✅ par lecture). Aucun changement nécessaire, sauf ajouter `xdg-user-dir DOCUMENTS` pour les systèmes localisés (optionnel).

---

## 3. Matrice de compatibilité (20 fonctionnalités)

Priorités : **P0** démarrage, **P1** fonction centrale, **P2** fonction secondaire, **P3** optionnel.
Compat. Ubuntu : 🟢 prêt · 🟠 partiel · 🔴 absent.
Wayland : N = natif · X = XWayland seulement · P = portail requis · — = sans objet.

| # | Fonction | Fichiers | État actuel (statut) | Ubuntu | Wayland | Problème | Correction | Prio | Test de validation |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Démarrage | `main.py`, `ui.py`, `setup.py` | `ast.parse` OK en 3.14 ✅ ; démarrage non tenté | 🟠 | N | Environnement absent ; aucune exécution tentée | Créer le `.venv` 3.13, installer, lancer | P0 | `python main.py` ouvre le serveur sur `:4719` sans traceback |
| 2 | Interface PyQt6 | `ui.py`, `main.py` | Qt présent (6.10.2 système ✅) ; fenêtre jamais affichée 📖 | 🟠 | N/X | `QT_QPA_PLATFORM` à choisir ; fenêtre de saisie de clé à vérifier ⚠️ | Tester `wayland` puis `xcb` ; garder offscreen pour les tests | P0 | `QT_QPA_PLATFORM=offscreen` : tests existants ; lancement réel : saisie de clé API |
| 3 | Galaxie (interface réelle) | `galaxie/server.py`, `galaxie/placement.py`, `main.py` | Chrome en dur ; repli `webbrowser` 📖 | 🔴 | X/P | Mauvais navigateur, pas de placement, pas de lien de vie, `ouvrir_adresse` plante | `google-chrome --app=…` via `subprocess` ; suivi du processus ; pas de placement sous Wayland (assumé) | P0 | La page s'ouvre dans Chrome app ; fermer la fenêtre éteint Jarvis |
| 4 | Audio et micro | `main.py`, `core/audio_devices.py`, `core/tts.py` | Branche Linux écrite 📖 ; `libportaudio2` présent ✅ | 🟠 | N | `sounddevice` jamais exécuté ; sélection d'appareils Pulse/Pipewire à valider | Installer, lister les appareils, choisir micro Jabra | P1 | `sd.query_devices()` ; 3 s d'enregistrement puis lecture |
| 5 | Gemini Live | `main.py`, `core/gemini.py` | Réseau pur ; pas de Windows 📖 | 🟢 | — | Dépend du lot 4 (audio) | Aucune a priori | P1 | Une phrase dite à Jarvis, réponse vocale |
| 6 | Synthèse vocale locale | `core/cerveau_local.py` | VoiceStudio Windows ; Piper OK ; `VoixLocale` = PowerShell 📖 | 🟠 | N | Secours cassé ; voix Piper à télécharger | Repli `spd-say`/`espeak-ng` ; documenter le téléchargement de la voix | P1 | `nouvelle_voix().dire("test")` audible |
| 7 | Reconnaissance vocale | `core/oreilles_locales.py`, `core/stt.py` | `faster-whisper` CPU int8, résolu ✅ | 🟢 | N | Modèle Whisper à télécharger (réseau) | Rien de code | P1 | Transcrire 5 s de micro en français |
| 8 | Ollama / cerveau local | `core/cerveau_local.py`, `core/llm_client.py`, `plugins/changer_cerveau.py` | Ollama installé ✅ ; modèle par défaut absent ✅ ; `pret()` lance `ollama serve` 📖 | 🟢 | — | `qwen3.5:9b` non installé ; pas d'outils (hors portage) | Régler `cerveau_local_modele` ou installer le modèle ; ne pas réinstaller Ollama | P1 | « passe sur ton cerveau local » → `[Cerveau local] première phrase…` |
| 9 | Mémoire et coffre | `memory/`, `core/coffre.py`, `plugins/gmail_lire.py` | DPAPI seulement ; repli en clair 📖 | 🟠 | — | Secret Gmail non chiffré | `keyring` (Secret Service / GNOME Keyring) avec repli actuel | P2 | Aller-retour `chiffrer`/`dechiffrer` ; relecture après redémarrage |
| 10 | Raccourcis clavier | `core/hotkey.py`, `main.py:1200`, `ui.py` (`QShortcut`) | Global seulement sous Windows 📖 | 🔴 | P | Aucun raccourci utilisable (fenêtre Qt cachée) | Portail `GlobalShortcuts` ; sinon boutons de la page galaxie | P2 | Raccourci enregistré dans les réglages GNOME ; appui détecté |
| 11 | Clavier et souris | `actions/computer_control.py`, `send_message.py`, `computer_settings.py`, `youtube_controle.py` | `pyautogui` via XTest 📖 | 🟠 | X | N'agit que sur XWayland | Message de limite ; option `RemoteDesktop` ou `ydotool` (P3) | P2 | Taper dans une fenêtre XWayland (Chrome) |
| 12 | Gestion des fenêtres | `actions/computer_control.py:focus_window`, `plugins/youtube_controle.py` | `wmctrl`/`xdotool` ; `pygetwindow` sans backend Linux 📖 | 🔴 | X | Fenêtres natives invisibles ; YouTube introuvable | Repli explicite ; sinon API de la page ; extension GNOME en option | P2 | Activer une fenêtre Chrome par titre |
| 13 | Fichiers et corbeille | `actions/file_controller.py`, `core/undo.py`, `open_anything.py` | `send2trash` ; restauration Windows seulement 📖 | 🟠 | — | Restauration corbeille non supportée | Message de repli existant ; éventuel `gio trash --restore` | P3 | Supprimer puis annuler un fichier de test |
| 14 | Navigateur et Playwright | `actions/browser_control.py`, `requirements.txt` | Branche Linux 📖 ; `google-chrome` présent ✅ | 🟠 | N/X | Ubuntu 26.04 non officielle pour `--with-deps` ⚠️ | `playwright install chromium` sans `--with-deps`, sinon `channel="chrome"` | P1 | « ouvre YouTube » ouvre la page |
| 15 | Webcam et vision | `actions/screen_processor.py`, `ui.py:3531` | `CAP_ANY` ; webcam présente ✅ | 🟢 | N | `opencv-python` vs Qt ⚠️ ; capture d'écran via `mss` (voir 11) | `opencv-python-headless` ; capture d'écran via portail | P1 | Une image de la webcam est envoyée à Gemini ; capture d'écran non vide |
| 16 | Notifications et rappels | `actions/reminder.py` | `notify-send`, `systemd-run --user` ; `win10toast`/`winsound` isolés 📖 | 🟢 | N | `winsound` dans un `try` ; sans bip sonore | Rien d'obligatoire | P2 | « rappelle-moi dans 2 minutes » : notification reçue |
| 17 | Galaxie et hologramme | `plugins/cerveau_hologramme.py`, `cerveau_galaxie.py`, `cerveau_tableau.py`, `galaxie/cerveau_carte.py`, `holo/` | `creationflags` → `ValueError` ✅ ; `netstat`/`taskkill` ; Chrome codé en dur 📖 | 🔴 | N/X | Plantent dès le lancement d'un sous-processus | Chemin d'ouverture et arrêt du serveur portables (`ss`/`psutil`) | P1 | « ouvre l'hologramme » ; « ferme l'hologramme » |
| 18 | Dashboard distant | `dashboard/server.py` | Branche Linux (`pkexec`) ; uvicorn | 🟢 | — | `ufw` inactif probablement ⚠️ | Aucune a priori | P2 | Scan du QR code depuis le téléphone |
| 19 | Indexation des apps | `index_pc.py`, `actions/open_anything.py`, `open_app.py` | 100 % Windows 📖 | 🔴 | — | Index vide ; noms de la table `open_app` partiellement faux | Version Linux basée sur les `.desktop` | P2 | « ouvre la calculatrice » trouve `gnome-calculator` |
| 20 | Gestion du système | `actions/computer_settings.py`, `system_monitor.py`, `ui.py` | Branches Linux 📖 ; `pactl` absent ✅ ; pas de rétroéclairage ✅ | 🟠 | N | `pactl` absent ; luminosité sans objet ici ; moniteur GPU : `libnvidia-ml.so.1` géré 📖 | Repli `wpctl` ; message clair pour la luminosité | P2 | Volume +10 % ; état du système affiche CPU/RAM/GPU |

**Plugins** (ligne 20 du cahier des charges, détaillée) : parmi les 17 plugins, `changer_ecran`, `enregistrer_ecran` (hotkeys), `montre_ou_cliquer` (capture, `startfile` gardé), `youtube_controle` (fenêtres) et les 3 `cerveau_*` serveurs sont affectés. Les autres (`cerveau_chercher`, `cerveau_lire`, `cerveau_noter`, `gmail_lire`, `mode_humour`, `changer_cerveau`) sont multiplateformes (📖). `core/plugin_loader` isole les plugins défaillants : un plugin cassé ne bloque pas les autres.

---

## 4. Dépendances système

Colonne « Ici » : ✅ installé · ❌ absent · ❓ non vérifié. « O » obligatoire, « F » facultatif.

| Fonctionnalité | Paquet apt (Ubuntu 26.04) | O/F | Ici | Notes |
|---|---|---|---|---|
| Interface Qt6 | `libxcb-cursor0`, `libxkbcommon-x11-0`, `libxcb-icccm4`, `libxcb-keysyms1`, `libxcb-shape0`, `libxcb-xinerama0`, `libegl1`, `libgl1` | O | ✅ tous | PyQt6 embarque Qt ; ces bibliothèques servent au plugin `xcb`. Pour le plugin `wayland` natif : à confirmer avec `QT_DEBUG_PLUGINS=1` (⚠️). |
| Audio et micro | `libportaudio2` | O | ✅ | `portaudio19-dev` et `libasound2-dev` **inutiles** : ils ne servent qu'à compiler PyAudio ; `sounddevice` charge la bibliothèque dynamique. |
| Volume | `pulseaudio-utils` (`pactl`) | F | ❌ | Remplaçable par `wpctl` (déjà installé, serveur PipeWire 1.6.2 actif). |
| Synthèse vocale | `piper-tts` (pip, voix `.onnx` en téléchargement) ; `speech-dispatcher` (`spd-say`) ; `espeak-ng` | O (un des trois) | Piper ❌ pip, `spd-say` ✅, `espeak-ng` ❌ | `espeak-ng` n'est pas obligatoire si `spd-say` sert de repli. |
| Reconnaissance vocale | `faster-whisper` (pip) | O (mode local) | ❌ pip | CPU, int8, sans CUDA : fonctionne déjà selon toi sous Windows. |
| Capture d'écran | `gnome-screenshot` (repli de Pillow) ; portail `Screenshot` | F | ❌ | `scrot` ne marche pas sous Wayland natif. `grim` : non supporté par GNOME (aucune installation à prévoir). |
| Clavier / souris | `xdotool` ✅ ; `python3-xlib` (pip, auto) ; `ydotool` (F) | F | ✅ / ❌ | Limites Wayland : cf. 2.4. `wtype` : inutile sous GNOME. |
| Fenêtres | `wmctrl` ✅, `xdotool` ✅ | F | ✅ | X11/XWayland seulement. |
| Notifications | `libnotify-bin` | O (rappels) | ✅ | |
| Rappels | `systemd` (user) ; `at` | O / F | ✅ / ❌ | `at` n'est qu'un second repli. |
| Réseau | `network-manager` (`nmcli`) | F | ✅ | Actions Wi-Fi seulement. |
| Navigateur | `google-chrome` ✅ ; Playwright Chromium (`playwright install chromium`) | O (au moins l'un) | ✅ | À éviter : `--with-deps` sur 26.04 (⚠️). |
| Ouverture | `xdg-utils` (`xdg-open`, `xdg-settings`, `xdg-user-dir`) | O | ✅ | |
| GPU NVIDIA | Pilote propriétaire (580.178 ✅) ; `nvidia-ml-py` (pip) | F | ✅ | Pour la jauge du HUD ; Ollama utilise son propre runtime CUDA. |
| Vidéo / média | `ffmpeg` | F | ✅ | Pour `yt-dlp`, `pydub`. |
| Secrets | `gnome-keyring` / Secret Service + `keyring` (pip) | F | ❓ | Pour remplacer DPAPI. |
| Python | `python3.13` via `uv` (déjà installé : 3.13.14) | O | ✅ | Pas de `python3.13` dans `apt` ; `python3-venv` 3.14 présent. |

---

## 5. Architecture recommandée

### 5.1 Principe
Ne pas multiplier les `if platform.system()` dans une quarantaine de fichiers (c'est déjà le cas dans plusieurs, et ça marche). Isoler **uniquement les endroits où une seule branche Windows existe** derrière une petite couche `core/plateforme/`. Les modules déjà multiplateformes ne sont **pas** réécrits.

```
core/plateforme/
  __init__.py      # choisit l'implémentation une fois (platform.system()) et expose l'API
  base.py          # signatures + comportements par défaut (rien ne plante, message clair)
  windows.py       # code Windows existant, déplacé tel quel (comportement identique)
  linux.py         # nouvelles implémentations (Wayland-aware)
  (macos.py)       # facultatif : repli sur base.py, hors périmètre
```

### 5.2 Interfaces envisagées

| Domaine | API minimale | Remplace aujourd'hui |
|---|---|---|
| Processus | `kwargs_sans_fenetre()` (dict `creationflags` sous Windows, `{}` ailleurs) ; `lancer_detache(cmd)` ; `arreter_sur_port(port)` | 9 `creationflags` en dur, `netstat`/`taskkill`, `pythonw.exe` |
| Navigateur | `ouvrir_en_fenetre_app(url, profil)` ; `ouvrir_url(url)` | `ShellExecuteW` + `CHROME` (3 fichiers) |
| Fenêtres | `trouver_fenetre(titre)` ; `activer(fenetre)` ; `fermer(fenetre)` ; renvoie « non supporté » explicite | `placement.py`, `pygetwindow` |
| Entrées | `touche_globale(nom, rappel)` ; `frappe(texte)` | `core/hotkey.py`, `GetAsyncKeyState`, `RegisterHotKey` |
| Audio système | `volume_get/set/mute()` | branches de `computer_settings.py` |
| Notifications | `notifier(titre, message)` | `reminder.py` (déjà bon) |
| Applications | `lister_applications()` ; `lancer(nom)` | `index_pc.py`, `open_app.py` |
| Chemins | `documents()` ; `bureau()` ; `donnees()` | `_documents()` de `_cerveau_commun.py`, `_get_desktop_dir` |
| Chiffrement | `chiffrer(texte)` / `dechiffrer(valeur)` | `core/coffre.py` (DPAPI) |
| Démarrage auto | `autostart(actif)` | `ui.py:5230-5290` (déjà bon) |

### 5.3 Avantages et inconvénients

| | Option A : gardes locales (`if _OS == …`) | **Option B : couche additive (recommandée)** | Option C : refonte complète |
|---|---|---|---|
| Taille du diff | Petit par fichier, mais éparpillé | Moyen, concentré dans un module neuf | Très grand |
| Risque de régression Windows | Faible | **Faible** : le code Windows est déplacé à l'identique, ou laissé en place | Élevé |
| Conflits avec le dépôt amont (très actif : 47 commits en 16 jours, `ui.py` 5 900 lignes, `main.py` 2 978) | Moyens | **Faibles** si les sites d'appel ne changent que d'une ligne | Très élevés |
| Chance d'acceptation d'une PR | Moyenne | **Bonne** (petites PR indépendantes) | Faible |
| Testabilité | Difficile (branche dépend de l'OS) | **Bonne** (on teste `linux.py` seul, avec des faux) | Bonne |
| Lisibilité à long terme | Dégrade | **Bonne** | Excellente, mais coût élevé |

**Recommandation** : option B, appliquée **au fil des lots**, une interface à la fois, seulement quand le lot en a besoin. On ne crée pas une API sans utilisateur. Les modules déjà multiplateformes (`computer_settings`, `browser_control`, `reminder`, `audio_devices`) restent intacts, sauf pour y brancher un repli Linux manquant.

### 5.4 Garde-fous de compatibilité Windows
- Aucune suppression de fonction Windows ; les branches Windows sont déplacées sans modification, ou laissées sur place.
- Chaque nouvelle fonction retourne le comportement actuel sous Windows (test : `platform.system` simulé en « Windows » → mêmes arguments qu'avant).
- Baseline des tests lancée **avant** toute modification (l'auteur d'une PR amont signale 9 échecs préexistants dus à des dépendances optionnelles absentes).

---

## 6. Principes appliqués dans ce plan
- Windows non dégradé ; aucune fonction supprimée.
- Pas de réécriture des fonctions déjà multiplateformes sans justification (cf. 5.3).
- Aucune clé API, mémoire ou cerveau utilisateur touché : `config/api_keys.json`, `memory/`, `~/Documents/Cerveau` hors périmètre.
- Wayland n'est pas remplacé par Xorg (non disponible de toute façon).
- Ollama **déjà installé** : ne jamais l'installer ni le mettre à jour automatiquement.
- Dépendances obligatoires séparées des options.
- Le portage fonctionnel et le packaging ne sont pas mélangés : l'installateur est le dernier lot.

---

## 7. Plan de développement par lots

Chaque lot est indépendant et livrable seul. Pas de commit sans ta relecture.

### Lot 0 : Baseline (préalable, aucune modification)
- **Fichiers** : `tests/*`.
- **Action** : environnement jetable (`.venv` 3.13 via `uv`), exécuter la suite de tests actuelle avec `QT_QPA_PLATFORM=offscreen` et noter les échecs **avant** toute modification.
- **Risque** : échecs préexistants liés aux dépendances optionnelles.
- **Validation** : liste « avant » figée, utilisée pour prouver l'absence de régression.

### Lot 1 : Démarrage de l'interface
- **Fichiers** : `setup.py` (repères Linux), `galaxie/server.py` (`ouvrir_fenetre`, `ouvrir_adresse`), `galaxie/placement.py` (retours sûrs hors Windows), `plugins/cerveau_galaxie.py`, `cerveau_tableau.py`, `cerveau_hologramme.py`, `galaxie/cerveau_carte.py` (suppression des `creationflags` hors Windows), `core/plateforme/` (processus + navigateur).
- **Modifications** : Chrome détecté (`google-chrome`, `chromium`), ouvert en `--app` avec un profil à part ; suivi du processus pour l'extinction ; `creationflags` seulement sous Windows ; `ouvrir_adresse` via `xdg-open` ; `cerveau_carte` sans `creationflags`.
- **Risques** : Chrome sous Wayland (Ozone) ; Chrome déjà ouvert capture le lancement ; profil `.fenetre-chrome` à ignorer dans git ; interface Qt cachée.
- **Tests** : unitaires avec `platform.system` simulé (Windows : mêmes arguments qu'avant ; Linux : pas de `creationflags`) ; fonctionnel : lancement de bout en bout.
- **Critère** : `python main.py` sous Python 3.13 ouvre la galaxie dans Chrome en mode application, sans traceback ; fermer la fenêtre éteint Jarvis ; tests de baseline identiques.
- **1b (non bloquant)** : même test en Python 3.14.

### Lot 2 : Audio et micro
- **Fichiers** : `core/audio_devices.py`, `main.py` (périphériques), `memory/config_manager.py`.
- **Modifications** : aucune a priori ; correction seulement si la sélection Pulse/PipeWire échoue.
- **Risques** : PortAudio et PipeWire ; le micro Jabra et la webcam exposent deux entrées audio.
- **Tests** : script de diagnostic (liste des appareils, boucle 3 s) ; tests existants.
- **Critère** : micro et haut-parleurs corrects dans la page ; jauge de niveau vivante.

### Lot 3 : Gemini Live
- **Fichiers** : `main.py`, `core/gemini.py`.
- **Modifications** : aucune a priori.
- **Risques** : écho, latence, jeton de l'API.
- **Tests** : session de 2 minutes avec clé de test.
- **Critère** : dialogue vocal fluide ; l'outil `open_app` ou `browser_control` répond.

### Lot 4 : Synthèse et reconnaissance vocales locales
- **Fichiers** : `core/cerveau_local.py` (`VoixLocale`, `PROGRAMME_STUDIO`, `ouvrir_studio`), `core/oreilles_locales.py`.
- **Modifications** : sous Linux, repli `spd-say`/`espeak-ng` après Piper ; `VoixStudio` ignorée sauf Windows (ou URL configurable) ; documentation du téléchargement de la voix Piper.
- **Risques** : voix Piper à télécharger ; latence `spd-say` ; Whisper CPU.
- **Tests** : unitaires sur le choix de la voix (dispatch), manuel : phrase audible.
- **Critère** : `nouvelle_voix()` renvoie une voix audible ; transcription fiable d'une phrase française.

### Lot 5 : Ollama et cerveau local
- **Fichiers** : `core/cerveau_local.py` (`pret`), `core/llm_client.py`, `plugins/changer_cerveau.py`.
- **Modifications** : `pret()` portable (chemin Ollama sous Linux, sans toucher à l'installation) ; message clair si le modèle voulu manque, avec la liste des modèles installés ; réglage `cerveau_local_modele` documenté.
- **Risques** : mémoire GPU de la GTX 1070 (8 Go) selon le modèle.
- **Tests** : `pret()` avec faux serveur HTTP ; manuel : « passe sur ton cerveau local ».
- **Critère** : première phrase en moins de quelques secondes avec `qwen3:8b` ; retour au cloud fonctionnel.
- **Hors portage** (lot séparé) : donner des outils au cerveau local (règles puis tool-calling). C'est une évolution fonctionnelle, pas du portage.

### Lot 6 : Fonctions système
- **Fichiers** : `actions/computer_settings.py` (repli `wpctl`), `actions/open_app.py` (table Linux : `gnome-text-editor`, `gnome-calculator`, `nautilus`), `core/coffre.py` (`keyring`), `index_pc.py` (version Linux, `.desktop`), `actions/reminder.py`.
- **Risques** : `keyring` sans trousseau déverrouillé ; index trop gros ; `systemd-run` en session.
- **Tests** : unitaires avec faux `subprocess` ; manuel : volume, rappel, « ouvre la calculatrice ».
- **Critère** : volume, rappels et ouverture d'applications fonctionnent ; Windows inchangé.

### Lot 7 : Graphique et Wayland
- **Fichiers** : `core/hotkey.py`, `main.py` (Échap), `actions/screen_processor.py`, `plugins/montre_ou_cliquer.py`, `plugins/enregistrer_ecran.py`, `actions/computer_control.py`, `plugins/youtube_controle.py`.
- **Modifications** : raccourcis globaux via portail `GlobalShortcuts` (sinon boutons de la page) ; capture d'écran via portail `Screenshot` avec repli `gnome-screenshot` ; messages d'indisponibilité explicites pour les fenêtres natives ; enregistrement d'écran selon `ScreenCast` (optionnel).
- **Risques** : le plus risqué : autorisations utilisateur, dépendance D-Bus (`jeepney` ou `dbus-fast`), comportement différent selon GNOME.
- **Tests** : unitaires avec faux D-Bus ; manuel : capture non vide, raccourci détecté.
- **Critère** : capture d'écran et push-to-talk utilisables, ou limite annoncée clairement.

### Lot 8 : Plugins
- **Fichiers** : `plugins/*`.
- **Modifications** : passer chaque plugin affecté dans la grille « fonctionne / dégradé annoncé / non supporté annoncé ».
- **Critère** : la liste des plugins au démarrage ne contient plus d'erreur ; chaque plugin renvoie un résultat ou un message d'indisponibilité.

### Lot 9 : Installateur et packaging (dernier)
- **Fichiers** : nouveaux `install.sh`, `lancer-jarvis.sh`, `jarvis.desktop`, `outils/installer-cerveau-local.sh`.
- **Contenu** : détection d'Ubuntu ; paquets apt facultatifs listés en §4 ; Python 3.13 via `uv` (pas de PPA) ; `.venv` ; `requirements.txt` ; `playwright install chromium` **sans** `--with-deps` ; cerveau vierge dans `~/Documents/Cerveau` seulement s'il manque ; **détection d'Ollama sans réinstallation** ; clé Gemini saisie sans écraser l'existante ; icône et `.desktop`.
- **Risques** : droits `sudo` ; mise à jour qui écrase les réglages ; cas sans `uv`.
- **Tests** : installation propre dans un conteneur ou une VM Ubuntu 26.04 ; ré-exécution idempotente.
- **Critère** : une installation propre se lance depuis le `.desktop`, et une seconde exécution conserve la clé, la mémoire et le cerveau.

---

## 8. Risques et points restant à valider

### 8.1 Constatés (✅)
- `ctypes.windll` et `creationflags` plantent sous Linux : à neutraliser avant tout (lot 1).
- Pas de session Xorg sur Ubuntu 26.04 : le plan ne dépend pas de Xorg.
- `pactl` absent ; pas de rétroéclairage ; `qwen3.5:9b` non installé ; Chrome Windows codé en dur alors que `google-chrome` est présent.

### 8.2 Lus mais non exécutés (📖)
- Les pertes fonctionnelles décrites en 2.2, 2.3 et 2.4 reposent sur la lecture du code ou des sources des dépendances (`pygetwindow`, `pyautogui`, `mss`, `Pillow`).
- Les branches Linux de `computer_settings`, `reminder`, `open_app` et `browser_control` existent mais n'ont **jamais** été exécutées ici.

### 8.3 À tester (⚠️)
1. Démarrage complet de Jarvis sous Python 3.13 puis 3.14 (étape 2).
2. Choix `wayland` ou `xcb` pour Qt, et fenêtre de saisie de la clé Gemini.
3. Conflit `opencv-python` / PyQt6 (plugins Qt embarqués) ; essayer `opencv-python-headless`.
4. Qualité de la capture d'écran `mss` sous XWayland (image noire ou partielle ?) et comportement de `PIL.ImageGrab`.
5. Sélection des périphériques audio PipeWire (micro Jabra) et écho avec les haut-parleurs.
6. `playwright install chromium` sur Ubuntu 26.04 (non listée officiellement).
7. Utilisation du portail `GlobalShortcuts` depuis Python (bibliothèque D-Bus à choisir).
8. `systemd-run --user --on-calendar` en session graphique ; `pkexec`/`ufw` pour le dashboard.
9. Mémoire GPU : `qwen3:8b` ou `qwen3.5:9b` sur 8 Go avec Whisper CPU.
10. Comportement de `keyring` sans trousseau GNOME déverrouillé.

### 8.4 Décisions à prendre par toi
1. **Python 3.13 d'abord** (recommandé), puis 3.14 en second essai ?
2. **Wayland assumé** avec fonctions dégradées annoncées, plutôt que d'implémenter tous les portails dès le début : OK ?
3. Le **lot 5 hors portage** (outils du cerveau local) : après le portage, ou en parallèle sur une branche séparée ?
4. Quelles **PR séparées** proposer au mainteneur, sachant que les PR externes #2 et #3 restent sans réponse ?

### 8.5 Limites de cet audit
- Aucune exécution de Jarvis lui-même ; les statuts 📖 ne valent pas test.
- La résolution des dépendances (`uv pip compile`) ne prouve pas que les wheels s'importent ou fonctionnent : seule l'étape 2 le fera.
- La compatibilité macOS n'est pas auditée.

---

**Prochaine étape (2)** : sur validation explicite de ce rapport, créer le `.venv` Python 3.13, installer les dépendances et réussir le premier lancement (lot 0 puis lot 1). Rien de plus ne sera entrepris avant ton accord.


---

## 9. Procédure de lancement (Ubuntu 26.04 / GNOME Wayland)

Audit en lecture seule du 18/11/2026. Aucun lanceur Linux n'existe dans le dépôt (seul `Lancer-Jarvis.bat`, Windows).

- Point d'entrée : `main.py` (`main()`).
- Commande : `cd /dataSSD/travailJerome/jarvis-fr && .venv/bin/python main.py` (Python 3.13.14, venv inutile à activer).
- Variables optionnelles : `JARVIS_PTT_CHORD` (touche push-to-talk), `JARVIS_STATE_DIR`, `JARVIS_LOG_DIR`. Ne pas forcer `QT_QPA_PLATFORM` (réservé aux tests).
- Prérequis : service Ollama actif (modèle `qwen3:8b`), `gemini_api_key` présente dans `config/api_keys.json`, `~/.local/share/applications/io.github.jeromecamilleri.JarvisFR.desktop` (app id des portails), jeton `~/.local/state/jarvis-fr/remotedesktop.json`.
- Arrêt : « Jarvis, éteins-toi » ou fermeture de la fenêtre ; traces dans `~/.local/state/jarvis-fr/logs/arrets.log`. Journal : `jarvis.log`.

## 10. Bilan de la recette fonctionnelle (18/11/2026)

| Id | Test | Résultat |
|---|---|---|
| A1 | Lancer Jarvis | Réussi |
| A2 | Vérifier Galaxie | À tester |
| A3 | Fermer Jarvis | Réussi |
| A4 | Relancer Jarvis | Réussi |
| B1 | Périphériques audio | Réussi |
| B2 | Push-to-talk | **Échec** |
| B3 | Conversation Gemini Live | Réussi |
| B4 | Arrêter la conversation | À tester |
| B5 | Plusieurs échanges | Réussi |
| C1 | Bascule vers Qwen3:8B | Réussi |
| C2 | Question simple en local | Réussi |
| C3 | Retour à Gemini Live | Réussi |
| C4 | Bascules répétées | **Échec** |
| D1 | Synthèse vocale locale | Réussi |
| D2 | Reconnaissance vocale | Réussi |
| D3 | Interruptions | Réussi |
| E1 | Ouvrir l'éditeur de texte | **Échec** |
| E2 | Ouvrir la calculatrice | Réussi |
| E3 | Ouvrir le gestionnaire de fichiers | Réussi |
| E4 | Chrome en mode application | Réussi |
| E5 | Volume | Réussi |
| E6 | Rappels | Réussi |
| E7 | Mode sombre | Réussi |
| F1 | Saisie de texte (fenêtre native) | Réussi |
| F2 | Raccourcis clavier | Réussi |
| F3 | Placement de fenêtre | Réussi |
| F4 | Action souris indisponible | Réussi |
| F5 | Capture d'écran | **Échec** |
| G1 | Coffre GNOME Keyring | À tester |
| G2 | Refus RemoteDesktop | À tester |
| G3 | Permissions | À tester |

Total : 22 réussis, 4 échecs, 5 à tester sur 31.

### Échecs à analyser (causes non encore investiguées)
- **B2** push-to-talk : le test unitaire et l'essai réel du portail GlobalShortcuts passaient. À vérifier : état du portail dans `jarvis.log`, touche réellement acceptée par GNOME (Ctrl+Espace ?), conflit avec le raccourci de fenêtre.
- **C4** bascules répétées cloud ↔ local.
- **E1** éditeur de texte (`gnome-text-editor` est installé en `/usr/bin`) : voir `jarvis.log` et `core/apps_linux.py`.
- **F5** capture d'écran : probablement l'autorisation du portail Screenshot ou `_screenshot` de `computer_control.py`, qui n'a pas de branche portail.

### Procédures pour les tests restants (G, A2, B4)
- **G1 coffre** : dans un terminal, `.venv/bin/python -c "from core import coffre; print(coffre.etat())"` doit afficher `disponible`. Verrouiller ensuite le trousseau (Mots de passe et clés → verrouiller) et relancer : `verrouille`, sans blocage de plus de ~20 s. Aucun secret n'est affiché.
- **G2 refus RemoteDesktop** : renommer temporairement `~/.local/state/jarvis-fr/remotedesktop.json` (sans l'ouvrir), lancer Jarvis, demander une frappe, refuser dans la fenêtre GNOME : message explicite attendu, pas de redemande en boucle. Restaurer le fichier ensuite.
- **G3 permissions** : `stat -c '%a %n' ~/.local/state/jarvis-fr/remotedesktop.json config/api_keys.json` : 600 attendu pour le jeton.
- **A2 Galaxie** : ouvrir `http://localhost:4719` pendant que Jarvis tourne.
- **B4** : arrêter la conversation par la commande vocale ou le bouton micro, et vérifier que la session se ferme.
