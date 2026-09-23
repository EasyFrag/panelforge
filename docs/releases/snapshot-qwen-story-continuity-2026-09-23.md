# PanelForge — Qwen et continuité des histoires, 23 septembre 2026

Cette sauvegarde rassemble les évolutions réalisées depuis `3a5d85b` : édition d’images Qwen, continuité visuelle des histoires et correctifs de navigation, de lancement des rendus et de messages de troncature.

- Branche : `snapshots/qwen-story-continuity-2026-09-23`
- Tag : `snapshot-qwen-story-continuity-2026-09-23`

## Changements

- **Modifier avec Qwen 2.1** : projets, base et étapes successives, conversation, essais, comparaison avant/après, sauvegardes et exports. Les images jointes à la conversation guident le LLM ; les références de rendu sont transmises explicitement à Qwen pour les compositions à plusieurs images. Réglages adaptés au workflow versionné, sans recadrage, retouche locale ni upscaler dans cet atelier.
- **Continuité des histoires** : registre facultatif pour les états physiques, tenues, possessions et objets importants. Suivi textuel par défaut, références visuelles lorsque nécessaires et variantes liées à l’identité via Qwen. Contrats des nouveaux appels en 2.2, anciens contrats 2.1 compatibles ; aucune migration automatique des fabrications historiques.
- **Clarté narrative** : liens entre personnages explicités, progression dramatique simple, passé séparé des nouvelles intentions, relecture fondée sur ce que le spectateur voit et entend. La recette éditoriale passe en révision 4 ; un retournement du rapport de force peut suffire à la chute.
- **Navigation Image Lab** : accès à « Changer la vue » rétabli dans la navigation commune. Fonctionnement confirmé par l’utilisateur.
- **Démarrage Qwen** : même libellé de tâche utilisé lors de la réservation et de l’acquisition de la machine, même après renommage du projet ; libération de la réservation en cas d’échec au démarrage.
- **Troncature du scénario** : distinction entre réponse partielle conservée et absence de scénario. Archivage du raisonnement lors d’une reprise, fermeture du flux HTTP lorsque le consommateur termine. Le budget demandé reste à 80 000 tokens.

**La détection automatique des répétitions et l’arrêt associé ont été retirés à la demande de l’utilisateur.** Un raisonnement répété n’est pas interrompu pour ce motif. Les limites du fournisseur et l’annulation manuelle restent applicables.

## Validation

Contrôles statiques Python, JavaScript, JSON et du diff réalisés pour la publication. Les tests ciblés sont inclus mais restent à lancer par l’utilisateur, conformément à sa préférence. Aucun appel LLM, génération d’image/vidéo ou redémarrage n’est effectué pour publier cette sauvegarde. La qualité narrative et la fidélité visuelle restent à évaluer sur les essais réels.

Le runtime, les médias, les traces complètes et les fichiers de lancement personnels ne font pas partie de la sauvegarde. Les fixtures réduites nécessaires aux tests sont incluses. Les tags antérieurs sont conservés et la branche master reste inchangée.

## Reprise

Après la fin des traitements, redémarrer le Lab depuis le worktree utilisé et actualiser avec Ctrl+F5. Un prompt Qwen déjà enregistré peut être relancé directement sans nouvelle conversation. Pour l’histoire du restaurant dont la réponse était vide, reprendre l’étape nécessite un nouvel appel : aucun scénario n’avait été reçu.

- [Guide de l’atelier Qwen](../design/qwen-edit-guide.md)
- [Guide de continuité visuelle](../design/story-visual-continuity-guide.md)
- [Audit des histoires](../diagnostics/audit-histoires-continuite-2026-09-22.md)
- [Diagnostic de la troncature](../diagnostics/story-reasoning-loop-2026-09-22.md)

Tests ciblés à lancer par l’utilisateur depuis le dépôt :

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_qwen_edit tests.test_qwen_edit_web tests.test_qwen_edit_browser tests.test_story_visual_continuity tests.test_episode_visual_continuity tests.test_story_reasoning tests.test_navigation_and_resource_preview_browser tests.test_story_schema_transport tests.test_prompt_lab.OpenAICompatibleGatewayTest
```
