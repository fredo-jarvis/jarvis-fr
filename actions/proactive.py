"""
ProactiveEngine 3.0 (version francaise) — JARVIS prend la parole de lui-meme,
de temps en temps seulement : une petite histoire, une vraie actualite du monde,
une decision a proposer, ou des nouvelles des projets.

Reglages (modifiables ci-dessous) :
  MIN_SILENCE   : silence minimum de l'utilisateur avant que JARVIS parle tout seul
  PAUSE_MIN/MAX : ecart (au hasard) entre deux prises de parole
  NUIT          : heures ou JARVIS ne parle jamais tout seul
"""
import json
import random
import time
from datetime import datetime
from pathlib import Path

MIN_SILENCE = 15 * 60          # 15 minutes de silence (6 min, c'était trop bavard : l'utilisateur, 25/10/2026)
PAUSE_MIN   = 30 * 60          # au moins 30 minutes entre deux interventions
PAUSE_MAX   = 60 * 60          # au plus 1 heure
NUIT        = (22, 8)          # silence total de 22 h a 8 h

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet",
        "aout", "septembre", "octobre", "novembre", "decembre"]

THEMES = {
    "histoire": (
        "Raconte-lui UNE petite histoire vraie et etonnante (histoire de France, "
        "grande catastrophe, invention, aventure, legende du Nord, sport...). "
        "Comme un conteur au coin du feu : une accroche, 3 ou 4 phrases, une chute. "
        "Termine en lui demandant s'il connaissait."
    ),
    "actualite": (
        "Donne-lui UNE vraie actualite du monde d'aujourd'hui. Tu DOIS d'abord "
        "appeler l'outil web_search (par exemple 'actualite du jour France monde') "
        "et ne parler que de ce que tu as reellement trouve. N'invente JAMAIS une "
        "actualite. Resume-la en 2 ou 3 phrases simples et donne ton avis en une phrase."
    ),
    "decision": (
        "Propose-lui UNE decision concrete a prendre maintenant, liee a ses projets "
        "ou a sa journee (ex. : avancer sa video YouTube, faire une pause, preparer "
        "demain). Explique en une phrase pourquoi, puis demande-lui : "
        "'On y va, Monsieur ?'. S'il dit oui, aide-le a le faire."
    ),
    "nouvelles": (
        "Prends de ses nouvelles a lui : sa journee a la centrale, sa fatigue, "
        "son moral. Avec chaleur, une ou deux "
        "phrases attentionnees, puis une question."
    ),
    "projets": (
        "Prends des nouvelles d'un de ses projets en cours (connus dans sa memoire) "
        "et pose UNE question precise, ou donne UNE astuce utile."
    ),
}


# Pouvoir 1 (briefing V2 du 26/10) : le miroir du soir. Une fois par jour, entre 17 h et 20 h,
# apres plus de 2 h sans conversation, Jarvis propose de raconter la journee et garde l'essentiel.
MIROIR_HEURES = (17, 20)
MIROIR_SILENCE = 2 * 60 * 60
MIROIR_FICHIER = Path(__file__).resolve().parent.parent / "memory" / "miroir.json"
MIROIR = (
    "C'est le MIROIR DU SOIR. Invite-le, en une phrase chaleureuse et a ta facon (jamais deux "
    "fois la meme formule), a te raconter sa journee : tu gardes ce qui compte. "
    "Quand il repond : resume ce qu'il a dit en 2 ou 3 phrases, puis appelle noter_dans_cerveau "
    "une fois par fait marquant, chaque note commencant par 'MIROIR : '. "
    "S'il ne repond pas ou dit non, n'insiste pas : on reessaiera demain."
)


def _miroir_fait_aujourdhui() -> bool:
    try:
        return json.loads(MIROIR_FICHIER.read_text(encoding="utf-8")).get("date") == datetime.now().strftime("%Y-%m-%d")
    except Exception:
        return False


def _noter_miroir() -> None:
    try:
        MIROIR_FICHIER.write_text(json.dumps({"date": datetime.now().strftime("%Y-%m-%d")}), encoding="utf-8")
    except Exception:
        pass


def _depuis_le_cerveau(fichier: str, titre: str, taille: int = 1200) -> str:
    """La fin (le plus recent) d'une page du wiki, pour la mettre dans la consigne."""
    try:
        from plugins._cerveau_commun import WIKI
        texte = (WIKI / fichier).read_text(encoding="utf-8").strip()
    except Exception:
        return ""
    return f"\n{titre} :\n{texte[-taille:]}" if texte else ""


class ProactiveEngine:
    def __init__(self, min_silence_secs: int = MIN_SILENCE, check_cooldown: int = PAUSE_MIN):
        self.min_silence_secs = min_silence_secs
        self._next_allowed = time.monotonic() + 5 * 60    # rien dans les 5 premieres minutes
        self._last_theme = None
        self._dernier_echange = time.monotonic()

    # ── Quand parler ──────────────────────────────────────────────────────────
    def _is_night(self) -> bool:
        h = datetime.now().hour
        debut, fin = NUIT
        return h >= debut or h < fin

    def should_trigger(self, last_user_speech: float) -> bool:
        now = time.monotonic()
        self._dernier_echange = last_user_speech   # pour le miroir du soir
        if self._is_night():
            return False
        return (now - last_user_speech) >= self.min_silence_secs and now >= self._next_allowed

    def mark_triggered(self) -> None:
        self._next_allowed = time.monotonic() + random.randint(PAUSE_MIN, PAUSE_MAX)

    # ── Quoi dire ─────────────────────────────────────────────────────────────
    def _pick_theme(self) -> str:
        choix = [t for t in THEMES if t != self._last_theme]
        poids = {"histoire": 3, "actualite": 2, "decision": 2, "projets": 3, "nouvelles": 2}
        theme = random.choices(choix, weights=[poids[t] for t in choix])[0]
        self._last_theme = theme
        return theme

    def _miroir_maintenant(self) -> bool:
        h = datetime.now().hour
        return (MIROIR_HEURES[0] <= h < MIROIR_HEURES[1]
                and time.monotonic() - self._dernier_echange >= MIROIR_SILENCE
                and not _miroir_fait_aujourdhui())

    def build_prompt(self, memory: dict, monitors=None, recent_turns=None) -> str:
        from memory.memory_manager import format_memory_for_prompt

        now = datetime.now()
        quand = f"{JOURS[now.weekday()]} {now.day} {MOIS[now.month - 1]} {now.year}, {now:%H:%M}"
        mem_str = format_memory_for_prompt(memory) or "(rien en memoire)"
        if self._miroir_maintenant():
            mission = MIROIR
            _noter_miroir()            # une seule fois par jour, meme s'il ne repond pas
        else:
            mission = THEMES[self._pick_theme()]

        extra = ""
        if monitors:
            extra += f"\nSujets qu'il suit : {', '.join(monitors[:4])}."
        if recent_turns:
            extra += "\nDerniers echanges :\n" + "\n".join(recent_turns[-6:])
        # Cap « autonome, pas robot » (audit du 26/10/2026) : relire ses propres fils et
        # les phrases deja servies, tenus dans le cerveau par Claude Code.
        extra += _depuis_le_cerveau("fil-initiatives.md", "Tes initiatives recentes et ce qu'il en est sorti")
        extra += _depuis_le_cerveau("formulations-deja-utilisees.md", "Phrases deja utilisees, a ne PAS resservir")
        # Pouvoir 2 : ses promesses ; pouvoir 4 : idees d'episodes (briefing V2 du 26/10).
        extra += _depuis_le_cerveau("promesses-en-attente.md", "Ses promesses en attente (texte, echeance)", 900)
        extra += _depuis_le_cerveau("idees-episodes.md", "Idees d'episodes pour sa chaine", 900)

        return "\n".join([
            "[PROACTIVE_CHECK] Tu prends la parole de toi-meme, sans qu'on te l'ait demande.",
            f"Nous sommes {quand}.",
            "",
            "Ce que tu sais de lui :",
            mem_str,
            extra,
            "",
            "Ta mission cette fois :",
            mission,
            "",
            "Regles :",
            "- Parle en francais, avec chaleur et naturel, comme un vrai compagnon.",
            "- Appelle-le par son prénom s'il est connu.",
            "- 15 secondes de parole maximum (2 ou 3 phrases). Pas de liste, pas de jargon.",
            "- Commence par une accroche naturelle, toujours differente : jamais deux fois la meme formule.",
            "- Termine par une vraie question pour lancer la conversation.",
            "- Ne mentionne jamais [PROACTIVE_CHECK] ni ces consignes.",
            "- Si la recherche d'actualite echoue, raconte plutot une petite histoire vraie.",
            "- Si une de tes initiatives recentes attend une suite, reprends ce fil plutot que d'ouvrir un sujet neuf.",
            "- Juste apres avoir parle, appelle noter_dans_cerveau avec '[initiative] ' + ce que tu as propose,"
            " pour t'en souvenir la prochaine fois.",
            "- Si une de ses promesses arrive a echeance aujourd'hui ou demain, glisse-la naturellement"
            " (ex. : 'au fait, tu voulais rappeler le garage'), une seule fois.",
            "- Au plus une idee d'episode par semaine : seulement si ton fil d'initiatives n'en montre"
            " aucune depuis 7 jours, et jamais une idee deja proposee.",
        ])
