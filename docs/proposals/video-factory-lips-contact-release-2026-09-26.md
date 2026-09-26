# Lèvres — dépôt au contact, version du 26 septembre 2026

## Comportement

Le preset demande deux passages complets et distincts, de commissure à commissure : lèvre inférieure puis supérieure en sens inverse. La surface du raisin reste en contact sur chaque trajet. La matière apparaît immédiatement derrière ce contact ; les zones non parcourues restent nues. Pendant le changement de lèvre et après le retrait, aucun nouvel ornement n’apparaît. Le décor déjà posé reste fixe.

Le Plan et le Prompt reçoivent explicitement les trois états à conserver : deux lèvres nues ; bas décoré et haut nu ; deux lèvres décorées. Les deux passages doivent rester des actions distinctes, même au sein d’une phase unique. Les matières et couleurs suivent la référence ; le sourire franc avec dents visibles et la tenue finale sont conservés. Le dépôt remplace la propagation de l’ancien texte. Le son accompagne le frottement réel.

Le changement est limité à LIPS_INTENT dans domain/video_factory.py. La chaîne existante transmet déjà l’intention au Plan et au Writer dans USER INTENTION, ainsi que le plan approuvé dans PLAN TO PRESERVE. Aucun changement des recettes générales, des modèles ou des paramètres de rendu.

## Application

Après le prochain redémarrage habituel du Lab et rechargement de la page, sélectionner les lignes souhaitées dans Préparation et réappliquer le preset **Lèvres**. Cette action reprend les réglages du preset, y compris H3/image de fin, un plan de 10 s, DLSS et Texte IG anglais actifs : conserver ses réglages personnalisés au besoin après application.

Une ligne déjà terminée peut être dupliquée, puis recevoir le preset dans Préparation pour produire un nouvel essai. Les anciennes intentions, les prompts approuvés et les rendus existants ne sont pas modifiés automatiquement. Aucun traitement ni service n’a été lancé par ce patch.

## Version et vérification

- Point de retour Git avant modification : `defb8be`, limité à l’ancien bloc LIPS_INTENT.
- Correctif versionné séparément, sans embarquer les changements KREA2 ni les autres patches usine en cours. Ces commits ciblés ne constituent pas une sauvegarde de tout le checkout non commité.
- Vérification statique : syntaxe Python et différence limitée au bloc du preset ; suivi du passage de l’intention vers le Plan et le Writer. Aucun test fonctionnel exécuté selon AGENTS.md, aucun appel LLM ou rendu de validation.
- Comparatif utilisateur recommandé : même image et mêmes réglages, vérifier le dépôt immédiat, l’autre lèvre encore nue, l’arrêt hors contact et le sourire final. Le guidage textuel ne garantit pas le respect spatial par le modèle.

Analyse préalable et exemples : [Diagnostic](video-factory-lips-contact-2026-09-26.md).
