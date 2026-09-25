# Multilangue : vidéo bloquée avant admission H3 — 25 septembre 2026

## Constat

La copie anglaise `episode-874e7709066e6797c5d02acd1fb5ca34` (Le cafard du costume · English, série L’arnaque au cafard) contient 7 scènes et 14 répliques traduites et injectées. La traduction a réussi. La chaîne `video-chain-f3cdb71b9031497ab9e31e3f4419a059` reste en cours, avec la première scène `prompt_ready` et les six autres `pending`. Sa première tentative `attempt-bfb6751b564742cdbbc6fb2328c6e5f1` est encore `CREATED`, sans `execution_id`. La miniature est exclue de cette chaîne.

Un ancien projet H3, `h3-render-87b3baa87d6841f48d57432fe090f1df`, conserve la tentative `attempt-f22b7ba2e6b3443785ee0e7fc6c780b3` en `QUEUED`, sans `execution_id`. Dernière modification : 24 septembre à 16:04:19 UTC. Il appartient à « L’éclat de la scène », scène 2 « Le barrage de Frambosa », dont la chaîne est interrompue.

Lors du diagnostic, les endpoints en lecture du coordinateur local et de ComfyUI indiquent des files vides et aucun traitement actif. Aucune donnée runtime n’a été modifiée.

## Cause

La réservation FIFO est en mémoire, tandis que l’état QUEUED est persistant. Après interruption du processus, une réservation peut disparaître en laissant cet état enregistré. La récupération H3 réconciliait les états RUNNING et CANCEL_PENDING, mais pas QUEUED. L’admission d’une nouvelle vidéo refusait alors cet ancien travail comme déjà actif. La chaîne d’épisode réessayait toutes les 0,5 secondes sans exposer la raison de l’attente.

## Correctif

- Réconcilier une tentative QUEUED uniquement si elle n’a aucun execution_id, si un coordinateur existe, et si ni réservation FIFO ni worker revendiqué ne la possède. La tentative devient FAILED avec une explication de l’interruption. Prompt et réglages restent disponibles.
- Conserver les véritables réservations et les exécutions soumises. Aucune ancienne vidéo n’est automatiquement renvoyée à ComfyUI.
- Enregistrer et afficher la raison d’une attente derrière un rendu H3 actif ; l’effacer lors de la reprise/admission.
- Pour les scènes multilangues déjà injectées, afficher « en attente du lancement », au lieu d’annoncer un prompt manquant.
- Actualiser la version de chargement de episodes.js.

## Validation

AST des cinq fichiers Python concernés et syntaxe de episodes.js / fixture navigateur vérifiées ; git diff --check réussi. Régressions préparées dans test_h3_render_recovery.py, test_episodes.py et test_episodes_browser.py : réservation abandonnée, protection des tickets actifs et workers, reprise sans réécriture du prompt et affichage multilangue.

Tests fonctionnels non exécutés conformément aux instructions du projet et à la préférence utilisateur. Aucun appel LLM, rendu, redémarrage ou reprise de chaîne effectué.

## Reprise utilisateur

Quand les autres traitements sont terminés : redémarrer le Lab, actualiser avec Ctrl+F5, ouvrir la copie anglaise dans Scènes et cliquer sur « Reprendre la chaîne ». Le service détectera la chaîne interrompue ; les traductions et préparations existantes sont réutilisées. Inutile de recréer une adaptation ou de retraduire.
