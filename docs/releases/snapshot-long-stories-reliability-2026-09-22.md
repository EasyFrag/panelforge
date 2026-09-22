# PanelForge — Fiabilité des histoires et des scènes, 22 septembre 2026

Version de sauvegarde des correctifs depuis `ccb8698` (Histoires longues V2 du 20 septembre). Les versions de l’application et des recettes restent inchangées.

- Branche : `snapshots/long-stories-reliability-2026-09-22`
- Tag : `snapshot-long-stories-reliability-2026-09-22`

## Changements inclus

- **Réglages vidéo par scène** : sauvegarde automatique des modifications, attente avant navigation ou lancement, confirmation visible et durée technique affichée. Passer une scène à 8 secondes conserve ce réglage pour le prochain rendu sans modifier le prompt ou la durée narrative.
- **Progression des traitements** : les préparations distinguent attente, démarrage et génération réelle grâce aux événements de la passerelle LLM. Planifié en ambre, actif en bleu, terminé en vert avec coche, erreur en rouge ; suivi Vidéo/DLSS et dépendances visibles. Le Rédacteur ne reste pas annoncé en file après l’échec du Plan.
- **Récupération de réponses longues** : conservation des brouillons, correction locale limitée de certaines expressions de chaînes, et au plus une tentative supplémentaire de réparation de syntaxe avec contrôle des valeurs. Le plafond de sortie reste à 80 000 tokens.
- **Mémoire sans secret** : traitement du cas `secrets=[]` avec `knowledge.secret_id=null` après validation des personnages et événements. Les références réellement invalides restent rejetées.
- **Dépendances d’événements omises** : une relecture `edit_outline` conservant unités, IDs et ordre peut récupérer ses `depends_on` absents depuis l’arc enregistré. Aucun nouvel appel pour cette récupération ; normalisation tracée. La création initiale, les réorganisations et les autres champs invalides restent contrôlés.
- **Consignes et diagnostics** : contrat des événements explicite, erreurs localisées et consigne du Plan sur les connaissances et intentions propres à chaque personnage.
- Tests de régression ciblés, diagnostics des runs et fiche d’adaptation française de la vidéo de référence inclus.

## Validation et limites

Contrôles statiques de syntaxe Python/JavaScript et du diff effectués pour la publication. Les tests automatisés sont inclus mais **ne sont pas exécutés**, selon le choix de l’utilisateur. Aucun appel LLM, rendu ou redémarrage de service n’est déclenché pour cette sauvegarde.

La récupération des métadonnées ne garantit pas la qualité éditoriale : les audits relèvent notamment des passages en français/anglais mélangés dans certaines relectures. Le défaut de continuation d’une ancienne histoire vers le moteur long V2 est documenté et **reste à corriger** ; cette version ne prétend pas le résoudre.

Les sources, tests et documents sont versionnés. Les vidéos, assets, projets générés, transcriptions et traces LLM complètes restent dans le workspace local ignoré. Les liens de preuves locales dans les audits ne sont donc pas accessibles depuis GitHub.

## Utilisation

Après la fin des traitements actifs, redémarrer PanelForge puis recharger le navigateur avec Ctrl+F5. Un brouillon compatible avec les nouvelles normalisations peut être repris avec **Revalider la réponse reçue** sans nouvelle génération. Une chaîne déjà lancée conserve les paramètres qu’elle avait capturés.

## Documentation et tests ciblés

- [Patch scènes et réponses](../patch-scenes-et-reponses-2026-09-20.md)
- [Diagnostic des événements sans depends_on](../diagnostics/correctif-evenements-2026-09-22.md)
- [Audit des derniers runs du 20 septembre](../diagnostics/audit-runs-2026-09-20-1752.md)
- [Réglages et récit français de la vidéo de référence](../diagnostics/download21-reglages-et-recit-francais.md)

Commande à lancer par l’utilisateur dans l’environnement Python du projet :

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_story_response_recovery tests.test_long_story_response_contracts tests.test_long_stories tests.test_episodes tests.test_machine_work tests.test_episodes_browser
```
