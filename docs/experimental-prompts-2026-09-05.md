# Recettes expérimentales — 5 septembre 2026

Mise à jour du 7 septembre : les [parcours 3 / 2 / 1 étapes](video-preparation-recipes.md) sont disponibles. H3 Base démarre désormais sur **Exploration guidée · 3 étapes (1.0.0)** ; sa recette compacte `0.4.0` rejoint **Autres recettes → Versions historiques**. KREA2 Assisted démarre sur [V3 · corrections visuelles](assistance-recipe-versions.md), qui conserve le contexte V2 et reformule les demandes de suppression. Ref2V compact expérimental `0.5.0` conserve son statut de défaut. Les comparaisons ci-dessous décrivent le patch expérimental d'origine.

## Options disponibles

| Outil | Témoin conservé | Nouvelle option |
| --- | --- | --- |
| KREA2 Assisted | V1 `1.0.0` | V2 `2.0.0` — sujet et contexte compact |
| H3 Base mono-plan | `0.3.3` | `0.4.0` — mono-plan compact |
| Ref2V mono-plan | `0.4.0` | `0.5.0` — mono-plan compact |

Les versions expérimentales sont les défauts des sélecteurs pour les nouveaux projets. Choisir la recette avant de créer le projet/parcours. Un ancien projet KREA2 reste en V1. Pour comparer une vidéo existante, utiliser « Repartir de ce run », choisir la nouvelle recette, puis créer le parcours. Un Brief déjà créé ne bascule pas silencieusement de version : les nouvelles recettes exigent la paire profil Brief / cookbook Plan-Writer correspondante, également vérifiée côté service.

## KREA2 Assisted V2

Révision légère de V2 après le run « lips » : après un échec spatial répété rapporté par l'utilisateur ou visible dans les résultats joints, changer un choix concret de cadrage, d'échelle ou de position dans les contraintes utilisateur. Le message décrit une correction proposée au prompt, sans annoncer l'image comme corrigée. Deux paragraphes et le libellé JSON ont été condensés : système de création de 3524 à 3358 caractères (511 à 481 mots séparés par espaces), sans appel supplémentaire ni modification de V1. Contrôle de syntaxe uniquement ; qualité à évaluer par l'utilisateur.

La création assistée accepte aussi une image seule, en V1 comme en V2 : laisser l'intention vide initialise une demande de reproduction du sujet, de la composition, des matières et de l'ambiance. Cette demande est conservée dans l'intention du projet et utilisée pour le premier échange. Sans texte ni image, la création est refusée.

- Le sujet peut être un objet, une chaussure, une main, une créature, un animal, une personne ou plusieurs éléments. Le prompt distingue les traits visuels à conserver de l'état narratif modifiable. Il demande une image fixe autonome, sans présumer un protagoniste humain.
- Le contexte contient le prompt courant et les 13 entrées précédentes utilisateur/assistant, avec leurs retours verbatim. Les copies intégrales des prompts des tours anciens sont omises. Si le résultat sélectionné utilise exactement le prompt courant, son texte n'est inclus qu'une fois avec les réglages du résultat.
- Une correction visuelle ne charge pas les catalogues de ressources ni les recettes publiées. Une demande technique reçoit un catalogue partiel borné (12 checkpoints, 16 LoRA), avec priorité aux termes explicitement mentionnés. La mémoire des recettes publiées reste disponible pour une demande de recette ou sa préparation à la publication.
- Les images jointes gardent leurs rôles existants. Aucun résumé LLM, arbre, mémoire sémantique persistante ou appel additionnel n'est créé. Sélectionner un ancien résultat ne rembobine toujours pas les échanges ; le système le précise et sait recevoir une demande explicite de reprise depuis cette référence.
- Le JSON de réponse reste compatible. La version du projet et des tours est persistée ; les nouvelles opérations du journal sont `krea2.assisted.creation_chat@2.0.0` et `krea2.assisted.recipe_chat@2.0.0`. Les plafonds de sortie et températures ne sont pas modifiés.

## Vidéo : concision et succession des actions

Les nouvelles recettes conservent trois appels : Brief, Plan, Writer. Elles demandent un Brief plus court, un Plan limité aux phases causales utiles et moins de répétitions entre résumé du beat, actions et états résultants. Le schéma validé reste V4 ; aucune contrainte de timing, caméra, dialogue ou rôle de frame n'est retirée pour accélérer le modèle.

Un plan sans coupe peut comporter plusieurs actions finies. Le champ `primary_motion` désigne désormais l'action de la phase finale dans ces recettes. Le compilateur n'ajoute plus la phrase imposant cette action « pendant tout le plan » : une main peut saisir, planter, relâcher et se retirer avant que la plante ne continue de pousser. Le compilateur conserve la phrase de fin et le comportement `continue_motion`, `natural_settle` ou `intentional_hold`. Les versions témoins gardent leur comportement antérieur.

La projection `camera_clean_compact_v5` réduit seulement l'entrée du Writer. Elle retire des doublons strictement identiques au même niveau temporel et l'indentation JSON. Les faits distincts et les états atteints plus tôt sont conservés. Les repères caméra restent présents. Les cues conservent ID, identité du locuteur et position ; le texte, la langue et la diction restent dans le Plan complet, utilisés par le compilateur pour les clauses verbatim. L'instantané final est lui aussi compilé depuis le Plan complet. Le Plan approuvé n'est jamais réécrit par cette projection.

Les variantes de direction créative des nouveaux profils utilisent les mêmes principes de concision et de phases, avec les mêmes niveaux d'audace et libertés. Les fichiers des profils/cookbooks témoins, les workflows ComfyUI, les poids et le loader Hybrid restent inchangés. Production V1/V2 continuent à utiliser leurs recettes standard actuelles.

## Validation à effectuer par l'utilisateur

Aucun test, appel LLM ou rendu n'a été lancé pendant ce patch, et aucun service n'a été redémarré. Des tests hors ligne ont été ajoutés/actualisés mais ne sont pas exécutés. Aucun gain de latence ou de qualité n'est encore mesuré.

Quand les générations en cours sont terminées, redémarrer PanelForge et recharger la page. Pour une première comparaison, conserver le même modèle LLM, les mêmes références, intention, durée et libertés ; pour les images, garder aussi checkpoint, seed et LoRA identiques. Commencer par un sujet non humain (chaussure ou main), une modification de l'état d'un dragon, une séquence saisir/planter/retirer/pousser, puis un mouvement réellement continu et un dialogue exact. Juger la fidélité, les contradictions et les erreurs de contrat avant la seule vitesse.

Le journal existant et les sessions/compositions permettent de retrouver les prompts, réponses, références de recette et durées. Aucun nouveau panneau de logs n'est ajouté. Le journal technique reste borné à 20 appels : relever les comparaisons avant qu'elles ne soient remplacées. Les compteurs de tokens peuvent rester absents selon le serveur local.
# Ajustement du guidage caméra

H3 Base `0.4.0` et Ref2V `0.5.0` appliquent désormais une règle commune au Brief standard, au Brief Direction créative `0.2.0`, à leurs révisions et au Plan (génération/arbitrage). Choisir un mouvement principal, ou un cadre fixe ; conserver une succession seulement si une phase de la scène la justifie. Une combinaison simultanée impossible à représenter est simplifiée explicitement, en respectant les cadrages, les axes de liberté et le suivi continu demandé. Aucun mouvement secondaire ne doit être caché dans les champs descriptifs du Plan.

Le modèle reçoit une consigne de décision unique puis de rédaction directe, sans alternatives de caméra ni brouillons complets répétés. Cette modification vise les hésitations observées dans le thinking fourni par l'utilisateur ; aucun gain de temps n'a encore été mesuré. Les recettes témoins restent inchangées. Aucun test ni appel LLM n'a été exécuté pour cet ajustement.
