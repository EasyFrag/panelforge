# H3 Base : résolutions et seed

À partir du workflow de rendu `minimax-h3-latent-speed@0.1.3`, les nouveaux
ateliers H3 Base proposent deux réglages indépendants, tous deux modifiables :

- **MP avant upscale** : résolution de la génération initiale, défaut **0,2**.
- **MP sortie** : résolution cible après upscale/finition, défaut **0,2**.

Plage de chaque champ : 0,1–16 MP, par pas de 0,1. Modifier un champ ne change
pas l’autre. Le ratio est commun. Les deux valeurs égales ne suppriment pas la
seconde passe du workflow. Une cible inférieure à la résolution initiale est
acceptée ; le redimensionnement réduit alors la résolution avant la finition.

**Réutiliser la seed** est coché par défaut : la valeur affichée est envoyée aux
rendus suivants. Décocher conserve le fonctionnement aléatoire existant.
Les anciens essais gardent leurs valeurs de sortie ; **Reprendre prompt +
réglages** restaure les deux résolutions et la seed de l’essai choisi.

Le champ `initial_megapixels` traverse l’API de préparation, le snapshot de
l’essai, le stockage H3, les métadonnées du feedback LLM et le compilateur. Les
anciens fichiers sans ce champ reprennent la valeur historique 0,2 ; les schémas
1–3 restent lisibles et le schéma 3 est conservé. Les entrées du workflow sont
déclarées dans le nouveau manifest, sans identifiant de nœud dans le service.

Les workflows 0.1.0–0.1.2 sont conservés. L’ancienne première passe reste fixe à
0,2 lorsqu’un de ces workflows est chargé explicitement. Aucun changement aux
recettes de préparation LLM en 1/2/3 étapes, ni aux contrôles Ref2V pour ce patch.
Le tag `stable-avant-masque-2026-09-06` reste intact.

Tests préparés, non exécutés par l’agent : compilation des quatre modes H3,
indépendance et validation des résolutions, persistance/lecture ancienne,
paramètres réellement compilés, contrôle navigateur des défauts et de la seed.

```powershell
$env:PYTHONPATH = 'D:\Code\localQ\.panelpatch\src'
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_h3_render tests.test_h3_render_controls_browser tests.test_run_lab_build tests.test_lab_web
```

Aucun appel LLM, rendu, test ou redémarrage de service pendant l’implémentation.
Le code sera chargé au prochain redémarrage du Lab par l’utilisateur ; caches
CSS/H3 Render `20260907.5`.
