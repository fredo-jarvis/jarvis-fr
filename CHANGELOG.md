# Journal des versions

## 1.1.3 — Mails, écran et injection de prompt (15 novembre 2026)

Un membre de la communauté a signalé trois points précis. Ils étaient fondés : les voici corrigés, avec des tests.

**Sécurité**
- **Gmail** : le mot de passe d'application n'est plus jamais écrit en clair. Il est chiffré par Windows (la même protection que les mots de passe enregistrés de Windows) : copié ailleurs, le fichier ne révèle rien. Si tu avais déjà branché Gmail, il est chiffré automatiquement à la première lecture de tes mails et la version en clair est effacée. Rappel : ce n'est jamais ton vrai mot de passe Google, et tu peux l'annuler à tout moment sur myaccount.google.com/apppasswords.
- **Écran et caméra** : plus aucune image ne part vers Gemini sans ton accord. Quand tu demandes « regarde mon écran », Jarvis affiche **REGARDER TON ÉCRAN** avec le bouton CONFIRMER ; l'accord vaut 3 minutes pour enchaîner les questions. Même chose pour « montre-moi où cliquer » et la caméra.
- **Injection de prompt** : un mail, une page web, un fichier ou l'écran sont maintenant donnés à l'IA **comme des données entre balises, jamais comme des ordres** (un mail ne peut pas fermer la balise pour s'en échapper), et les consignes de Jarvis le rappellent.
- Pendant 5 minutes après une de ces lectures, toute action qui agit sur le PC ou envoie quelque chose (ouvrir une application, souris et clavier, fichiers, messages, navigateur, réglages, notes du cerveau…) attend ton clic sur **CONFIRMER**. Si c'est bien toi qui l'as demandée, un clic suffit ; si c'est un mail piégé, rien ne se passe.
- Nouveau test : `tests/test_securite_1_1_3.py` (14 vérifications, dont un mail piégé qui demande d'ouvrir une application : rien n'est lancé).

Ce qui change pour toi : un clic sur CONFIRMER avant que Jarvis regarde ton écran, et avant une action juste après avoir lu un mail ou une page. Tout le reste est identique.

Pour l'avoir : relance la ligne d'installation (elle ne touche ni à ta clé, ni à ta mémoire, ni à ton cerveau).

## 1.1.2 — Plus aucun code généré exécuté (15 novembre 2026)

Un membre de la communauté a signalé une faille sérieuse : l'action « tâche libre » du bureau faisait **écrire du Python par Gemini puis l'exécutait** sur la machine, dans un « bac à sable » du même processus. Ce bac à sable se contournait en une ligne, et une page web ou un mail piégé lu par Jarvis pouvait détourner le modèle. Merci à lui pour ce signalement précis et bienveillant.

**Sécurité**
- **Bureau** : plus aucun code écrit par l'IA n'est exécuté. Les tâches libres passent par les outils nommés qui existaient déjà (souris et clavier, fichiers, applications, réglages), dont les arguments sont vérifiés. Fond d'écran, rangement, nettoyage, liste et statistiques du bureau fonctionnent comme avant.
- **Agent développeur et assistant de code** : rien n'est lancé avant ta **confirmation à l'écran** (le bouton CONFIRMER, que l'IA ne peut pas actionner à ta place). L'écran indique le projet, la commande de lancement et les bibliothèques qui seront installées.
- La commande de lancement d'un projet doit être un simple `python <fichier du projet>` ou `node <fichier du projet>` ; tout le reste est refusé.
- Les noms de bibliothèques suspects (options pip, liens, chemins) sont refusés, et **aucune bibliothèque devinée** à partir d'un message d'erreur n'est installée automatiquement (protection contre les paquets pièges).
- **Plus aucun `shell=True`** : ouverture de VS Code, luminosité sous Linux et réglage du pare-feu du tableau de bord passent désormais sans interpréteur de commandes.
- Nouveau test : `tests/test_securite_1_1_2.py` (14 vérifications).

Ce qui change pour toi : un clic sur CONFIRMER avant que Jarvis construise ou lance un programme. Tout le reste est identique.

Pour l'avoir : relance la ligne d'installation (elle ne touche ni à ta clé, ni à ta mémoire, ni à ton cerveau).

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
