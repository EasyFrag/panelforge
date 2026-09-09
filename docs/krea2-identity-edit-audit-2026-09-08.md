# Audit KREA2 Identity Edit — 8 septembre 2026

Demande : comparer le LoRA et son workflow aux recommandations de l'auteur, pour comprendre les suppressions difficiles et la perte de netteté. Audit uniquement ; aucune modification du moteur, des prompts ou des réglages.

## Sources et version

- [Version Civitai demandée](https://civitai.red/models/2761113/krea-2-identity-edit?modelVersionId=3139172) : l'API publique `/api/v1/model-versions/3139172`, lue sur `.red` et `.com`, confirme **v1.2** et `krea2_identity_edit_v1_2.safetensors`. Pas de trigger obligatoire déclaré. Pas de téléchargement ni de calcul de hash des poids installés.
- [Fiche de l'auteur sur Hugging Face](https://huggingface.co/conradlocke/krea2-identity-edit) : Turbo, 8–12 steps, CFG 1 pour les éditions courantes ; Raw, environ 20 steps, CFG 3 pour les suppressions importantes. LoRA à 1.0. Génération conseillée jusqu'à 2 MP ; davantage peut provoquer duplication ou débordement de référence. La suppression reste imparfaite et les éditions peuvent modifier la colorimétrie ou des zones voisines.
- [Documentation des nœuds](https://github.com/lbouaraba/comfyui-krea2edit) : instruction d'édition ancrée dans l'image, double conditionnement visuel obligatoire ; `grounding_px` 768 par défaut, 512 à essayer pour une modification de scène récalcitrante. Le chemin image + VAE et `target_latent` sont recommandés.
- [Changelog](https://github.com/lbouaraba/comfyui-krea2edit/blob/main/CHANGELOG.md) : géométrie FIT en v1.2 ; centrage et arrondis corrigés en 1.2.4 ; pré-encodage via `target_latent` en 1.2.5.

Le fil [Blurry with 2:3 portrait ratio pics](https://huggingface.co/conradlocke/krea2-identity-edit/discussions/5) contient des témoignages proposant un multiple de 16 plutôt que 8, principalement sur **v1.1**. Ce ne sont ni une preuve de défaut en v1.2 ni une recommandation confirmée par l'auteur dans ce fil. Ne pas généraliser ces témoignages aux nœuds actuels.

## Installation et workflow réellement utilisés

Inspection SSH en lecture seule de `/home/malmo/ComfyUI/custom_nodes/comfyui-krea2edit` : paquet **1.2.5**, commit `86f886d` du 29 juillet 2026. Cela vérifie les fichiers sur disque, pas une introspection du module Python chargé. Le workflow compilé récent utilise bien `target_latent`.

Workflow local `workflows/image.edit/krea2-identity/0.1.0/` et candidat enregistré `attempt-5b16a155994e49ddb0339173ff60bc88` :

| Élément | Constat |
| --- | --- |
| Identity Edit | Poids nommés v1.2, force 1 ; distincts des LoRA facultatifs |
| Géométrie | `fit`, image source + VAE branchés, `target_latent` branché |
| Modèle du candidat | `Krea2/krea2_turbo_bf16.safetensors` |
| Sampling | Euler / Simple, 10 steps, CFG 1, denoise 1 |
| Référence | `ref_boost` 1 sur cet essai ; défaut atelier 2.5 |
| Texte | Qwen3-VL-4B **heretic**, ancré dans la source ; négatif vide également ancré |
| Grounding | 768 fixe |
| Résolution | 2.1 MP demandés ; multiple de 8 |

CFG reste fixe à 1 même si l'utilisateur choisit un checkpoint Raw. Le passage à Raw seul ne suffit donc pas à suivre la recette de suppression de l'auteur. Le départ est un latent vide : abaisser le denoise comme sur un img2img classique n'est pas une correction évidente ici. `ref_boost` règle la fidélité à la référence ; le monter systématiquement ne garantit ni netteté ni suppression.

Le text encoder heretic est une variante du modèle standard cité par l'auteur. Aucune preuve recueillie d'une responsabilité dans les défauts ; comparaison éventuelle séparée, sans en faire une priorité.

## Observation de l'atelier récent

Chaîne `krea2-edit-95a241c04c3740bba7b0dab2a4bfc0c3`, pelouse et excavation en silhouette. Lecture pendant que l'utilisateur travaille : instantané, pas inventaire définitif du dernier run.

- Étape `krea2-edit-094148a0972245b391415f1e5f74d2a3` : la demande « Enlève la peinture au niveau des gants » produit **528 mots**. La reformulation suivante produit 476 mots. Writer `krea2.edit.conversation@2.0.0`.
- Étape suivante `krea2-edit-bc236743a9ae417698b7c4a0661466ca` : ajout de bâche puis retrait de terre apparente, prompts de 545 et 557 mots.
- Ces essais utilisent Turbo, 10 steps, aucun LoRA facultatif. Les difficultés ne peuvent donc pas être attribuées systématiquement à un LoRA de style ajouté.
- Source de l'étape peinture : `asset-bc1787d9b52944cc97ea6f059ef1cb82`, **1664 × 2960**, soit 4.925 MP. Générations `asset-9943425183f94d248ae7bb925b2184d7` et `asset-258f6eaf8f6f4462b680a4ca869fb4c2` : **1112 × 1976**, soit 2.197 MP réels.
- Le compositeur conserve les dimensions de la source, conformément au choix utilisateur, et agrandit la génération par Lanczos : environ **×1.5 par axe** ici. Les zones retouchées ne récupèrent pas les détails d'une vraie génération de 4.9 MP. Hors masque, la source reste protégée.
- Inspection visuelle source / deuxième génération : la tache centrale disparaît, mais la texture du sol devient plus grossière et l'aspect du contour change. Cela constate une réinterprétation, sans isoler la responsabilité du prompt, de la résolution ou du sampling. La source affichée a été réduite par l'outil de visualisation : pas de mesure comparative de netteté au pixel.

## Diagnostic et proposition pour une prochaine version

**Priorité : le contrat de prompt Edit.** `application/krea2_edit_assistance.py` exige actuellement une description autonome complète de l'image finale. C'est un écart avec l'interface d'instruction d'édition du modèle. Hypothèse : les longues descriptions et répétitions diluent le changement demandé et favorisent une reconstruction globale. Cela n'établit pas à lui seul la cause du flou.

Une nouvelle version pourrait produire les changements ciblés **par rapport à la source fixe de l'étape**, avec localisation, remplacement concret et quelques invariants. Garder tous les changements encore souhaités dans l'étape courante, pas uniquement la dernière phrase utilisateur. Les états déjà présents dans la source n'ont pas à être redécrits intégralement. Les grandes transformations restent possibles ; ne pas imposer une limite arbitraire d'une phrase.

Exemple à comparer manuellement, non exécuté :

> Replace the white painted patch in the center of the excavation with bare brown soil at the same depth and with the same texture as the surrounding pit floor. Preserve the excavation shape, its outer white boundary, the lawn, framing and lighting.

Puis prévoir une nouvelle version de workflow avec réglages compatibles Turbo / Raw, sans déduire automatiquement la famille d'un checkpoint communautaire à partir de son nom. Exposer CFG et éventuellement grounding dans les paramètres avancés ; conserver un défaut Turbo simple.

Pour isoler les causes, proposer à l'utilisateur des comparaisons successives : même source/seed/réglages avec le nouveau prompt, puis grille 16, puis une résolution dans la plage conseillée, puis Raw/20/CFG3 pour une suppression récalcitrante. La grille 16 est une piste de compatibilité à comparer, pas un correctif de flou prouvé. Une résolution plus basse peut améliorer le comportement du modèle tout en réduisant les détails disponibles au réagrandissement : ces deux effets doivent être jugés séparément.

Le masque et l'harmonisation restent pertinents pour préserver le reste de l'image. Ils ne restaurent pas les détails absents dans la zone générée. Afficher les dimensions réelles et le facteur d'agrandissement aiderait à interpréter le résultat.

**Livraison de cet audit : documentation et continuité uniquement. Aucun test, appel LLM, génération, modification runtime, mise à jour de nœud ni redémarrage.**

## Complément : ce que l'auteur appelle le problème de géométrie

Précisions utilisateur : conserver l'ancien prompting accessible pour comparer avec une nouvelle version ; revoir les réglages séparément ; laisser résolution et redimensionnement actuels inchangés. L'upscaling est une réflexion, aucune étape supplémentaire demandée. La demande immédiate est d'expliciter le diagnostic de netteté.

Le [code de l'auteur](https://github.com/lbouaraba/comfyui-krea2edit/blob/main/__init__.py), également relu dans l'installation de Bucket, distingue deux traitements :

1. Ancien chemin : adapter directement le latent VAE aux dimensions cibles. Ses commentaires attribuent un ramollissement à cette interpolation ; un rapport largeur/hauteur différent pouvait aussi étirer le contenu.
2. Chemin image : ajuster les pixels de la source aux dimensions adaptées, puis les encoder par le VAE. Il évite le redimensionnement du latent. Il faut effectivement brancher `vae` et `source_image` ; sélectionner `fit` seul ne suffit pas.

La géométrie FIT place la référence à une échelle et une position cohérentes avec les images utilisées à l'entraînement. Les corrections 1.2.4 concernent aussi des arrondis qui comprimaient le contenu jusqu'à 15 pixels et un centrage décalé de 8 pixels ; ces défauts se manifestaient surtout par des bandes dédoublées en extension de cadrage. L'auteur mentionne des cas résiduels et `crop` comme contournement éventuel, pas comme meilleur défaut universel. Source : changelog lié plus haut.

Application à notre cas : `vae` + `source_image` + `fit` sont branchés dans le workflow compilé inspecté. Le code installé contient bien ces corrections. `target_latent` est également branché, mais son gain annoncé concerne le moment du pré-encodage et la vitesse, pas un filtre supplémentaire de netteté.

La source 1664×2960 et la sortie 1112×1976 ont des proportions presque identiques (écart relatif d'environ 0.105 %). Le code FIT choisit alors l'ajustement avec recadrage central minimal ; on n'est pas dans le cas d'une grande bande vide due à un changement de format. Passer aveuglément sur `crop` a donc peu de justification pour cet exemple.

Le multiple de **8** du sélecteur de résolution reste un paramètre distinct. Les deux dimensions de cette sortie ne sont pas divisibles par 16. Le code complète les grilles aux dimensions nécessaires ; cela ne démontre pas un bug, et les témoignages de flou évité avec un multiple de 16 datent surtout de v1.1. Une comparaison 8/16 peut rester proposée à l'utilisateur, sans modifier la valeur actuelle ni promettre un gain.

Conclusion limitée : le défaut historique de redimensionnement latent est bien documenté ; notre câblage active déjà le chemin prévu pour l'éviter. Les défauts de texture actuels ne peuvent pas lui être attribués sur ces seuls éléments. Aucun rendu de comparaison exécuté, aucun paramètre changé.
