# Qwen Changer la vue : réglages de rendu 0.3.0

Dans Image Lab → Changer la vue → Réglages avancés :

- **Steps** : 8 par défaut, modifiable de 1 à 50.
- **Résolution (MP)** : vide par défaut, pour conserver le dimensionnement automatique du workflow actuel (buckets Kontext autour de 1 MP). Valeur explicite de 0,1 à 4 MP.
- **Format de l’image** : automatique selon la source, carré, portrait ou paysage. Un format imposé utilise un recadrage centré de la source ; aucune déformation volontaire. Le fichier reste un PNG.
- **Réglages initiaux** rétablit ces trois paramètres, sans réinitialiser angle, seed ni force de LoRA.

Résolution vide + format imposé : cible de 1 MP dans ce format. Les dimensions sont arrondies à des multiples de 32 ; les MP réels et le ratio peuvent donc différer légèrement des valeurs demandées. MP explicites + format source : conservation du ratio source, avec le même arrondi technique.

Les réglages sont stockés avec l’essai et repris à l’ouverture de l’historique. Les anciens essais reviennent aux valeurs initiales pour ces trois champs. Les changements de steps/résolution/format sont marqués comme réglages expérimentaux dans le run.

## Implémentation et défauts

Le bundle `workflows/character.change_view/qwen-edit-2511-multiple-angles/0.3.0` reprend exactement les octets du workflow et du prompt de 0.2.0. Ses bindings supplémentaires déclarent les points de réglage. Les versions 0.1.0 et 0.2.0 restent intactes.

Les valeurs initiales conservent `FluxKontextImageScale`, 8 steps, CFG 4, Euler/simple et les LoRA existantes. La LoRA Lightning 8 steps reste chargée même lorsque les steps sont modifiés : augmenter ce nombre ne constitue pas une promesse d’amélioration.

Une résolution explicite utilise `ImageScaleToTotalPixels`. Un format imposé utilise `ImageScale` avec `crop=center`. Les deux redimensionnent la référence utilisée par l’encodeur et les conditionnements, pas seulement le PNG après génération. Ces nodes étaient présents dans le catalogue Bucket consulté en lecture seule ; aucune dépendance ajoutée.

## Vérification

Contrôles réalisés : syntaxe Python/JS, unicité des identifiants HTML, hashes et identité des snapshots de workflow/prompt, inspection du diff. Aucun test applicatif, appel LLM ou rendu exécuté ; aucun service redémarré.

Tests préparés pour l’utilisateur :

```powershell
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest discover -s tests -p test_change_view_render_settings.py
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest discover -s tests -p test_lab_web.py
```

Après redémarrage du Lab sur `.panelpatch` et Ctrl+F5 : comparer les valeurs initiales, un changement de steps seul, puis une résolution et un format imposés. Les variantes n’ont pas encore été qualifiées visuellement.
