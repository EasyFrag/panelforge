# Usine : conserver la prévision pendant les attentes — 28 septembre 2026

## Cause du second clignotement

Le premier correctif conservait la prévision pendant une requête et après une erreur. Il ne traitait pas une réponse réussie contenant des durées nulles. Le simulateur peut produire cette réponse lorsqu’une machine est momentanément bloquée par une attente dont la durée est inconnue, même si les durées des étapes sont connues. La progression de la production faisait donc alterner les horaires et le message d’attente.

Les captures et la lecture du code identifient ce chemin. Un relevé en lecture seule a trouvé les six fiches de préparation avec une estimation numérique au moment du relevé (environ 95 minutes pour la sélection) ; il ne constitue pas une reproduction navigateur du défaut.

## Correctif

- Pour une sélection et des révisions de fiches inchangées, chaque durée précédemment calculée est conservée si la nouvelle réponse ne peut plus la calculer. Les nouvelles valeurs numériques restent prioritaires.
- La ligne affiche « Reste ≈ … » et « Estimation conservée ». La durée conservée est figée pendant l’attente ; aucune nouvelle heure de fin n’est promise. Les détails indiquent que l’attente reste à confirmer.
- Le total est conservé/recomposé à partir des budgets connus de toutes les vidéos sélectionnées. Si une vidéo n’a encore jamais reçu de durée, le total reste à préciser.
- Une réponse chiffrée rétablit automatiquement les horaires actualisés. Les chiffres peuvent donc encore évoluer avec la production ; ils ne sont pas figés définitivement.
- Un changement de preset, de réglages ou de sélection invalide les anciennes valeurs. Aucun résultat d’une autre configuration n’est réutilisé.
- Une hauteur minimale de 58 px et une largeur minimale de 140 px stabilisent le bloc de prévision non vide en Préparation. Les autres onglets ne reçoivent pas cette réserve d’espace.

Le correctif reste côté navigateur : aucun changement de calcul serveur, d’ordonnancement, de protection thermique ou de données runtime.

## Fichiers et vérifications

Checkout actif : D:/Code/panelforge-krea2-flux.

- static/video-factory-monitor.js : conservation par vidéo, total indicatif, détail d’attente.
- static/video-factory-monitor.css : dimensions stables du bloc de prévision.
- static/index.html : versions de cache du script et de sa feuille de style passées à 20260928.preview3.
- tests/test_factory_preview_browser.py : troisième scénario préparé avec réponses synthétiques. Couvre absence de première valeur, réponse mixte, réponses nulles répétées, attente longue, retour des durées, hauteur stable, invalidation par preset/sélection et absence de mutation des réponses.

Vérifications effectuées : AST/compilation Python, compilation syntaxique V8 des deux scripts et des quatre blocs de scénario/initialisation, références HTML/cache, structure CSS et git diff --check. Aucun scénario ni test fonctionnel/navigateur exécuté, conformément à AGENTS.md actif. La hauteur n’a donc pas encore été mesurée dans un navigateur.

Activation : Ctrl+F5 sur la page Usine ; aucun redémarrage nécessaire. Tests laissés à l’utilisateur, depuis le checkout actif :

```powershell
$env:PYTHONPATH = "D:/Code/panelforge-krea2-flux/src"
D:/Code/panelforge/.venv/Scripts/python.exe -m unittest tests.test_factory_preview_browser tests.test_video_factory_web
```

Sauvegardes, diffs, relevé et contrôles : D:/Code/panelforge/.agent/diagnostics/factory-preview-retention-20260928/. Aucun service redémarré, traitement commandé, média généré, commit ou push.
