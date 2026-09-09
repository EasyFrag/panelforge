# Reprendre une étape KREA2 Edit validée

Patch du 7 septembre 2026. Les tests ci-dessous sont préparés mais **non exécutés**. Aucun appel LLM, rendu ou redémarrage de service pendant l'implémentation.

## Usage

Dans la frise, ouvrir une étape validée puis cliquer **Reprendre depuis cette étape**, près du titre. Une version de travail s'ouvre au même rang, avec sa source d'origine, sa conversation, ses essais et le prompt/réglages de l'essai validé. Ce choix reste exact lorsqu'un essai plus récent avait été généré mais non validé. Les images et masques enregistrés sont réutilisés, sans génération automatique.

Modifier par exemple les mégapixels, lancer ses essais puis **Valider et continuer**. Cette validation rend la nouvelle version active. La prochaine étape reçoit exactement l'image choisie et ses réglages, avec une conversation et des essais vides. L'ancienne suite reste consultable dans **Version du parcours** ; elle n'est ni effacée ni recalculée. Ses étapes non validées deviennent elles aussi en lecture seule. Reprendre à nouveau une étape validée d'une ancienne version reste possible.

Pendant le travail, le brouillon n'affecte pas la version active. Plusieurs brouillons peuvent exister ; la dernière validation détermine la version active, indépendamment de l'ordre de création des brouillons. Une opération LLM ou un rendu encore actif dans l'ancienne version doit finir avant la bascule. Aucun travail distant n'est annulé par la reprise.

**Recommencer cette étape** conserve son rôle distinct : vider le travail de l'étape courante, sur la même source. **Reprendre depuis cette étape** conserve le travail d'une étape validée dans une nouvelle version. Les brouillons de formulaire et de masque dans l'onglet restent séparés par source lors de la navigation. Un masque enregistré peut être rouvert sur ses deux images d'origine ; aucun masque d'une étape suivante n'est automatiquement appliqué à la nouvelle image.

## Stockage et API

- Schéma Edit **6**, lecture des schémas 1–5 conservée. Aucun ancien fichier n'est migré globalement.
- Chaque version dispose de son propre `project_id` et de sources distinctes pour le préfixe validé et l'étape reprise. Seules les métadonnées sont copiées ; les IDs d'assets restent partagés et immuables. Les étapes suivantes ne sont pas copiées.
- `revision` contient la famille, le numéro de version, le projet/étape/essai d'origine et la clé de requête. `copied_from_source_id` identifie l'origine de chaque copie. Les traces/workflows historiques des essais copiés restent dans leur source d'origine ; ils ne sont pas soumis à nouveau.
- `revision_activation` est enregistré sur l'étape reprise lors de sa validation. Les statuts actif/historique/brouillon sont dérivés de ces données durables. Les autres projets ne sont pas modifiés pour les archiver.
- Création du brouillon : écrire le préfixe et l'étape puis publier la source racine en dernier. Une copie partielle reste invisible ; une nouvelle tentative peut la terminer avec la même identité. Les écritures de fichiers sont atomiques.
- `POST /api/image-lab/krea2-edit/sources/{source_id}/resume`, corps `{ "request_id": "identifiant-unique" }`. Idempotent pour la même étape/clé, y compris après validation du brouillon. Réponse : source reprise et catalogue des versions.
- `GET /api/image-lab/krea2-edit/projects/{project_id}` renvoie la chaîne complète d'une version. Les réponses de liste et de lecture d'une source incluent aussi le catalogue des versions. La limite de liste sélectionne les entrées récentes ; leurs chaînes complètes et les versions actives/brouillons de ces familles sont incluses pour éviter une frise tronquée.
- Les mutations d'une ancienne version sont refusées côté service, même depuis un ancien onglet. Les résultats de retouche arrivés après une bascule ne sont pas enregistrés dans la version historique. Les retours de navigation/polling périmés sont ignorés côté interface.

## Export

Le dossier existant de l'ancienne version reste intact. La nouvelle version a un dossier distinct, identifié par son `project_id`, contenant uniquement son préfixe et ses résultats validés. Le manifeste précise la version et la provenance de reprise. La cohérence des liens parent/source/image est vérifiée avant export. Un échec d'export conserve la validation et peut être réessayé, comme auparavant.

## Vérification à lancer par l'utilisateur

```powershell
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_krea2_edit_versions tests.test_krea2_edit_versions_browser tests.test_krea2_edit tests.test_krea2_edit_web tests.test_krea2_retouch tests.test_krea2_retouch_browser
```

Ces tests utilisent uniquement des données synthétiques et des services simulés. Ils couvrent la reprise du premier rang et d'un rang intermédiaire, les versions historiques, l'essai sélectionné et ses réglages, la conservation de la conversation, les retouches, l'absence de doublon, la copie interrompue, l'échec de validation, les gardes de mutation, la navigation et l'export de la chaîne exacte. Le test navigateur utilise un Chromium local s'il est installé.

Caches : Edit JS `20260907.5`, CSS `20260907.6`. Retouche Canvas et H3 inchangés par ce patch. Point de restauration Git conservé : `stable-avant-masque-2026-09-06`.
