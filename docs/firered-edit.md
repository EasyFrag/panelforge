# FireRed 1.1 dans l’atelier Edit

Implémentation du 8 septembre 2026, après validation du défaut à **1 MP**.
Les essais réels et les tests restent à exécuter par l’utilisateur.

## Utilisation

Dans **Modifier avec KREA2 → Paramètres du rendu**, choisir **Moteur → FireRed 1.1**.
L’atelier reste le même : conversation de l’étape, essais, comparateur, masque,
amélioration des détails et **Valider et continuer**.

| Mode FireRed | Steps par défaut | CFG par défaut | Lightning |
| --- | --- | --- | --- |
| Lightning | 8 | 1 | LoRA fournie, force 1 |
| Standard | 40 | 4 | Désactivée dans la branche sélectionnée |

Changer de mode remet les steps et le CFG aux valeurs de ce tableau ; ces deux
champs restent modifiables. Le champ MP commence à **1**, reste modifiable et
conserve le ratio de la source. La source originale reste stockée intacte.
L’entrée envoyée à ComfyUI est normalisée selon son orientation EXIF, puis le
workflow la redimensionne en Lanczos. Aucun upscale automatique n’est ajouté.
Les dimensions réellement décodées du PNG apparaissent sur l’essai terminé.

Le changement KREA2 / FireRed conserve prompt, instruction non envoyée,
conversation et brouillons de masque. Chaque moteur retrouve ses réglages dans
l’onglet. Aucun appel LLM ni rendu n’est déclenché par ce changement : le prompt
actuel reste utilisable immédiatement, le prochain échange LLM utilisera le
profil du moteur choisi. Les influences visuelles déjà présentes dans la
conversation restent présentes.

**Reprendre prompt et réglages** restaure le moteur, la recette, le mode et les
valeurs de cet essai. Une validation transmet le candidat choisi comme source
de l’étape suivante, ainsi que ses réglages de moteur. Le PNG d’origine d’un
rendu FireRed peut aussi être réimporté : les métadonnées du graphe connu et les
sidecars exportés permettent de récupérer ses réglages.

Les réglages FireRed non enregistrés ne survivent pas à la fermeture de l’onglet ;
ceux des essais sont persistés. Ref boost, checkpoint et LoRA KREA2 restent
propres à KREA2. FireRed utilise les composants fixes du workflow fourni.

## Contrats

- Graphe fourni conservé octet pour octet dans
  `workflows/image.edit/firered/0.1.0/workflow_api.json`, SHA-256
  `dd1e6ea1668edb64de057e1dc900dfe3fd2951685e2f91dd2d7cbc5fd6456660`.
  Tous les IDs de nœuds sont liés par son manifeste ; l’application ne les connaît pas.
- Recette `firered.image_edit@0.1.0`, modèle FireRed **1.1** : version de recette
  distincte de celle du modèle. La sélection transmet ID **et** version pour
  distinguer cette recette de KREA2 `0.1.0`.
- Steps, CFG, mode, seed entier 64 bits et MP propres à FireRed. Le ratio
  `source` ne représente pas une dimension KREA2 calculée. Dimensions finales
  lues dans le PNG, y compris après récupération d’une exécution détachée.
- Profil LLM `firered.edit.conversation@1.0.0`, construit sur les consignes
  ciblées V3, avec une adaptation de cible. Les anciens profils KREA2 restent
  disponibles et identifiés dans les révisions ; aucune conversion des échanges passés.
- Stockage Edit **schéma 9**, lecture des schémas **1–8**. Les anciens essais
  sans moteur restent KREA2. Source, rendu, masque et provenance d’upscale
  gardent leurs assets distincts ; l’export identifie le moteur d’origine.
- Même file et suivi que l’atelier Edit existant. Les retouches locales ne
  deviennent pas des générations ComfyUI.

Les bornes de contrôle FireRed sont 0,1–16 MP, 1–100 steps, CFG 0–100.
Ce sont des plages de réglage, pas une garantie de mémoire GPU disponible ou de
qualité à chaque valeur. Le décodage local reste borné à 25 Mio par image et
17 millions de pixels (incluant les arrondis ComfyUI à 1024² par MP).
Les outils masque/upscale conservent leur limite existante de 16 millions de
pixels et leur tolérance de proportions de 1 %. Les arrondis de ratio du modèle
peuvent donc empêcher une retouche dans certains formats ; aucun recalage automatique.

## Vérification à lancer par l’utilisateur

Depuis le checkout actif `D:\Code\localQ\.panelpatch`, avec l’environnement du projet :

```powershell
python -m unittest tests.test_firered_edit tests.test_firered_edit_browser tests.test_run_lab_build tests.test_krea2_edit_workflows tests.test_krea2_edit_assistance_v3 tests.test_krea2_edit_web tests.test_krea2_edit_versions_browser tests.test_krea2_retouch tests.test_krea2_upscale
```

Ces tests utilisent des transports simulés et de petits PNG construits en mémoire.
Le scénario navigateur utilise Chromium local s’il est installé. Couverture :
graphe importé et deux branches, recettes de même numéro, erreurs de paramètres,
EXIF/dimensions, mémoire et feedback exact, retouche et upscale, export et nouvelle
source, anciens schémas, import PNG/sidecar, contrôles et brouillons par moteur.

Contrôles effectués pendant l’implémentation : lecture et compilation de syntaxe
uniquement, sans invocation des fonctions de l’application ni des scénarios.
Aucun test, appel LLM, rendu, téléchargement, annulation ou redémarrage de service.
Le tag `stable-avant-masque-2026-09-06` reste le point de restauration.

Pour essayer dans le Lab, redémarrer le Lab et recharger la page quand les
générations en cours sont terminées. Comparer d’abord KREA2 et FireRed depuis la
même source ; juger ensuite l’intérêt d’un MP supérieur. L’intégration ne permet
pas encore de conclure sur le gain de netteté.
