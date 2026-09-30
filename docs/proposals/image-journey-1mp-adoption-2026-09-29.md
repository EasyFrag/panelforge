# Validation visuelle du réglage fixe autour de 1 MP — 2026-09-29

L’utilisateur a terminé les quatre étapes de l’essai `journey-trial-3975e2066841523c8c35eb14c888f582`
du parcours `journey-323a50895e5f5c72bf755375b6070023`, puis demandé de conserver le réglage pour les
nouveaux parcours. Les quatre sorties sont enregistrées en 768 × 1376 et chacune alimente la suivante.

Les vues d’ensemble et des recadrages écorce/racines ont été examinés à taille commune. L’ancienne
chaîne durcit fortement les contrastes et transforme les textures en reliefs réguliers et brillants.
La suite à dimensions fixes conserve mieux les grandes fissures, les nuances gris-brun et la mousse,
avec moins d’aspect artificiel. La dernière image reste sensiblement plus proche de la source.

Les ajouts ne sont pas identiques : porte, rambarde, panneau solaire et éclairage diffèrent en forme
ou en placement. Une seed conservée ne rend pas identique un calcul à une autre résolution. Le constat
soutient le choix pratique d’un défaut à 1 MP ; il n’isole pas une cause unique de la dégradation et ne
garantit pas l’absence de dérive sur tous les parcours.

Patch : profil à dimensions fixes uniquement sur les nouveaux parcours ; UX pleine largeur,
bandeau repliable, grille avec retour à la ligne et retrait des deux panneaux d’essai.
Les anciens projets et médias ne sont pas réécrits. L’erreur rouge `call_id` de la capture est celle
conservée dans l’ancien journal ; la signature actuelle utilise déjà `analysis_id`, correction antérieure.

Planches, provenance et diff de tâche : `D:/Code/panelforge/.agent/diagnostics/journey-default-1mp-20260929/`.
Aucun nouvel appel LLM/rendu, test ou redémarrage de service pendant cette tâche.
