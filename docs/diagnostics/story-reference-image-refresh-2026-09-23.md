# Histoires — remplacement des images et relance MiniMax

## Problème confirmé

Dans « Peau neuve, regard neuf », la fiche Pêchette contenait la nouvelle image, mais les six préparations et ateliers MiniMax conservaient l’ancienne. L’interface signalait « À actualiser » tout en permettant une relance manuelle de cet ancien atelier. Les deux dernières tentatives observées étaient annulées : l’audit confirme les références enregistrées, pas un nouveau rendu terminé.

## Comportement du patch

- Si seuls les fichiers image changent, une relance manuelle ou par la chaîne crée une nouvelle préparation de fabrication et un nouvel atelier de rendu. Même prompt, mêmes correspondances Picture, mêmes paramètres de rendu ; aucun appel Plan/Rédacteur supplémentaire.
- La comparaison porte sur le contrat complet de préparation. Changement de rôle, ordre, personnage, intention, dialogue, continuité ou réglage du prompt : la relance manuelle demande une nouvelle préparation. Le lancement explicite de la chaîne conserve sa préparation automatique habituelle.
- Le contrôle est effectué côté serveur. La chaîne vérifie aussi les entrées juste avant de créer un nouvel essai. Un essai déjà créé/mis en file conserve les images de son instantané.
- Les anciennes préparations, leurs images et leurs essais restent inchangés. Le nouvel atelier conserve la provenance du prompt et un lien vers l’atelier parent. Schéma H3 16 ; lecture des schémas 1 à 15 conservée. Retrouver l’atelier depuis l’ancienne session renvoie toujours l’atelier d’origine.
- Le bandeau nomme les images modifiées ; bouton « Générer avec les nouvelles images », puis préparation « Images actualisées · prompt conservé ». L’interface suit la nouvelle préparation lorsqu’on consultait la plus récente ; une ancienne préparation choisie explicitement reste consultable.
- Les échanges LLM consultables restent ceux qui ont produit le prompt conservé, avec leurs références historiques. La nouvelle préparation enregistre séparément les images utilisées pour fabriquer la nouvelle vidéo.

Le patch ne déduit pas le contenu visuel d’une image. Si le prompt impose explicitement une ancienne tenue ou apparence, l’action existante « Préparer le prompt » reste utile pour revoir cette description.

## Vérification

Contrôles effectués : syntaxe Python (AST), compilation syntaxique JavaScript sans exécution des scripts, `git diff --check`. Aucun test fonctionnel, LLM, rendu, modification de projet runtime, redémarrage ni publication.

Régressions préparées et non exécutées : actualisation manuelle et en chaîne sans LLM, modification entre préparation et lancement, conservation du prompt/durée/seed/recette et historique, refus des contrats différents et références absentes, persistance et compatibilité H3, API et sélection du nouvel atelier dans le navigateur.

Depuis le worktree actif, à lancer par l’utilisateur :

```powershell
D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_episode_reference_refresh tests.test_episodes_web tests.test_episodes_browser tests.test_h3_render_controls_browser
```

Essai manuel : après la fin des traitements, redémarrer le Lab et faire Ctrl+F5. Ouvrir la dernière préparation de « L’humiliation » et cliquer « Générer avec les nouvelles images ». Vérifier le nouveau rendu, puis sélectionner l’ancienne préparation pour retrouver ses essais. Aucun besoin de refaire le Plan/Rédacteur pour un simple remplacement de l’image de Pêchette.
