# Audit H3 — ouverture dans le mur, 7 septembre 2026

Audit en lecture seule des projets et appels déjà enregistrés dans `D:\Code\panelforge\workspace`. Deux images natives inspectées ; vidéos non visionnées. Aucun test, appel LLM, rendu, annulation ou redémarrage. Aucun changement de recette ou validateur dans cet audit.

## Runs comparés

- Direct : `prompt-095b6a23c42d404bae50ee0d4a54d14c`, `minimax.h3.fl2va.direct.prompt@1.0.0` ; appel `llm-1f380d3bc5ab49f6a13725eafd013372` à 16:35:34 heure de Paris, accepté en 27,563 s. Son essai vidéo est enregistré comme annulé ; ne pas attribuer une qualité vidéo à ce prompt sur cette base.
- Guidé : `prompt-43f98cac12d348d8beb2a701d12f414f`, `minimax.h3.fl2va.direct.guided@1.0.0` ; Brief `creative-direction@0.2.0`. Le projet vidéo associé `h3-render-7d22988425ec40a9a1da2ab64ab896c2` possède ensuite un essai réussi.
- Même intention : ouvrier en jean bleu, t-shirt blanc et casquette bleue, travaux en avance rapide pour atteindre la seconde image, nuages rapides ; 7 secondes. Audace 3, trois axes à 3. Les opérations utilisent Qwen3.8-27B local.
- Mêmes images effectivement jointes : `asset-79ede4d5594f438189a6d6f5dcab473a` / `asset-1b80955334f0431fbda0203c09371005`. La seconde montre une ouverture dans un mur auparavant plein, un parement intérieur et des gravats. Le chemin est déjà partiellement pavé au départ et ne présente pas de changement de pavage évident dans cette paire.

| Appel guidé | Durée | Résultat |
| --- | ---: | --- |
| Brief `llm-04d6ebe2d7c44abc9a6a32a86f01d69b` | 55,729 s | Brief persisté puis approuvé |
| Plan `llm-0239eeaeb64f4c3aa7be37f3c8cdfaab` | 69,617 s | Refus applicatif |
| Plan relancé `llm-a398a3aba8e74d5f8fe98bb95991e696` | 72,152 s | Accepté |
| Prompt `llm-24fa083766f44f8da45a4eea4dec88e8` | 19,248 s | Accepté |

Somme des appels guidés : 216,746 s, dont 69,617 s pour le candidat rejeté. Ces durées n'incluent pas le rendu vidéo. Un seul couple de préparations ne permet pas de classer globalement les recettes.

## Erreur de validation

Message : `invalid H3 Base continuing-motion plan: keystone_s1.action: continue_motion must not settle into the final-frame composition at 6200 ms before the cut at 7000 ms without an instantaneous pass-through`.

Le champ rejeté décrit à 5,5–6,2 s : « revealing the dark niche that matches the final frame ». Mais `continuity_after` précise que l'ouvrier reste présent. Il sort ensuite entre 6,2 et 7 s et les nuages continuent ; `final_hold_ms` vaut 0. Il s'agit de la forme d'un élément terminé, pas d'une immobilisation de toute la composition finale.

Dans `application/direct_ref2v_plan.py`, `_continuing_motion_anchor_issues` cherche des mots de convergence proches de `final/last frame` et bloque si le champ se termine avant la coupure, sans distinguer l'élément concerné du mouvement final. Le second candidat conserve une niche terminée à 6,2 s mais écrit « finished niche identical in form to the last frame » : cette formulation ne correspond pas au motif bloquant. Le passage au second essai ne démontre donc pas la correction de la chronologie.

Correction proposée : ne plus traiter une simple ressemblance textuelle comme la preuve d'un arrêt global. Une phase matérielle finie peut se terminer avant la coupure alors que le mouvement final continue. Garder les contrôles structurels de temps et du contrat de fin ; avertir sur les ambiguïtés lexicales. Ne bloquer un arrêt textuel que si la contradiction avec le mouvement devant rester actif est explicite. Préparer des cas distinguant niche terminée, ouvrier encore présent, nuages actifs et véritable gel final, sans ajouter de LLM au validateur.

## Pourquoi le creusement disparaît

Le prompt direct ne décrit que l'ajout de pierres ; le creux apparaît derrière l'arche. Le Brief guidé choisit déjà cette même interprétation et la fixe en trois phases : entrée, pose de pierres, clé de voûte et sortie. Le Plan doit préserver cette décision. Le plan accepté contient même la résolution : « The visible action is adding and adjusting stones; removal is not shown and remains outside the frame. »

Les traces de raisonnement identifient bien le mur initial plein, mais privilégient l'assemblage de la voûte et reportent le retrait de matière hors champ. Elles développent surtout gestes saccadés, entrée/sortie, nuages et clé de voûte ; le problème est aussi sémantique, pas seulement une limite de durée ou de JSON.

Les consignes savent déjà qu'un plan continu peut comporter plusieurs phases. Cependant elles insistent sur une séquence simple et économique, et le texte d'audace se termine par « ne multiplie pas les actions ». Cela peut favoriser le raccourci ; ce run ne prouve pas que cette phrase en soit l'unique cause. Les trois étapes affichées désignent Brief → Plan → Prompt, pas trois opérations de chantier imposées dans la vidéo.

Correction proposée : au stade qui décide la progression (Brief en guidé, Plan en deux étapes, prompt direct en une étape), déduire les transformations visibles entre les images, puis leurs prérequis matériels. Distinguer retirer, évacuer, préparer et ajouter ; décrire un résultat observable par phase nécessaire. L'accélération compresse les gestes répétés, sans supprimer la causalité. Les restrictions sur les actions supplémentaires doivent viser les ajouts décoratifs, pas ces prérequis. Le rédacteur final conserve les phases choisies ; aucune nouvelle étape d'appel ou schéma de chantier nécessaire.

Pour cette paire : ouvrir le mur → dégager les gravats en conservant ceux visibles à la fin → aménager les bords et l'intérieur de l'ouverture → sortir du cadre. Un nouveau pavage est à demander explicitement et à rendre cohérent avec l'image finale : celui du chemin existe déjà au départ. La qualité de ces gestes dans H3 reste à éprouver par l'utilisateur après amélioration de la préparation.
