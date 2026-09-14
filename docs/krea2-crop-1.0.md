# Recadrage de la source — KREA2 Modif

Dans une étape éditable de Modifier avec KREA2, cliquer **Recadrer la source**, près des contrôles de comparaison.

1. Tracer un rectangle sur l’image à la souris.
2. Le déplacer depuis son intérieur ou ajuster ses bords avec les poignées. Les dimensions de la sélection sont affichées en pixels.
3. **Valider et continuer** enregistre le recadrage comme résultat validé de cette étape, puis ouvre l’étape suivante. **Annuler** conserve l’atelier tel quel.

L’outil recadre toujours la source de l’étape, indépendamment de l’essai choisi dans Avant/Après. Pour recadrer un résultat généré, le valider d’abord afin qu’il devienne la source de l’étape suivante.

Le traitement utilise les pixels de l’image d’origine, après application de son orientation EXIF, et produit un PNG aux dimensions du rectangle. Il est local sur CPU. Les limites de décodage existantes restent applicables : image fixe PNG/JPEG/WebP, 25 Mio, 17 millions de pixels décodés.

L’image originale reste dans l’historique. Le recadrage entre dans le stockage des assets et l’export de projet habituels, avec ses coordonnées. La nouvelle étape repart avec une conversation et un prompt vides : les descriptions de l’ancien cadre ne sont pas transférées. Les réglages de rendu sauvegardés sont hérités et restent modifiables.

Une sauvegarde répétée avec le même identifiant et le même rectangle retrouve la même étape. Une source remplacée, une étape recommencée ou un traitement en cours entraîne un refus explicite plutôt qu’un recadrage sur un autre contexte.

## Validation

Vérifications statiques effectuées : syntaxe Python et JavaScript, identifiants HTML uniques, script chargé avant l’atelier, contrôle du diff. Aucun test fonctionnel, appel LLM, rendu ni redémarrage lancé, conformément aux consignes du projet.

Tests préparés : coordonnées et orientation, pixels/canal alpha conservés, historique et exports, prompt suivant vide, réouverture, sauvegardes répétées, récupération d’un échec partiel et contrat HTTP. À lancer par l’utilisateur :

```powershell
Set-Location D:\Code\localQ\.panelpatch
$env:PYTHONPATH = Join-Path (Get-Location) "src"
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_krea2_crop tests.test_krea2_edit_web tests.test_krea2_retouch tests.test_krea2_upscale tests.test_krea2_restaging tests.test_krea2_edit_versions
```

Redémarrer le Lab pour charger le serveur modifié, puis recharger le navigateur avec Ctrl+F5.
