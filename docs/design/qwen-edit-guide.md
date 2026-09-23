# Atelier Modifier avec Qwen

Implémentation du 22 septembre 2026, dans `D:\Code\panelforge-krea2-flux`.

## Mise en route

Quand les traitements en cours sont terminés, redémarrer PanelForge avec son lanceur habituel depuis ce worktree, puis actualiser le navigateur. Ouvrir **Image Lab → Modifier avec Qwen**.

Les trois modèles sont ceux du workflow fourni : `qwen_image_2.1_bf16.safetensors`, `qwen3vl_8b_bf16.safetensors` et `qwen_image_2.1_vae_bf16.safetensors`. Leur présence et le nœud natif `TextEncodeQwenImage21` avaient été vérifiés en lecture seule pendant l’alignement. Aucun rendu réel n’a été exécuté pour cette implémentation.

## Essai 1 : une photo pour guider le LLM

1. Créer un projet avec **Modifier une image**.
2. Dans la conversation, **Joindre une image**, la coller ou la déposer dans le champ de conversation.
3. Écrire : « Reprends les couleurs de cette photo, en gardant la composition et les matériaux de mon image. »
4. **Envoyer** prépare la réponse française et le prompt anglais en un appel LLM. Le modèle choisi doit accepter les images.
5. Vérifier le résumé, puis **Générer l’image**.

La vignette porte le badge Assistant. Qwen ne reçoit que la source et le prompt ; l’inspiration reste destinée au LLM.

## Essai 2 : composer avec plusieurs personnages

1. Partir d’un décor, ou choisir **Nouvelle composition** pour créer la scène à partir des références.
2. Sous l’aperçu, utiliser **＋ Référence** pour ajouter deux portraits. Plusieurs fichiers peuvent être sélectionnés ensemble.
3. Ouvrir **Usage et rôle** sur chaque vignette et les nommer Léa et Marc. Le rôle est facultatif.
4. Écrire : « Place @Léa à gauche et @Marc à droite. Ils discutent. Garde ce décor. » Adapter la dernière phrase si la scène est créée de zéro.
5. Envoyer, vérifier l’instruction, générer.

Avec un décor source, Qwen reçoit trois images ; sans décor, les deux portraits. Une image de palette peut aussi être jointe uniquement à la conversation pendant cette même étape.

Pour passer une inspiration à Qwen : **Usage et rôle → Utiliser aussi pour le rendu → Enregistrer**. L’ancien prompt devient à actualiser ; cette modification ne déclenche pas d’appel LLM caché.

## Réglages et parcours

- Réglages initiaux : taille source (1 MP en nouvelle composition), 25 steps, CFG 1, Euler/Simple, denoise 1.
- Le format est proposé pour une nouvelle composition ; l’édition conserve celui de la source.
- La seed est stockée comme texte pour préserver ses 64 bits. Elle est réutilisée par défaut ; **Nouvelle variation** la change sans générer. Désactiver la réutilisation choisit une nouvelle seed à chaque rendu.
- Le prompt négatif apparaît au-dessus de CFG 1. Aucun réglage artificiel de fidélité, recadrage, retouche, LoRA ou upscaler dans cet onglet.
- Les paramètres, noms, références et brouillon du message sont enregistrés automatiquement. Le prompt édité manuellement possède une action explicite **Enregistrer ce prompt**.
- Chaque essai garde ses images, rôles, prompt, paramètres et workflow compilé. **Reprendre ces réglages** restaure le contexte du résultat sélectionné et garde les références plus récentes dans les images réutilisables.
- **Valider et continuer** utilise le résultat choisi comme source de l’étape suivante. Les références antérieures sont accessibles via **Réutiliser une image** ; elles ne sont pas réactivées automatiquement.
- Les étapes passées sont consultables. **Reprendre d’ici** crée une nouvelle version dans la liste des projets, sans supprimer la précédente.
- Le raisonnement exposé par le fournisseur et sa réponse brute restent consultables par message. Une réponse complète conservée peut être reprise sans nouvel appel, si ses images et rôles correspondent encore au contexte. Une réponse illisible reste consultable et la demande peut être reprise.

## Sauvegardes

Le journal se trouve sous `<workspace>/qwen_edits`, avec un index explicite des projets. Les images utilisent le magasin de médias existant. Chaque rendu fige ses entrées ; les changements effectués pendant son exécution préparent le prochain essai.

Une copie est produite lors de la validation d’un résultat, dans **Qwen Projects**, à côté du dossier configuré pour **KREA2 Projects** (par défaut `D:\AI\PanelForge\Qwen Projects`). Elle contient la base, les étapes validées, les références, les conversations et les workflows. **Télécharger le projet** fournit aussi un ZIP portable avec les essais et leurs médias. Le chargement des projets se fait par la liste de l’atelier ; l’import d’un ZIP externe n’est pas ajouté.

## Vérification

Les tests ciblés sont écrits, mais ne sont pas exécutés par l’agent conformément aux instructions du projet. Aucun appel LLM, génération ou redémarrage de service n’a été lancé. Les contrôles effectués sont la syntaxe Python/JavaScript/JSON, les identifiants HTML, la cohérence statique du manifeste et le chargement des modules via `scripts/run_lab.py --help`.

À lancer par l’utilisateur, depuis PowerShell :

```powershell
Set-Location 'D:\Code\panelforge-krea2-flux'
$env:PYTHONPATH = 'D:\Code\panelforge-krea2-flux\src'
& 'D:\Code\panelforge\.venv\Scripts\python.exe' -m unittest discover -s tests -p 'test_qwen_edit*.py'
```

Les tests utilisent des faux serveurs LLM/ComfyUI et des fichiers temporaires. Le test d’interactions utilise Chromium local, s’il est installé, avec une API simulée ; il ne contacte pas l’application en cours.

Le rendu réel et la fidélité des compositions restent à qualifier avec les deux essais ci-dessus. L’assistant peut avoir une limite d’images propre à son serveur ; aucune pièce jointe n’est silencieusement retirée pour contourner cette limite.
