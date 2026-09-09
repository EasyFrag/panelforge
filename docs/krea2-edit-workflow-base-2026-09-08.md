# KREA2 Edit — nouvelle base importée

Fichier fourni : `C:\Users\samue\Downloads\krea2_identity_edit_new_start.json`.
Intégration autorisée le 8 septembre 2026 pour comparer les résultats. Aucune génération ni aucun test exécuté par l'agent.

## Différences observées

| Élément | Workflow 0.1.0 | Base importée 0.2.0 |
| --- | --- | --- |
| Encodeur texte image | `qwen3-vl-4b-heretic.safetensors` | `qwen3vl_4b_bf16.safetensors` |
| Checkpoint par défaut | Kroma v0.2 Turbo | KREA2 Turbo bf16 |
| Ref boost par défaut | 2.5 | 4 |
| Sortie ComfyUI | SaveImageKJ + légende/sidecar | SaveImage natif |
| LoRA facultatifs | Loader présent même sans sélection | Aucun dans le graphe de base ; ajout uniquement si sélection explicite |
| Format du modèle de workflow | Portrait 9:16, 1 MP | Carré 1:1, 1 MP |

Le checkpoint, le Ref boost, le ratio, les MP, les steps et la seed sont des contrôles de l'atelier : ils remplacent les exemples contenus dans le fichier. Les essais récents audités utilisaient déjà KREA2 Turbo, malgré le défaut Kroma de l'ancien modèle de workflow.

**Géométrie inchangée** : Identity Edit v1.2 ×1, FIT, source_image + VAE + target_latent branchés, multiple 8 et grounding 768. Sampling identique : Euler / Simple, 10 steps par défaut, CFG 1, denoise 1 ; négatif vide ancré dans la même image. Le nouveau fichier ne propose pas de correction de géométrie supplémentaire. Le changement d'encodeur est une différence concrète à évaluer, sans gain de netteté présumé.

Deux GET en lecture seule des définitions ComfyUI ont confirmé la disponibilité de Qwen standard et de KREA2 Turbo sur Bucket. Aucun téléchargement, import de modèle sur GPU ou redémarrage.

## Utilisation dans le Lab

Après redémarrage du Lab et rechargement de la page par l'utilisateur :

1. Ouvrir **Modifier avec KREA2 → Paramètres du rendu**.
2. Choisir **Base importée · Qwen standard (0.2.0)** dans **Workflow**.
3. Pour partir de la base proposée, cliquer **Reprendre les réglages de base** : Turbo bf16, Ref boost 4, 10 steps et aucun LoRA facultatif. Le prompt, le ratio, les MP et la seed sont conservés.
4. Lancer soi-même un rendu, puis comparer avec **Historique (0.1.0)** si souhaité.

Le sélecteur seul change le workflow du prochain rendu et conserve les réglages affichés. C'est utile pour comparer Qwen standard et Heretic avec le même checkpoint/Ref boost/seed/prompt. Le bouton de base modifie plusieurs paramètres à la fois : un éventuel gain ne sera alors pas attribuable au seul encodeur.

La base 0.2.0 est le défaut pour les nouveaux essais des étapes actives ordinaires, y compris dans les anciens ateliers. Les valeurs de modèle/Ref boost déjà présentes restent affichées jusqu'à un changement explicite ou l'usage du bouton. Un essai validé ou repris avec **Reprendre prompt et réglages** retrouve sa version exacte ; un choix non envoyé reste dans le brouillon de l'onglet lors des navigations. Les étapes historiques restent consultables et immuables.

Le prompting **V2/V3** reste un choix indépendant. Aucun changement de prompt système, de résolution existante, de masque, d'harmonisation ou d'upscaling dans ce patch.

## Implémentation et provenance

- Snapshot `workflows/image.edit/krea2-identity/0.2.0/workflow_api.json` **identique octet pour octet** au fichier fourni, SHA-256 `7f9e066f4ac3bee9b9aa5aa1cb2765d724b8851bc18b11303d5f673912184a19`. Les images et prompts d'exemple sont toujours remplacés par les entrées explicites du rendu.
- Manifeste version 2 : SaveImage sans liaison de légende, extension des LoRA facultatifs décrite dans le manifeste avec ses connexions. Sans LoRA sélectionné, aucun nœud supplémentaire n'est inséré ; avec sélection, le loader habituel est ajouté avant Identity Edit et les conditionnements texte. Jusqu'à dix LoRA comme auparavant.
- Ancien manifeste et graphe 0.1.0 inchangés. Les deux versions sont chargées explicitement dans `scripts/run_lab.py`.
- Chaque nouvel essai garde sa référence de workflow complète. Les anciens essais sans ce champ utilisent la référence historique de leur source. Le choix reste fixé pendant la file, l'exécution et la récupération d'une exécution détachée.
- Une retouche hérite de la version de sa génération d'origine, y compris lors d'une reprise de masque. Validation, source suivante et sidecar d'export conservent cette provenance. La composition locale reste identifiée séparément.
- Stockage Edit **schéma 7**, lecture des schémas 1–6 conservée. Aucune migration globale des données runtime. Les anciennes versions du logiciel ne lisent pas les projets nouvellement sauvegardés en schéma 7 ; l'ancien workflow reste utilisable dans le Lab actuel.
- La sauvegarde native ne crée plus le `.txt` ComfyUI de SaveImageKJ. Le projet local conserve prompt, réglages, workflow compilé et historique ; l'export validé continue de produire son sidecar JSON et les fichiers de provenance de retouche.
- API : catalogue `workflows` et défauts issus du manifeste dans le spec ; `workflow_version` facultatif à la préparation d'un essai, défaut courant 0.2.0 au lancement standard ; version et empreinte exposées par essai. Version inconnue refusée avant création ou soumission.
- Cache Edit JS **20260908.3**. Tag `stable-avant-masque-2026-09-06` conservé, aucun commit/push demandé.

## Vérification

Correctif du 2026-09-08 : `workflow_version` avait été déclaré dans le body Assisted au lieu du body Edit, provoquant un HTTP 500 à la préparation d'un essai. Le champ facultatif est désormais dans `Krea2EditAttemptBody`. Le Lab doit être redémarré par l'utilisateur pour charger ce contrat corrigé ; aucun changement ComfyUI ni cache frontend requis. Le test HTTP ci-dessous couvre les deux versions explicites, l'omission/null (défaut courant) et une version inconnue refusée sans nouvel essai. Il est préparé mais **non exécuté** :

```powershell
python -m unittest tests.test_krea2_edit_web.Krea2EditWebTest.test_imported_workflow_defaults_and_selection_are_exposed_without_rendering
```

Tests préparés, **non exécutés** :

```powershell
python -m unittest tests.test_krea2_edit_workflows tests.test_krea2_edit tests.test_krea2_edit_web tests.test_krea2_retouch tests.test_krea2_edit_versions_browser tests.test_run_lab_build
```

Ils couvrent le graphe importé exact, l'ancien hash, l'extension LoRA facultative, les paramètres conservés, le routage de versions dans un ancien atelier, la persistance, la lecture historique, la validation, l'export, les retouches et le bouton de base sans génération automatique. Faux gateways/ComfyUI et fichiers temporaires uniquement dans ces scénarios.

Contrôles statiques de l'agent : syntaxe Python, compilation JavaScript/fixture navigateur sans invocation, lisibilité JSON, empreintes et liaisons des manifestes. Aucun appel LLM, génération, test ou redémarrage exécuté. La qualité visuelle reste à évaluer par l'utilisateur.
