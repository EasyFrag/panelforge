# Liberté vocale et adaptation H3 vers REF2V

Patch implémenté le 9 septembre 2026 après le correctif de démarrage BUNNY. Tests préparés, **non exécutés** ; aucun appel LLM, rendu ou redémarrage de service pendant l’implémentation.

## Versions et accès

| Préparation | Nouvelle version, pour les trois parcours |
| --- | --- |
| H3 Base mono-plan · guided / planned / prompt | 1.2.0, profil 0.6.0 |
| H3 Base multi-plan · guided / planned / prompt | 1.1.0, profil 0.3.0 |
| REF2V mono-plan · guided / planned / prompt | 1.1.0, profil 0.6.0 |
| Échange après prompt H3 / REF2V | 0.3.0 · dialogues et caméra compilée |

Les recettes précédentes restent dans les catégories historiques. Les anciens parcours conservent leur version ; le curseur vocal est masqué pour une recette qui ne le prend pas en charge. Les recettes historiques REF2V multi-plan gardent leur comportement antérieur. On peut adapter un nouveau parcours H3 multi-plan vers REF2V avec le bouton de conversion, puis utiliser la révision vocale 0.3.0.

« Dialogues et réactions » se trouve avec les autres libertés créatives ; dans l’atelier de rendu, « Dialogues au prochain échange » applique le choix à la prochaine demande au LLM. La valeur seule ne réécrit aucun prompt.

« Adapter en REF2V » est près du prompt éditable H3, accessible avant le premier rendu. L’appel démarre directement si une first/last frame existe ; en texte seul, un sélecteur d’image apparaît d’abord. Le bouton « Ouvrir l’atelier REF2V » ouvre le résultat sans changer de page automatiquement pendant l’appel. Les ateliers dérivés sont accessibles dans la liste « Adaptations depuis H3 » à gauche de REF2V, avec un lien de retour au rendu H3 d’origine. Ils n’exigent aucun Brief ou Plan artificiel.

La conversion copie le prompt actuellement affiché et les réglages compatibles. BUNNY reste BUNNY ; sa variante REF2VA est sélectionnée. Le rendu actuel reste le défaut général. Une limitation de première passe de la recette de destination est affichée. Les références, réglages, origine, réponse brute et statut sont persistés ; un échec conserve le brouillon. « Reprendre l’enregistrement » réutilise l’identifiant existant, sans rejouer un appel déjà lancé. Pour demander une nouvelle réponse après un échec LLM, revenir à H3 et cliquer à nouveau sur « Adapter en REF2V ».

Stockage : sessions de prompts schéma 9 (lecture 1–8), compositions 4 (lecture 1–3), ateliers H3 6 (lecture 1–5). Le hash des intentions historiques à dialogue 0 reste identique. Les tags caméra, paroles, repères temporels, coupes et champs audio sont protégés pendant la conversion. La conservation sémantique des actions et locuteurs dépend aussi du modèle ; la conversion ne garantit pas la qualité d’une future vidéo.

## Vérification par l’utilisateur

Depuis le checkout `.panelpatch`, avec son environnement Python et `src` accessible :

```powershell
python -m unittest tests.test_vocal_policy tests.test_h3_ref2v_conversion tests.test_dlss_outputs
```

Les fixtures utilisent des réponses fixes et des fichiers temporaires. Vérifier ensuite dans l’interface les trois parcours, un prompt H3 modifié manuellement, BUNNY, first seule / last seule / les deux / texte avec référence ajoutée, l’ouverture depuis la liste REF2V et une navigation pendant l’adaptation. Aucun rendu ne doit partir à la conversion. Les tests et essais restent à exécuter par l’utilisateur.

## Cadrage validé conservé

## Liberté de dialogue

Ajouter « Dialogues et réactions » aux libertés créatives de H3 et REF2V. Le réglage est indépendant de l’audace, de la caméra et de la musique.

| Niveau | Permission |
| --- | --- |
| 0, défaut | Aucun ajout spontané. Conserver les paroles et réactions explicitement demandées. |
| 1 | Courtes réactions non verbales adaptées à l’action : souffle de surprise, rire, cri justifié. |
| 2 | Réactions et une courte réplique anglaise, si utile. |
| 3 | Bref échange en anglais entre personnages présents ; rester compatible avec la durée et l’action. |

Ces permissions ne sont pas des quotas. Ne pas inventer un personnage, une blessure, un danger ou un événement pour justifier une intervention. Une demande explicite de silence reste prioritaire. Les paroles utilisateur restent verbatim, y compris lorsqu’elles sont dans une autre langue. Les cris et souffles sont des événements vocaux non verbaux, distincts des phrases prononcées.

Le choix des ajouts appartient à la première étape décisionnelle : Brief en trois étapes, Plan en deux, prompt direct en une. Les étapes suivantes reprennent les interventions retenues, leur locuteur et leur place dans l’action. En conversation post-prompt, le réglage peut être changé pour le prochain échange ; le changement du contrôle seul ne réécrit pas le prompt. Une instruction explicite de modification reste possible.

Le code actuel comporte des validations exigeant exactement les dialogues de l’intention, notamment en prompt direct et en multi-plan. Il faut distinguer les paroles imposées et les ajouts autorisés dans les données conservées, puis adapter ensemble prompts, compilateurs et validations. Ne pas simplement supprimer les comparaisons de dialogues, ni ajouter une consigne contradictoire à un ancien prompt.

Versionner les nouvelles consignes et recettes de préparation, en partageant les blocs de politique vocale. Préserver les recettes historiques et charger les anciens projets avec un niveau 0. Couvrir les préparations en une, deux et trois étapes, les séquences mono/multi-plan et les ajustements post-prompt. Les anciennes recettes ne doivent pas présenter un contrôle actif qu’elles ne savent pas appliquer.

## Bouton « Adapter en REF2V »

Placer le bouton près du prompt courant de l’atelier de rendu H3. Il doit aussi fonctionner avant le premier rendu et après une modification manuelle du prompt.

1. Capturer le texte actuellement affiché, les images et les réglages compatibles. Conserver cet instant de départ pendant l’appel, même si l’utilisateur navigue ailleurs.
2. Reprendre les assets existants : début vers rôle `first_frame`, fin vers rôle `last_frame`, avec leurs labels et un ordre explicite. S’il n’existe aucune image, demander une référence avant l’adaptation ; ne pas générer une image automatiquement.
3. Effectuer un seul appel LLM multimodal de conversion avec une consigne versionnée. Adapter la formulation au contrat REF2V ; préserver actions, état final, durée, dialogues, caméra, son et éventuelles coupes. Le niveau de liberté de dialogue ne permet pas d’ajouter des paroles durant cette conversion.
4. Compiler les labels et les en-têtes de référence côté application. Vérifier les éléments protégés et conserver le candidat en cas d’échec ; aucune relance LLM automatique.
5. Ouvrir un atelier REF2V dérivé avec prompt éditable, lien vers l’origine et images préaffectées. Ne pas écraser l’atelier H3 ni fabriquer de Brief ou de Plan approuvé. Aucun rendu vidéo automatique.

Reprendre durée, ratio, MP et réglages compatibles. Si BUNNY est sélectionné, il peut rester sélectionné côté REF2V avec le routage de modèle propre à ce mode. Sinon, sélectionner la recette REF2V correspondante disponible et afficher le choix. Les historiques de rendu des deux ateliers restent distincts ; le nouvel atelier peut ensuite utiliser les actions REF2V habituelles, le feedback et DLSS.

Une référence avec rôle « première/dernière frame » en REF2V est guidée par le prompt et ne constitue pas le verrouillage d’entrée/sortie FL2VA. La conversion préserve l’intention de ces rôles, sans promettre une reproduction exacte des images.

## Vérification à préparer lors de l’implémentation

- Paroles utilisateur conservées ; anglais pour les ajouts ; silence prioritaire ; aucun ajout à 0 ; budget vocal compatible avec le clip.
- Conservation des ajouts entre étapes, réouverture et révision ; anciens projets et recettes inchangés.
- Conversion depuis un prompt modifié manuellement ; first seule, last seule, les deux, absence d’image ; mono/multi-plan.
- Un seul appel LLM, aucun rendu ; absence de nouveau Brief/Plan ; mapping applicatif et références exactes, conservation des dialogues, caméras et coupes.
- Échec ou navigation pendant l’appel : source et brouillon conservés, résultat rattaché au bon atelier, absence de doublon lors d’un nouvel enregistrement.
- Réouverture du nouvel atelier, reprise des réglages, rendu avec la bonne recette et continuité du feedback/DLSS.

Les tests seront préparés pour l’utilisateur. Aucun appel LLM ou génération de vérification, aucun redémarrage de service par l’agent.
