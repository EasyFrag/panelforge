# PanelForge — KREA2 V4, Qwen V2 et correctifs Histoires

Sauvegarde du code actuel du 23 septembre 2026, depuis `4f89ab6`.

- Branche : `snapshots/krea4-qwen2-story-fixes-2026-09-23`
- Tag : `snapshot-krea4-qwen2-story-fixes-2026-09-23`

## Changements

- **Histoires et MiniMax** : un remplacement des seules images de référence crée une nouvelle préparation et un nouvel atelier de rendu, sans appel LLM supplémentaire. Le prompt, les réglages et l’historique restent conservés. Contrôles côté serveur pour les relances manuelles et en chaîne ; les changements narratifs, d’ordre ou de rôle nécessitent une nouvelle préparation. L’interface distingue les images à synchroniser et les anciennes préparations.
- **Automatique, chat et noms fruités** : correction des seuls blocages, relecture informée des corrections précédentes, questions sans réécriture ni changement du mode, actions question/modification/validation explicites. Consignes de prénoms fruités pour les nouveaux projets ; noms existants conservés.
- **Modifier avec Qwen V2** : projets visuels, étapes, guide local dessiné sur l’image, comparaison directe au pointeur, références typées et finition colorimétrique locale. Workflow 2.0 utilisant les poids BF16 de l’installation, diagnostic détaillé des rejets ComfyUI ; recadrage et DLSS partagés, retouche dédiée retirée.
- **KREA2 Assisted V4** : bibliothèque locale de prompts, recherche sémantique et reclassement selon la scène, trois propositions inspectables et exemple choisi enregistré. Le parcours principal analyse d’abord la scène via le LLM, recherche localement, puis rédige le prompt. L’action « Sans actualiser l’inspiration » réutilise l’exemple retenu. V3 reste disponible explicitement. Compatibilité de lecture des anciens projets maintenue.
- **Dépendances** : ajout de `fastembed>=0.7,<1` et `numpy>=1.26,<3` pour la recherche locale.

L’adaptation d’une histoire dans une autre langue reste une proposition : aucune copie linguistique ni traduction automatique de production n’est implémentée dans cette version. Le correctif de découpage des citations imbriquées dans le plan vidéo reste également en attente.

## Validation

Pour cette publication : contrôles statiques Python, JavaScript, JSON/TOML, empreinte du workflow et diff ; contrôle de la sélection des fichiers. Aucun test fonctionnel, appel LLM, rendu ou redémarrage lancé.

Le journal du développement KREA2 V4 rapporte 86 tests ciblés et deux fixtures navigateur passés avant la sauvegarde ; ils ne sont pas relancés pour cette publication. Les régressions Histoires/Qwen/Comfy ajoutées restent à exécuter par l’utilisateur. Cette sauvegarde ne constitue pas une validation complète du dépôt.

## Données et reprise

Les projets runtime, images, vidéos, traces complètes, modèles, fichiers de lancement personnels et caches sont exclus. La bibliothèque de prompts V4 et son index restent dans `workspace/prompt_libraries/bunnys_wildcards_1` : sauvegarder ce dossier séparément pour restaurer l’installation sur une autre machine. V4 signale son indisponibilité si la bibliothèque requise manque.

Sur l’installation actuelle, après la fin des traitements, redémarrer le Lab et faire Ctrl+F5 pour charger les changements. La publication n’interrompt aucun traitement.

## Notes détaillées

- [Synchronisation des images des histoires](../diagnostics/story-reference-image-refresh-2026-09-23.md)
- [Automatique, chat et noms fruités](../diagnostics/story-auto-chat-naming-patch-2026-09-23.md)
- [Journal de continuité](../../.agent/CONTINUITY.md)

Tests ciblés à lancer par l’utilisateur :

```powershell
python -m unittest tests.test_episode_reference_refresh tests.test_episodes_web tests.test_episodes_browser tests.test_h3_render_controls_browser tests.test_story_workflow
python -m unittest discover -s tests -p "test_qwen_edit*.py"
python -m unittest discover -s tests -p "test_krea2_assisted*.py"
python -m unittest tests.test_comfy_client
```
