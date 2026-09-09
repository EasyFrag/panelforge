# Révisions H3 : rejets de shake.slightly

Audit du dernier atelier `h3-render-ec42843919e0465bab7231a4fa5df502`, mode first/last, dans `D:\Code\panelforge\workspace`. Lecture du projet et des appels enregistrés dans `llm_calls.json` ; aucun appel LLM, test ou rendu exécuté.

## Ce que montrent les traces

Les erreurs proviennent de la **conversation après vidéo**, opération `h3.base.render.revision@0.2.0`, et non du plan de préparation ou du workflow vidéo.

| Heure locale, 9 septembre | Durée LLM | Résultat |
| --- | ---: | --- |
| 12:07:29 | 56,934 s | Rejet : `shake.slightly` avec `amplitude: small` et `speed: slow`. |
| 12:12:37 | 31,683 s | Correction explicite acceptée avec amplitude/vitesse nulles. |
| 12:20:21 | 74,432 s | Rejet : `shake.slightly` avec `target_clause: keeping the entire row of salamanders and her face in view`. |
| 12:22:04 | 28,206 s | Correction explicite acceptée avec cible nulle. |

Il y a donc deux refus apparentés, dont **un seul portant exactement sur la cible** dans ce dernier atelier. L’erreur apparaît aussi dans le contexte de la demande de réparation suivante ; ce n’est pas un refus supplémentaire. Le projet enregistré a ensuite retrouvé un prompt valide, avec `The camera shakes slightly.` et aucune erreur de révision en cours au moment de l’audit.

Appels refusés : `llm-1b22a163eba444158198260192692a30` et `llm-3341aa462c7449b19a277dc3019b6568`. Appels de correction : `llm-2ed33e37c42e47caad4b2b60fe87ba7c` et `llm-f94d47fc4a6640d7abe5f8306df1d6af`.

## Cause

`H3CameraDirective` interdit les modificateurs amplitude/vitesse pour `static_shot`, `shake.slightly`, `shake.strongly` et `pov`. Les trois derniers n’acceptent pas non plus de cible. Ces contraintes figurent déjà dans le schéma du plan direct ; elles manquaient dans le contrat textuel de la conversation après rendu.

Le contrat conversationnel indiquait une liste générale de préfixes autorisés, dont `keeping`, sans préciser quels mouvements acceptaient une cible. Le LLM a donc utilisé ce champ pour porter la demande de conserver toute la scène visible. Son raisonnement de 31 083 caractères hésite aussi entre conserver le léger tremblement, passer en plan fixe, laisser les directives à null ou déplacer la contrainte dans la prose. L’interdiction générale de « framing prose » rendait cette dernière solution ambiguë. Ces traces expliquent une partie des hésitations ; elles ne permettent pas de prédire un gain de temps ni d’établir la cause visuelle du zoom observé.

## Correctif

- Compléter le **contrat commun H3 / REF2V** avec les champs obligatoirement nuls selon le mouvement, et un exemple valide de `shake.slightly`.
- Autoriser explicitement les descriptions de composition dans la prose de l’action : quels sujets et éléments restent visibles ensemble, au moment pertinent. Une demande de visibilité n’impose pas de remplacer le léger tremblement par un plan fixe ; `camera_directives: null` reste permis si le mouvement compilé ne change pas.
- Garder les instructions de mouvement dans les tokens compilés. Le validateur reste strict : aucune suppression silencieuse de la contrainte utilisateur. En cas de réponse encore invalide, le message d’erreur indique les champs à mettre à null et où préserver la contrainte de visibilité ; cela aide aussi la réparation explicite.

Correctif du contrat de révision `0.2.0` existant, sans nouvelle recette 1/2/3 étapes, sans modification du compilateur, du stockage ou des prompts historiques `0.1.0`. Les anciens runs ne sont pas réécrits ; seules les prochaines demandes utilisent les consignes corrigées après chargement du code par le Lab. Aucun cache navigateur à modifier pour ce changement exclusivement serveur.

Tests ajoutés dans `H3RenderRevisionVersionTest` : composition visible avec shake inchangé (directive nulle ou explicite), mauvais champ toujours refusé avec brouillon préservé et explication actionnable, règles shake/POV/static et diffusion des consignes aux requêtes H3 et REF2V. **Tests préparés, non exécutés.** Commande à la main de l’utilisateur :

```powershell
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_h3_render.H3RenderRevisionVersionTest
```
