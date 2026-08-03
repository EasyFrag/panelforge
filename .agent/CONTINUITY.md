# CONTINUITY

## Goal

- Construire PanelForge comme un monolithe modulaire centré sur un canon visuel approuvé et des presets ComfyUI versionnés.

## Current state

- Works:
  - Squelette Python minimal créé.
  - Frontières `domain`, `application`, `features` et `infrastructure` posées.
  - Convention initiale des workflows documentée.
  - Dépôt Git initialisé dans `D:\Code\panelforge`.
  - Test d'import standard library validé (`python -m unittest discover -s tests`).
  - Baseline minimale enregistrée dans un commit Git initial.
  - Audit legacy ciblé terminé: protocoles ComfyUI `queue/history/view/upload` et noyau d'appel LLM OpenAI-compatible isolés des anciennes couches d'orchestration.
  - `ComfyHttpClient` implémenté en standard library avec quatre opérations: `submit_workflow`, `get_history`, `download_output`, `upload_image`.
  - Le transport utilise `base_url`, `client_id` et timeout explicites; les erreurs HTTP, réseau et JSON ne sont pas interceptées.
  - Six tests unitaires passent, dont cinq sur le protocole ComfyUI sans serveur réel (`python -m unittest discover -s tests -v`).
  - Smoke test manuel ajouté dans `scripts/smoke_comfy.py`: chargement d'un workflow API externe, soumission, polling borné, extraction de la première image, téléchargement et validation PNG.
  - Le smoke test affiche le corps des erreurs HTTP ComfyUI et les causes d'accès réseau sans ajouter cette politique au client de transport.
  - Onze tests unitaires passent au total, dont cinq tests ciblés sur le polling et l'extraction du smoke test.
  - Smoke test réel réussi contre ComfyUI sur `http://192.168.1.72:8188`: prompt `6e32c579-b43d-4adb-a1fd-860553fb7888`, sortie PNG du node `15` téléchargée (`2699593` octets).
  - `scripts/smoke_comfy.py` peut maintenant conserver explicitement le PNG téléchargé via `--save-output`, sans écraser un fichier existant; douze tests unitaires passent.
  - Première expérience `character.bootstrap` générée avec le squelette de prompt riche, négatif dédié, `1104x1472`, `CFG=1.05`, 8 steps et seed `124327953304464`; prompt Comfy `1b16c411-050a-4f0a-9153-70038726766f`.
  - Le candidat PNG est conservé dans `workspace/experiments/character_bootstrap/qwen_2512_lightning/v0/`; adhérence visuelle globale bonne (identité, tenue, mains, fond, absence de texte).
  - Premier contrat métier pur ajouté: `character.change_view` décrit l'asset source, 8 azimuts, 4 élévations et 3 cadrages sans dépendre de ComfyUI ou de Qwen.
  - Première recette cataloguée intégrée sous `workflows/character.change_view/qwen-edit-2511-multiple-angles/0.1.0`: workflow fourni conservé exactement, manifest, prompt protégé et plan de validation manuelle.
  - Le renderer produit déterministement les 96 prompts officiels `<sks> azimuth elevation shot_size`; le rewriter LLM est interdit pour cette recette.
  - Le loader vérifie hashes, vocabulaire officiel, bindings, output et valeurs critiques du workflow; chaque construction retourne une copie isolée pour éviter la contamination entre runs.
  - `ComfyHttpClient.upload_image` ajouté avec multipart standard library, `overwrite=false`, référence de retour typée et nom serveur utilisé dans `LoadImage`.
  - Smoke test réel `upload -> view -> build -> submit -> history -> download` réussi sur `http://192.168.1.72:8188`: prompt `58ba954a-18e0-4584-8ec5-7a8be3a8a93d`, sortie node `9` de 880910 octets.
  - Le résultat `back / low / wide` et sa provenance sont conservés hors Git dans `workspace/experiments/character_change_view/qwen_edit_2511_multiple_angles/v0.1.0/`; statut technique réussi, approbation humaine en attente.
  - Trente-quatre tests unitaires passent (`python -B -m unittest discover -s tests -v`).
- Broken / missing:
  - Aucun cas d'usage applicatif ne relie encore durablement catalogue d'assets, upload, génération, polling et enregistrement du lineage; le smoke actuel reste un harness manuel.
  - La matrice visuelle de neuf cas est encore en attente et la recette reste `experimental`; un seul cas réel a été généré.
  - `character.bootstrap` reste une expérience hors Git et n'est pas encore un preset intégré.
  - Aucune interface utilisateur.

## Decisions

- Les expérimentations workflow/prompt ont lieu manuellement dans ComfyUI, hors de PanelForge.
- Un preset intégré est immuable et décrit explicitement workflow, prompt, bindings, modèles, LoRA et variables.
- Premier jalon: fiche personnage manuelle -> candidats -> sélection -> édition -> canon approuvé.
- Vidéo hors V1.
- Premier port technique retenu: transport ComfyUI minimal `submit/history/download`, configuration explicite, timeout explicite et exceptions remontées; pas de WebSocket, retry, logs ou politique d'erreurs dans cette première brique.
- L'adapter LLM viendra avec l'import d'histoire et n'exposera d'abord qu'un appel `complete`; parsing JSON et validation resteront hors du transport.
- Le polling présent dans `scripts/smoke_comfy.py` reste un harness de validation manuelle et ne constitue pas encore l'orchestration applicative.
- Les variantes en cours d'exploration restent dans `workspace/experiments` (ignoré par Git); elles ne deviennent des presets versionnés qu'après validation qualitative explicite.
- Pour `character.change_view`, le LLM peut éventuellement choisir les enums métier mais ne peut jamais réécrire la chaîne technique `<sks> azimuth elevation shot_size`.
- Le workflow API est la vérité exécutable; le manifest conserve les bindings, la grammaire et les assertions critiques sans dupliquer un bloc de paramètres runtime concurrent.
- Toute vue dérivée reste un candidat jusqu'à approbation humaine et ne remplace jamais automatiquement l'image canonique source.

## Next steps

1. Faire approuver ou rejeter visuellement le smoke `back / low / wide`, puis exécuter la matrice manuelle de neuf cas à source et seed fixes sur deux ou trois personnages.
2. Ajouter le cas d'usage applicatif qui enchaîne asset source -> upload -> recette -> run -> output avec provenance persistée, sans encore choisir de framework UI.
3. Reprendre séparément la validation du candidat `character.bootstrap`, puis le promouvoir en preset versionné lorsqu'il est réellement approuvé.

## Risks / open questions

- La recette d'angle est techniquement validée mais pas qualitativement généralisée: un seul sujet et une seule combinaison réelle ne suffisent pas à la déclarer stable.
- Le smoke `back / low / wide` respecte nettement l'angle et le cadrage, mais invente les jambes/chaussures, des détails arrière de tenue et un studio visible; l'identité faciale n'est pas vérifiable de dos.
- Le workflow manuel contient encore quatre slots LoRA désactivés; leur présence peut réduire sa portabilité sur une autre instance ComfyUI et devra être testée dans une future version nettoyée.
- Le SHA-256 Civitai du LoRA d'angle est enregistré comme provenance, mais le hash du fichier réellement installé sur le serveur ComfyUI n'est pas encore vérifié.
- Sur le candidat `v0`, le cadrage s'arrête plutôt au haut des cuisses qu'aux genoux et la cicatrice semble placée du côté miroir; les directions anatomiques gauche/droite restent fragiles en text-to-image.
- À `CFG=1.05`, le négatif est théoriquement actif mais très faiblement; son utilité n'est pas encore démontrée par un A/B à seed fixe.
- Le choix du framework UI reste volontairement ouvert.
- Le code legacy reste disponible en lecture dans `D:\Code\localQ`; tout portage devra rester ciblé et accompagné de tests plutôt que copier des modules entiers.
