# Usine à vidéo

Implémentation du 25 septembre 2026 dans le checkout `D:\Code\panelforge-krea2-flux`, branche `feature/video-factory-2026-09-25`.

## Utilisation

Les boutons violets **Envoyer à l’usine** sont disponibles sur les images KREA 2 (en remplacement de Replacer dans…), à côté de Créer le parcours dans H3 et REF2V, et à côté de Lancer prompts + vidéos dans Histoires. L’envoi copie les données dans Préparation, sans création de parcours ni appel LLM ou génération vidéo. Le retour Ajouté à l’usine permet d’ouvrir la file ; l’atelier reste affiché. Un double envoi identique retrouve la même ligne. Dupliquer permet une nouvelle production volontaire.

- **Préparation** : chaque ligne affiche Prêt ou À compléter. Sélectionner une vidéo ouvre les réglages à droite, ou sous la liste sur un écran plus étroit. Une image seule arrive sans intention présumée, avec un rôle à choisir. Lancer la sélection ajoute explicitement les lignes complètes à la production.
- **Production** : vidéos actives et en attente. L’ordre est modifiable avec les flèches de priorité. Modifier une ligne en attente la remet en préparation.
- **Résultats** : vidéos terminées, erreurs et annulations. Cliquer sur Plan, Prompt, Vidéo, DLSS ou Texte IG ouvre le détail et les sorties déjà disponibles. Reprendre les chaînes conserve les étapes réussies.

Une scène correspond à une ligne : cinq scènes d’histoire donnent cinq vidéos, regroupées et sélectionnables ensemble. Les productions sont rattachées aux scènes si les entrées et leur préparation sont restées inchangées. Une scène modifiée entre-temps conserve sa nouvelle préparation ; la vidéo reste accessible dans l’usine avec une indication dans son détail. Les références manquantes d’histoire se corrigent dans la source, puis via Recharger depuis l’histoire.

## Réglages

Exactement quatre presets : Réglages source, Lèvres, Petits hommes, Personnalisé. Une modification devient Personnalisé en conservant l’origine. Réglages source restaure la copie capturée à l’envoi.

- Lèvres : H3, une image de fin, un plan et une intention de mouvement éditable.
- Petits hommes : H3, image de départ, un plan, huit secondes, intervention d’une main géante qui aide les petits personnages. Ce preset reprend les constantes retrouvées dans les anciens parcours H3 ; l’action précise se complète dans l’intention.
- Les deux presets utilisent Bunny et Motion Repair, avec les réglages actuels de fabrication. Ils exigent une seule image et refusent un lot incompatible sans modification partielle.
- Le nombre de plans accepte Auto ou 1 à 6. H3 accepte première / dernière frame ; REF2V conserve les références et leurs rôles.
- Les réglages de rendu et les paramètres avancés sont accessibles depuis l’inspecteur. Modifier seulement la durée de rendu ne réécrit pas un prompt déjà préparé.
- Le DLSS hérite de la source ; il est actif pour les scènes envoyées depuis Histoires et désactivé par défaut pour une nouvelle image ou un nouveau parcours sans réglage source.
- Texte IG est désactivé par défaut. Son activation propose anglais, Gemma 4 local et trois variantes. Le français et le nombre de variantes sont réglables. L’entrée est automatiquement la vidéo H3 produite ; un échec DLSS n’empêche pas Instagram. Le résultat peut être ouvert dans l’atelier Texte IG.

La sélection multiple permet un preset commun, une durée, le nombre de plans, DLSS et Texte IG. Les champs non renseignés restent inchangés. Le retour Annuler restaure les réglages précédents et les résultats dont les entrées correspondent. Les anciennes sorties restent consultables dans l’inspecteur. Une révision par ligne empêche d’écraser une modification concurrente. Le rafraîchissement conserve les brouillons et le focus dans les réglages.

## Ordonnancement et reprise

Le coordinateur existant reste responsable des machines, des files de réservation et des règles thermiques. Pour chaque machine disponible, l’usine cherche la première étape exécutable dans l’ordre des lignes. Une ligne bloquée ne retient pas l’autre machine ; elle retrouve sa priorité dès qu’elle peut avancer. Une seule étape par ligne est active à la fois.

**Pause après les étapes actives** laisse finir les étapes déjà commencées, puis empêche toute étape suivante. La pause persiste jusqu’à Reprendre la file, y compris si l’utilisateur lance de nouvelles lignes. Les éléments en préparation ne partent jamais automatiquement. Il n’y a pas de commande Finir la file puis suspendre.

Annuler arrête l’admission des étapes restantes et demande l’arrêt des travaux H3/DLSS déjà actifs. Une réponse LLM en cours est interrompue au prochain événement du flux. Les sorties reçues avant ou pendant la demande restent accessibles.

La file, les réglages copiés, les révisions et les identifiants des travaux enfants sont enregistrés atomiquement dans `workspace/video_factory/state.json`. Un verrou de processus empêche deux moteurs d’utiliser ce même journal. Les rendus et DLSS déjà identifiés sont réconciliés au redémarrage, même si la file est en pause. Une étape LLM interrompue, ou une étape sans travail enfant enregistré, demande une reprise explicite ; elle n’est pas relancée silencieusement. Les documents de préparation déjà enregistrés sont réutilisés à la reprise.

Le type persistant `kind: video` laisse une place à de futurs blocs. La génération d’histoires ou de nouveaux épisodes comme blocs de file n’est pas incluse dans cette version.

## Validation et mise en service

Contrôles effectués : syntaxe Python, imports des nouveaux modules, analyse syntaxique JavaScript et `git diff --check`. Aucun test fonctionnel ni génération n’a été exécuté, conformément à `AGENTS.md`. Aucun service n’a été redémarré.

Tests ciblés à lancer avec l’environnement Python habituel depuis ce checkout :

```powershell
python -m unittest tests.test_video_factory tests.test_video_factory_web
```

Les tests utilisent des services factices et un répertoire temporaire. La fixture navigateur utilise le Chromium local si disponible, sans serveur ni backend de génération.

La suite projet reste `python -m unittest discover -s tests`. Après le prochain redémarrage habituel du Lab, recharger la page avec Ctrl+F5. Vérifications manuelles utiles : envoyer une image, appliquer Lèvres, activer IG et vérifier anglais / trois variantes ; envoyer une histoire de cinq scènes ; vérifier les cinq étapes visibles ; lancer une petite sélection, mettre en pause et reprendre ; annuler puis reprendre une chaîne avec une vidéo déjà produite.

Sauvegarde avant implémentation : [snapshot-pre-video-factory-2026-09-25](https://github.com/EasyFrag/panelforge/tree/snapshot-pre-video-factory-2026-09-25), commit `8e91ed424ce51b508746ac0d239d9187d8a45c16`.