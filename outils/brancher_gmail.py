"""Branche Gmail à Jarvis (lecture seule). Lancé par Brancher-Gmail.bat.

Demande l'adresse Gmail et un mot de passe d'application Google, vérifie qu'ils marchent,
puis les garde dans config/api_keys.json (ce fichier n'est jamais partagé).
"""
import getpass
import imaplib
import json
import webbrowser
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"

print("=== Brancher Gmail à Jarvis (lecture seule) ===\n")
print("Il te faut un « mot de passe d'application » Google (16 lettres), PAS ton vrai mot de passe.")
print("1. La validation en deux étapes doit être activée sur ton compte Google.")
print("2. La page pour créer le mot de passe d'application va s'ouvrir : donne-lui le nom « Jarvis ».\n")
input("Appuie sur Entrée pour ouvrir la page Google...")
webbrowser.open("https://myaccount.google.com/apppasswords")

adresse = input("\nTon adresse Gmail : ").strip()
mdp = getpass.getpass("Le mot de passe d'application (il ne s'affiche pas, c'est normal) : ").replace(" ", "")

print("\nVérification auprès de Gmail...")
try:
    m = imaplib.IMAP4_SSL("imap.gmail.com", timeout=20)
    m.login(adresse, mdp)
    m.logout()
except Exception as e:
    print(f"\nÇa n'a pas marché : {e}\nVérifie l'adresse et le mot de passe d'application, puis relance.")
    input("\nAppuie sur Entrée pour fermer.")
    raise SystemExit(1)

try:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
except Exception:
    cfg = {}
cfg["gmail_adresse"] = adresse
cfg["gmail_mot_de_passe_app"] = mdp
CONFIG.parent.mkdir(parents=True, exist_ok=True)
CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
print("\nC'est branché ! Relance Jarvis et demande-lui : « j'ai des nouveaux mails ? »")
input("\nAppuie sur Entrée pour fermer.")
