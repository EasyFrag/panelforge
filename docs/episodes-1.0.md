# Fabrication d’épisode · 1.1

Depuis Histoires, développer un scénario puis **Valider et préparer la
fabrication**. Cette action ne lance aucun modèle : elle conserve une copie du
scénario avec des identifiants de fiches et de scènes. Valider deux fois le même
scénario retrouve la même fabrication. Une autre version crée une fabrication
distincte ; l’ancienne reste accessible dans le sélecteur.

## Références

Choisir un personnage ou un décor dans la liste. La description est préremplie
depuis le scénario. **Style et réglages communs à l’épisode** contient maintenant :

- Les **presets de style KREA2 Assisted**, repris depuis le catalogue existant.
  Choisir puis **Appliquer le preset** conserve une copie de son exemple visuel,
  de son prompt d’inspiration et de sa version. Son checkpoint et ses LoRA sont
  appliqués aux réglages communs ; le format, la seed et le sampling restent
  indépendants. Une nouvelle version du preset n’est reprise que via Appliquer.
- Une **direction visuelle textuelle**, une image importée facultative, ou
  **Utiliser l’image retenue de cette fiche**. Remplacer/retirer l’image passe en
  style personnalisé, sans effacer le checkpoint ni les LoRA déjà choisis.
- Le **checkpoint commun**, avec le sélecteur partagé recherche/favoris/fiche
  d’informations, jusqu’à dix LoRA avec forces et ordre, et le preset de rendu.

L’image est transmise comme guidage au LLM KREA2 à chaque préparation, dans le
même appel que la description. Les consignes limitent l’inspiration à la
stylisation, palette, matières et lumière ; identité/tenue/décor viennent de la
fiche. Ce n’est pas un conditionnement d’image supplémentaire du workflow de
rendu. Le prompt d’exemple du preset peut être un extrait pour respecter la
limite de message Assisted ; le preset complet reste conservé et les échanges
permettent de voir exactement l’extrait et l’image transmis.

Les nouvelles fiches héritent du checkpoint, des LoRA et du sampling communs.
**Personnaliser cette fiche** permet de les changer uniquement pour elle ;
**Revenir aux réglages communs** réactive l’héritage. Le format, les mégapixels
et la seed restent propres à chaque fiche. Les fiches v1 qui avaient des
réglages explicites les conservent comme personnalisations.

Le **preset de rendu** reste distinct du preset de style : Actuel 8+2 er_sde /
simple, Finition 4 steps 8+4 er_sde / simple, Moody Beta 8+4 euler_ancestral /
beta. Les anciens réglages personnalisés de sampling sont conservés.

- **Proposer / ajuster le prompt** utilise KREA2 Assisted 3.0.0, avec le modèle
  de la fiche et un retour facultatif. Le prompt reste éditable.
- **Générer l’image** soumet le prompt à la file KREA2 Assisted existante.
  Checkpoint, format, mégapixels, seed et les trois presets de sampling sont
  disponibles dans les réglages repliés.
- **Utiliser cette image** sélectionne un essai pour les scènes. Une image
  importée devient directement la référence retenue. Les propositions précédentes
  restent disponibles.
- Le projet KREA2 complet peut être ouvert pour ses outils supplémentaires ; ses
  rendus reviennent dans la liste de propositions de la fiche après actualisation.
  Le champ de prompt de la fiche garde son propre brouillon enregistré.

Enregistrer les réglages communs les conserve pour la suite ; ils sont aussi
enregistrés avant les actions et changements de fiche. Un changement de style
signale les prompts à vérifier et les images issues d’une ancienne direction,
sans modifier les images retenues. Pour un import ou un ancien essai sans
provenance, l’interface indique que le style n’est pas documenté. Sous chaque
nouvel essai lancé dans Fabrication, **Style et réglages utilisés** montre le
style de rédaction, les paramètres réellement soumis, la seed et le prompt.
Les modifications manuelles du prompt sont distinguées de sa rédaction LLM.

Les fiches sont partagées dans cette fabrication. Choisir une autre image signale
les préparations concernées comme anciennes ; leurs images et prompts historiques
ne sont pas remplacés. Enregistrer la fiche conserve description, modèle LLM,
prompt et réglages ; les actions de génération et changements de fiche enregistrent
aussi les modifications avant de continuer.

## Scènes

Un menu présente chaque micro-scène, sa durée et son état. Les personnages de
la scène sont affectés à **Sujet / identité**, le lieu à **Décor**. On peut
retirer/ajouter des fiches de la fabrication, modifier leurs rôles et les réordonner.
Les numéros Picture et les liens transmis au modèle suivent cet ordre.

Le maximum est **neuf images au total par rendu**. Une scène issue d’un scénario
avec davantage de références les affiche toutes : l’utilisateur doit en choisir
au plus neuf avant de préparer le prompt. Aucune troncature silencieuse. Un
personnage ou lieu volontairement sans référence est décrit dans l’intention.

Le texte éditable porte les actions, l’état initial et l’état final. Les dialogues
du scénario validé sont affichés séparément et ajoutés automatiquement, avec leurs
locuteurs et dans leur ordre. Pour changer les dialogues, revenir à l’histoire et
valider sa nouvelle version. L’intention complète peut être consultée.

Valeurs initiales, modifiables par scène :

- Classique expérimental `minimax.h3.ref2v.classic.cinematic.planned@1.0.0` ;
- Plan : `local::unsloth/Qwen3.8-27B-GGUF` ;
- Rédaction : `local::unsloth/gemma-4-31B-it-qat-GGUF` ;
- plans Auto, audace 2, aucun dialogue inventé ;
- BUNNY `0.1.3`, 9 / 4 / 5 steps, 0,9 MP initial et final, Turbo/preview actifs ;
- Motion Repair seul actif, forces 0,60 / 0,20 ;
- durée de la scène et musique désactivée.

Un modèle indisponible reste identifiable ; aucun remplacement silencieux. Les
variantes Hauhau peuvent être sélectionnées dans les modèles locaux existants.

La préparation propose les **cinq curseurs indépendants 0–3 de H3/REF2V** :
audace, vie de la scène, caméra, mouvements additionnels, dialogues et réactions.
Ils sont persistés et transmis à la préparation REF2V par scène. Les valeurs
initiales de Fabrication sont conservées et rendues visibles : audace 2, vie 1,
caméra 2, mouvements 1, dialogues 0. À 0, seules les répliques du scénario sont
demandées ; les niveaux vocaux supérieurs gardent la politique des recettes
existantes. Les répliques validées conservent leur texte et leurs locuteurs.
Changer un axe rend l’ancienne préparation à actualiser sans en écraser les
paramètres ; les préparations v1 restent relisibles et reprenables à entrées égales.

**Préparer le prompt** effectue le Plan puis la Rédaction avec les services REF2V
actuels. Ces deux documents sont validés par leurs validateurs existants. Une
erreur reste visible et les échanges sont consultables. **Reprendre l’étape
échouée** réutilise le Plan accepté si les entrées n’ont pas changé. Une nouvelle
préparation conserve les précédentes et crée une nouvelle session de prompting.

Le panneau vidéo est une instance isolée du composant REF2V existant : recettes,
checkpoint, LoRA, réglages BUNNY, preview, essais, reprise, ajustement et DLSS. Les
réglages sont enregistrés par scène après modification et avant un lancement.
Les essais gardent leurs paramètres effectifs. Le rendu vidéo reste une action
explicite après la préparation du prompt.

## Stockage et vérification

`workspace/episodes/episode-….json` contient la copie du scénario, les fiches,
images retenues, configurations et liens de préparation/rendu. Les images, projets
KREA2, sessions REF2V, traces LLM et vidéos restent dans leurs stockages existants.
Écritures atomiques, contrôles de révision, déduplication des demandes de traitement
et détection d’une préparation interrompue après redémarrage.

Tests préparés pour l’utilisateur :

```powershell
python -m unittest tests.test_episodes tests.test_episodes_web tests.test_episodes_browser
```

Ils utilisent des services/API simulés ; aucun appel LLM ni rendu réel. Ils n’ont
pas été exécutés pendant l’implémentation, conformément à AGENTS.md. Contrôles
effectués : AST Python, compilation syntaxique JS, liaisons et unicité des IDs HTML,
vérification des imports et des contrats, `git diff --check`.

Pour charger cette version, redémarrer le Lab une fois les travaux en cours
terminés, puis recharger la page. Aucun service n’a été redémarré automatiquement.
L’import d’un scénario depuis Video Lab, le lancement de tout l’épisode en lot et
son assemblage restent hors de cette première version. P1 I2V et P2 analyse vidéo
adaptative conservent leur place au backlog.
