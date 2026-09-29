# Prévisions Usine : références voisines — 28 septembre 2026

## Diagnostic

L’utilisateur constate « Historique comparable insuffisant » sur quatre scènes de « La présentation », puis des dates absentes sur « La piscine des regards » et un total « À préciser » pour le lot de 11 vidéos.

Relevés en lecture seule via les API PC et mobile, puis copie du journal avec partage Windows lecture/écriture/suppression pour ne pas gêner ses remplacements atomiques. Le journal contient 615 mesures : 129 plans, 129 prompts, 122 rendus vidéo, 129 DLSS, 94 textes sociaux et 12 exports. Aucune alerte du journal ni télémétrie périmée au relevé.

Les quatre scènes concernées ont 7 références (un environnement et six références sujet). Même durée 10 s, format portrait, 0,9 MP, 9 étapes, recette effective et LoRA que les configurations historiques voisines. L’ancienne règle exigeait une égalité de toute la liste des rôles, donc de leur nombre, pour la vidéo et le DLSS.

À tous les autres réglages identiques :

| Références | Mesures vidéo | Médiane vidéo | Mesures DLSS | Médiane DLSS |
| --- | ---: | ---: | ---: | ---: |
| 2 | 1 | 276,8 s | 2 | 157,4 s |
| 3 | 10 | 292,8 s | 14 | 154,8 s |
| 4 | 9 | 310,5 s | 9 | 155,3 s |
| 5 | 2 | 322,6 s | 3 | 158,6 s |
| 6 | 2 | 406,2 s | 1 | 141,8 s |
| 7 | 0 | — | 0 | — |

Il existe donc 24 mesures vidéo et 29 DLSS proches. Les cinq scènes du second groupe ont déjà leurs propres estimations ; leurs dates sont inconnues par dépendance aux quatre scènes précédentes. Dans la simulation, une étape inconnue bloque sa machine et les dates dépendantes ; le total devient inconnu si un membre du lot ne peut pas être daté. Ce n’est pas un nouveau type de traitement ni un manque global de données.

## Correction

Dans `domain/factory_timing.py`, sans changer le format du journal :

- Conserver les mesures strictement identiques en priorité.
- Vidéo REF2V : à défaut, accepter une seule référence en plus ou en moins, avec les mêmes types de rôles. Tous les autres critères restent identiques, notamment machine, recette/version/empreinte, modèle, LoRA, géométrie, durée et paramètres de calcul.
- DLSS : à défaut, utiliser les mêmes caractéristiques et contrat de traitement sans partitionner selon les références de la scène source. Le DLSS traite la vidéo déjà rendue.
- Replis signalés par une confiance faible, une fourchette élargie et un motif indicatif transmis aux interfaces PC/mobile.
- Aucun repli arbitraire si les paramètres de calcul diffèrent ou si la variation de références vidéo est plus éloignée. Aucune réécriture des mesures, modification d’ordonnancement ou de protection thermique.

Pour les quatre scènes à 7 références, les deux observations vidéo à 6 références deviennent éligibles ; les 29 observations DLSS deviennent éligibles. Ces nombres décrivent le relevé archivé, pas une validation fonctionnelle du nouveau code ni une promesse de durée exacte.

## Validation et activation

Syntaxe Python et compilation sans exécution applicative vérifiées. Quatre scénarios de régression préparés : repli adjacent et priorité exacte ; frontières de compatibilité ; DLSS indépendant des références ; prévision globale et scènes suivantes sans mutation de l’état.

Tests NON exécutés conformément à AGENTS.md du checkout actif. Depuis ce checkout, pour validation par l’utilisateur :

```powershell
$env:PYTHONPATH = "D:/Code/panelforge-krea2-flux/src"
D:/Code/panelforge/.venv/Scripts/python.exe -m unittest tests.test_factory_monitoring
```

Aucun redémarrage, génération, appel LLM, commande de file, notification ni écriture du runtime. Le correctif sera chargé au prochain démarrage choisi de PanelForge ; le processus actuel conserve son code en mémoire. Aucune version Git ni publication créée pour ce correctif.

Preuves et sauvegardes : `D:/Code/panelforge/.agent/diagnostics/factory-eta-history-20260928/` : relevés API, copie du journal, statistiques, versions avant correction et diffs.
