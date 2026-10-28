# Création Assistée MH V1 — 28 octobre 2026

Version de PanelForge incluant le nouvel atelier **Création Assistée MH** dans
Image Lab. Base : sauvegarde `3e2283dd1908ff524d6bbd69b9b38e828328a9e8`.
Branche : `snapshots/mh-assisted-v1-2026-10-28`.

L’atelier permet de créer des images fixes avec MiniMax H3 Still à partir d’au
moins une référence : une pose, une autre image ou les deux. Il conserve les
presets artistiques existants, les langues anglais/chinois, les directions
artistiques, le choix LLM, la conversation, le prompt éditable et l’historique.
Les réglages de rendu sont propres à MiniMax.

Le sélecteur de poses utilise AI Pose Gallery et regroupe les angles, avec
recherche et filtres. L’index personnel installé contient 288 poses et 1 439 vues.
Les images du catalogue et les données du workspace ne sont pas distribuées
dans cette version. Les références et choix artistiques sont conservés avec
chaque essai. L’enregistrement d’un essai MH comme nouveau preset personnel,
la vidéo, le batch et l’édition de poses restent hors de cette V1.

Voir [le guide de l’atelier](../mh-assisted.md) pour l’utilisation et les tests.
Les contrôles statiques de syntaxe et de cohérence des assets ont réussi.
Les tests n’ont pas été exécutés ; aucun appel LLM ni rendu réel n’a été lancé
pour la validation. L’activation nécessite le redémarrage du Lab puis le
rechargement du navigateur, à un moment compatible avec les productions.

Cette version prolonge la sauvegarde précédente sur une branche dédiée.
La branche de travail `master` et son index sont conservés. Le compteur Git de
l’éditeur continue donc à comparer le dossier à son ancien commit du 19 octobre,
et inclut les évolutions antérieures à MH ainsi que les fichiers locaux non suivis.
