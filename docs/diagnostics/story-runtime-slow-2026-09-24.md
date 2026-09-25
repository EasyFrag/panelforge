# Histoire lente et suivi du raisonnement — 24 septembre 2026

## Incident observé

Projet `story-362831f6ca4b34f0b3d1d6748d8e45fa`, « Caca sur le date — suite ». Un seul appel `story.long.compose@2.2.0`, Qwen3.8-27B local, budget demandé 80 000 tokens. Début 13:35:29 UTC, arrêt 13:47:30 UTC après 721,18 s. 28 815 caractères de raisonnement et aucune réponse finale. Le workflow est bloqué avec `model returned an empty text response`. Aucune boucle de corrections ou validation du scénario n’a eu lieu sur cet appel.

Sources lues : `D:/Code/panelforge/workspace/video_llm_traces/calls/llm-abd644e8c30b4a42b83b42af11fc9c81.json` et JSON du projet. Les traces PanelForge n’enregistrent aucun compte de tokens pour cet appel : leur débit en caractères/s n’est pas une mesure en tokens/s.

## Mesures natives d’Unsloth / llama.cpp

- Dans `C:/Users/samue/.unsloth/studio/logs/server/server-20260924-090713-pid2460.log`, lignes 1171–1181, chargement Qwen Q6 à 13:21:59 UTC : environ 19 571 Mio de VRAM libre, poids estimés 23,6 Go, cache 2,5 Go, réserve MTP 0,73 Go, contexte 72 960 ; `--fit on` et projecteur vision sur CPU. Le manque de VRAM rend le chargement mixte très fortement étayé ; ce journal peu verbeux ne donne pas le nombre exact de couches GPU. Le projecteur vision seul sur CPU ne ralentit pas une génération texte.
- Journal natif `.../logs/llama-server/llama-1790256119-port-51129-try0.log`, tâche 2765 : 201 mesures de génération, médiane du débit récent 11,33 tokens/s, dernière mesure ligne 413 : 7 244 tokens, débit cumulé 11,46 tokens/s. Le contexte a pris environ 90 s avant la génération. Les deux échanges précédents sur cette instance ont terminé à 12,73 et 12,16 tokens/s.
- À 13:47:30 UTC, le journal Unsloth indique `inference.reload_cancelled_generations`, count=1, immédiatement avant la fin du flux, puis un POST `/api/inference/unload`. Cela explique la réponse vide après le raisonnement ; ce n’est pas une preuve d’épuisement des 80 000 tokens.
- Rechargement à 13:51:09 UTC, 32 140 Mio libres, même modèle/quantification/contexte, `-ngl -1 --fit off`, placement complet GPU annoncé. Journal `.../logs/llama-server/llama-1790257878-port-55118-try0.log` : débit autour de 100 tokens/s ; échantillon relevé médiane récente 101,21 tokens/s. D’autres options ont également changé (threads, cache), donc ce n’est pas un benchmark contrôlé isolant un seul paramètre.
- Nous n’avons lancé ni ces appels, ni ces chargements/déchargements. Lecture des journaux et une mesure GPU sans mutation uniquement.

## Garde-fou proposé, non implémenté

1. Contrôle de placement : exiger un modèle texte entièrement sur GPU quand ce modèle est configuré pour tenir sur la carte. Comparer le placement effectif, pas seulement un booléen « GPU utilisé » ni les octets de RAM du processus. Un cache mémoire mappé ou un projecteur vision sur CPU ne prouve pas que des couches texte calculent sur CPU. La VRAM libre sert de précontrôle, pas de preuve universelle.
2. Débit par requête : utiliser les compteurs natifs de tokens et de temps, raisonnement inclus. La version installée écrit `n_gen`, `tg` et `tg_3s` toutes les quelques secondes pendant la génération (`llama.cpp/tools/server/server-context.cpp`, autour de la ligne 615). Lier le journal au processus/modèle et au slot/task actifs ; en cas d’attribution incertaine, signaler « mesure indisponible » sans arrêter un autre appel.
3. Point de départ à valider sur le Qwen de cette RTX 5090 : après traitement du contexte et une courte grâce de génération, seuil 20 tokens/s maintenu 45 secondes. Seuil propre au modèle/quantification/contexte, configurable ; l’absence de métrique n’est pas un débit nul.
4. Arrêter proprement uniquement la requête de PanelForge, conserver la trace/brouillon, bloquer sa chaîne avec motif explicite. Aucune réécriture/récupération LLM ni relance automatique. Réessayer après libération de VRAM et rechargement correct du modèle ; aucun arrêt de processus tiers.

Attention : `engine_stats.gen_tok_s` reste souvent à zéro pendant une réponse ; les compteurs correspondants se mettent à jour à la fin. `decode_calls_s` mesure des appels de calcul, pas des tokens, particulièrement avec MTP. Le code installé `studio/backend/core/inference/llama_stats.py` le documente explicitement. Ne pas utiliser ces zéros comme déclencheur. La route OpenAI actuelle ne transmet pas tous les timings natifs ; `stream_options.include_usage` donnerait un bilan terminal, pas à lui seul une surveillance live fiable.

## Petit patch d’interface livré

Le panneau de trace existant est remonté dans le cadre d’état des histoires longues, après le titre et le message, puis ouvert à chaque nouvel appel actif. Durée et nombres de caractères de raisonnement/réponse affichés. Défilement automatique tant que la lecture est en bas ; remonter dans la trace conserve la position. Panneau repliable. Histoires courtes : emplacement conservé. Message plus clair quand le modèle ne fournit que du raisonnement puis termine sans réponse finale.

Pas d’arrêt automatique, aucune modification des prompts/modèles/budgets ou du backend. La trace reste celle exposée par le modèle, avec les limites de stockage existantes. Actualiser la page suffit (stories.js 20260924.5 ; styles et présentateur 20260924.4).

Contrôles : compilation syntaxique seule des deux JavaScript, IDs HTML uniques, balisage suites/fabrication conservé, diff-check. Aucun test fonctionnel, appel modèle, génération, modification runtime ou redémarrage.
