# Journal des versions

## 1.1.1 — Revue de sécurité (12 novembre 2026)

Une revue de sécurité rapide du code (lecture seule, ce n'est pas un audit officiel) a trouvé deux points à renforcer. Ils sont corrigés, avec un test écrit avant chaque correction.

**Sécurité**
- **Ouvrir une application** : le nom donné par l'assistant n'est plus jamais passé à un interpréteur de commandes. Un programme est lancé par son chemin, un lien par `os.startfile` ; les noms avec caractères spéciaux et les liens dangereux (`file:`, `javascript:`, `ms-msdt:`…) sont refusés.
- **Télécommande du téléphone** : 5 mauvais essais de clé bloquent l'appareil 5 minutes (page de connexion et lien du QR code).
- Aucun secret (clé, mot de passe, jeton) n'a été trouvé dans l'historique du dépôt.
- Pas encore fait : n'ouvrir le port de la télécommande que lorsqu'on la demande.

Pour l'avoir : relance la ligne d'installation (elle ne touche ni à ta clé, ni à ta mémoire, ni à ton cerveau).

## 1.1 — La Galaxie, Jarvis OS et le cerveau local

**Nouveau**
- **La Galaxie** : ton cerveau en étoiles (recherche, filtres, 2D/3D), avec le cœur J.A.R.V.I.S. qui réagit à la voix. Elle remplace l'ancien grand cercle bleu, supprimé.
- **Jarvis OS** (`http://localhost:4719/tableau`) : le tableau de bord du cerveau (tâches, routines, promesses, séances, rappels, objectif de 90 jours), en lecture seule.
- **Bouton MICRO** sur les deux pages : couper et remettre le micro d'un clic.
- **Mode FOCUS** avec un bouton « Quitter le focus » toujours visible (ou Échap).
- **Le cerveau local** (Ollama + Whisper) : « Jarvis, passe sur ton cerveau local » pour discuter sans Internet.
- **Le cerveau en hologramme** (HOLO), commandé à la main avec une webcam ou à la souris.
- Chronomètre de blocage : `jarvis.log` note l'heure des figements (`[Chrono]`).

**Corrigé**
- Le briefing du matin ne répète plus de vieux articles : articles récents seulement, fil RSS officiel de France Info.
- Fermer la Galaxie éteint Jarvis, qui finit sa phrase d'au revoir.

**Retiré**
- L'ancienne interface bleue (grand cercle, panneaux, circuits) et la musique d'ouverture.

## 1.0 — Jarvis FR
Première édition française de Mark LV : installation en une ligne, premier cerveau vierge, Gmail en lecture seule.

Crédit : Jarvis FR est une œuvre dérivée de *Mark LV* de FatihMakes (CC BY-NC 4.0). Édition non officielle.
