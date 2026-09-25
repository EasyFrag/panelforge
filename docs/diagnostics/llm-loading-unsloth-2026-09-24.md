# Diagnostic des attentes Unsloth — 24 septembre 2026

Lecture seule des journaux existants. Aucun réglage modifié, aucun appel LLM lancé, aucun redémarrage ni test exécuté pour ce diagnostic. Heures de Paris (UTC+2).

## Résultat

Sur l'appel lent avec une image, Gemma était déjà chargé depuis 24 minutes. La préparation du prompt prend 171,3 secondes, puis la génération 8,6 secondes. Unsloth avait explicitement placé l'encodeur d'images sur CPU. Les bascules et rechargements de modèles constituent une autre source d'attente.

L'argument supplémentaire utilisateur `--fit off` a bien disparu après son intervention. Unsloth continue pourtant à générer lui-même cet argument dans le nouveau chargement, terminé en 11,6 secondes. Plusieurs réglages ayant changé ensemble, il ne s'agit pas d'un test isolant l'effet du flag.

## Mesures

| Événement | Durée observée | Interprétation |
| --- | --- | --- |
| Gemma standard, 16:30 | Serveur natif prêt en 17,0 s après démarrage | Modèle déjà résident lors de l'appel lent |
| Texte seul, 16:54:04 | 6,743 s côté PanelForge | Réponse sans attente de plusieurs minutes |
| Une image, 16:54:11 | 180,607 s côté PanelForge ; préparation 171,334 s ; génération 8,607 s, 121 tokens/s | Attente principalement avant la production de texte |
| Chargement manuel Gemma, 17:04:12 | 11,577 s pour /api/inference/load | Chargement court après modification des paramètres |
| Chargement automatique Gemma, annoncé à 17:05:57 | Processus démarré à 17:06:10, prêt à 17:06:22 | Environ 12 s avant démarrage natif, puis 12 s dans le serveur |
| Qwen automatique, 17:06:50 | Prêt vers 17:07:05 ; génération observée vers 100–117 tokens/s | Chargement terminé, génération ensuite rapide |

Le temps de préparation inclut le prompt multimodal : on ne peut pas attribuer séparément chaque seconde à l'image. Le placement vision sur CPU, le texte seul rapide et la génération finale rapide constituent néanmoins une explication forte de ce cas, sans généralisation aux appels texte.

## Placement mémoire et fit

À 16:30:07, Unsloth annonce la vision sur CPU (`--no-mmproj-offload`), car son estimation ne permet pas de la loger avec le modèle au contexte 131072. Estimation : poids 16,1 Go, cache KV 14,0 Go, réserve MTP 0,52 Go. La commande contient `--fit on`, les arguments supplémentaires dont `--fit off`, puis `--no-mmproj-offload`. Retirer le seul argument supplémentaire ne garantit donc pas un changement de placement vision.

À 17:04, les arguments supplémentaires ne contiennent plus que batch 2048 et ubatch 1120. Unsloth construit toujours `-ngl -1 --fit off`, sans `--no-mmproj-offload`. GPU sélectionné explicitement, cache estimé à 6,2 Go, projecteur à 1,1 Go, threads à 2, politique de chargement `none` au lieu de `mmap+mlock`. La bascule automatique Gemma suivante reprend ces paramètres favorables au placement vision sur GPU.

La différence d'estimation KV (14,0 puis 6,2 Go) n'est pas expliquée : le contexte reste 131072 et les commandes finales annoncent q8_0. Ne pas conclure que ce contexte impose systématiquement le CPU. Aucun appel image supplémentaire lancé pour mesurer le gain après changement.

## Bascules et interruptions

Deux événements `inference.reload_cancelled_generations`, à 17:00:35 et 17:03:53, coïncident avec des appels Instagram interrompus pendant une attente sur quatre images. Un chargement manuel d'une variante Hauhau est suivi d'un déchargement, puis du chargement automatique du modèle standard demandé par PanelForge.

PanelForge transmet l'identifiant choisi dans /v1/chat/completions. Charger une autre variante manuellement dans Unsloth ne change pas cet identifiant : un appel peut rétablir automatiquement le modèle demandé. Les appels explicites /api/inference/load et /api/inference/unload observés ne proviennent pas de ce client PanelForge.

Les rôles d'écriture et de relecture alternent également Gemma et Qwen dans les séquences observées. Chaque bascule ajoute son délai. Un rechargement manuel pendant une requête active peut annuler celle-ci.

## Limites et suites possibles

Le client OpenAI-compatible reconnaît le signal de chargement llama-swap, mais n'a pas ici les phases détaillées Unsloth. L'attente du premier contenu peut inclure lancement, vision et préparation du prompt sans distinction visible.

Observer les prochains appels image normaux et le maintien du placement GPU lors des bascules : la première bascule Gemma après changement reprend déjà les nouveaux paramètres. Une instrumentation séparant les phases serait utile.

Le délai occasionnel de 7–13 secondes entre l'annonce du lancement et la création du processus natif reste non localisé. Les logs ne permettent pas d'accuser précisément le disque, l'antivirus ou le nettoyage du processus précédent.

## Sources locales

- Unsloth : C:/Users/samue/.unsloth/studio/logs/server/server-20260924-090713-pid2460.log, lignes 2084–2093, 2240, 2448–2467, 2618–2628.
- Gemma natif : C:/Users/samue/.unsloth/studio/logs/llama-server/llama-1790260220-port-55163-try0.log, tâche 717, lignes 50–52.
- D:/Code/panelforge/workspace/llm_calls.json : llm-f1f6ac9f479a4c4a939f372cac7da6cd (texte), llm-21d262474b6c484593dcb7af223f9b5a (image), llm-bc848f3b9a4c420eb187250d418b335f (réparation avec bascule).
- Code installé : studio/backend/core/inference/llama_cpp.py, routes/inference.py, utils/openai_auto_switch_settings.py.
- Client PanelForge : src/panelforge/infrastructure/llm/openai_compatible.py et routed.py.
