# CONTINUITY

## Goal

- Construire PanelForge comme atelier local de canon visuel et de recettes versionnées, réutilisables ensuite pour produire des panels narratifs cohérents.

## Current state

- Works:
  - Image Lab exécute `character.change_view@0.2.0` via ComfyUI avec provenance, comparaison, review humaine et candidats persistants.
  - Prompt Lab fournit observations par image, Brief versionné, streaming, édition/révision, approbations et journal borné des appels LLM.
  - `minimax.h3.protocol@0.1.0` compile caméra, placeholders et balises fragiles. I2V utilise par défaut `minimax.h3.i2v.simple@0.3.0`; `0.2.0` reste son témoin A/B.
  - Ref2V utilise par défaut `undressing.single_shot@0.11.0`; `0.10.0` reste son témoin H3 strict. Le plan supervisé décrit topologie, route physique, prises des mains, états observables et jalons majeurs avant le writer.
  - En `0.11.0`, la seconde image suit `appearance_only_v1`: seules identité et apparence stable alimentent le Brief et le plan; le mapping final interdit aussi tenue, pose, mains, expression, caméra, lumière, décor et composition comme preuves venant de cette image.
  - Une cible caméra optionnelle invalide devient un avertissement en `0.11.0` sans perdre le mouvement typé; `0.10.0` conserve son rejet strict. Les erreurs structurelles restent bloquantes et le candidat brut reste visible.
  - Le journal distingue le statut transport LLM de l’issue applicative `accepted|rejected`. Les anciens stores/sessions/compositions sont migrés en lecture et un run `0.10.0` existant ne devient pas obsolète.
  - Suite complète: 258 tests verts; `git diff --check` propre.
- Broken / missing:
  - I2V `0.3.0`, Ref2V `0.11.0` et Fighter doivent encore être qualifiés par des rendus MiniMax H3 représentatifs.
  - Les runs Ref2V `prompt-528a5d...` et `prompt-81d638...` reconstruisent le décor sans instruction LLM correspondante; le second ajoute un tracking et une transition debout→lit qui amplifient ce risque.
  - Ref2V produit volontairement un format compact éprouvé, pas le contrat Ref2VA officiel à six sections.
  - Une session ne porte qu’une composition; il n’existe ni fork/comparateur A/B intégré ni test navigateur automatisé.

## Decisions

- Le LLM décide la sémantique, la route physique, les timings proposés et la prose; le code compile et valide uniquement les contrats exacts.
- Les recettes publiées restent des témoins immuables. Toute nouvelle sémantique est opt-in via une nouvelle version ou une capability déclarée dans le manifest.
- Les politiques de preuve sont typées, persistées et incluses dans la provenance; aucune projection `appearance_only` ne retombe sur le texte brut en cas de format inconnu.
- Durée, densité et ambiguïtés récupérables sont des avertissements; JSON illisible, ordre impossible, mouvement inconnu ou mapping altéré empêchent la persistance.
- Chaque livrable reste générable, éditable, révisable et approuvable manuellement; aucune chaîne autonome n’est introduite.

## Next steps

1. Rejouer le dernier prompt sur sa durée exacte de 8 s, puis relever la seconde précise du saut de décor.
2. Faire l’A/B avec Picture 2 brute puis recadrée/détourée sur fond neutre, au ratio de Picture 1.
3. Selon le résultat, préparer les références ou versionner un invariant positif de décor et un démarrage de tracking aligné sur le déplacement.

## Risks / open questions

- Un contrat et un prompt plus cohérents réduisent le risque de clipping mais ne garantissent pas la physique du rendu vidéo.
- Le planner propose encore la faisabilité temporelle; le code ne sait pas déterminer universellement la durée naturelle d’un geste.
- Le planner peut encore inventer une mauvaise topologie malgré le cookbook, comme des manches jusqu’aux poignets pour un haut explicitement à manches courtes.
- MiniMax reçoit toujours la seconde image et peut ignorer partiellement la frontière d’apparence; seule la qualification visuelle dira si le verrouillage textuel suffit.
- Les durées supérieures à 15 secondes et le format compact dépendent des capacités réelles du moteur ciblé.
- llama.swap ne fournit pas de pourcentage fiable de chargement; libérer la VRAM peut interrompre un appel en cours.
