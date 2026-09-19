# Atelier KREA2 Edit et presets de Création assistée

Patch du 2026-09-05. Le code est implémenté ; les tests sont à lancer par
l’utilisateur. Aucun appel LLM, rendu ou redémarrage effectué pendant le patch.

## Modifier avec KREA2

### Ateliers récents — 8 septembre 2026

La colonne de gauche affiche les **trois ateliers les plus récemment modifiés**.
**Afficher les autres ateliers (N)** charge les anciens ateliers à la demande ;
**Afficher seulement les 3 récents** replie la liste sans changer l’atelier ouvert.
Sa frise complète, ses essais, sa conversation et ses brouillons restent disponibles,
y compris lorsqu’il ne fait plus partie des trois récents. Les versions d’une même
famille comptent comme un atelier ; le brouillon le plus récent garde la priorité.

Le chargement utilise `GET /api/image-lab/krea2-edit/sources?project_limit=3` :
la limite porte sur les ateliers, jamais sur leurs étapes. `project_id` conserve
en plus la chaîne complète actuellement ouverte, même historique. Le serveur
effectue une lecture globale pour sélectionner les familles et leurs versions,
puis sérialise seulement les projets retenus. Le stockage reste inchangé ; les
requêtes historiques sans `project_limit` gardent leur contrat. Cache Edit JS
`20260908.5`. Le catalogue des modèles au premier chargement reste indépendant
de cette optimisation ; le gain de durée n’a pas été mesuré en session réelle.

Tests préparés, **non exécutés**, à lancer par l’utilisateur :

```powershell
python -m unittest tests.test_krea2_edit_web tests.test_krea2_edit_versions tests.test_krea2_edit_versions_browser tests.test_krea2_edit_backlog_browser
```

### Conversation et édition

Le **Ref boost** accepte désormais **0 à 1000**, par pas de 0,1 dans l’interface.
Cette borne correspond au contrat annoncé par le nœud `Krea2EditModelPatch`
installé sur ComfyUI, vérifié en lecture seule le 8 septembre 2026. La valeur
choisie est conservée dans l’essai et transmise à la prochaine étape ; les
workflows 0.1.0 et 0.2.0 transmettent le même réglage.

Mise à jour du 8 septembre : [V3 à instructions ciblées et sélecteur V2/V3](krea2-edit-prompting.md). La description ci-dessous retrace le patch initial V2 ; le workflow de rendu reste inchangé.

- Conversation visible par étape : instruction utilisateur, réponse française,
  prompt complet repliable. Les six derniers échanges acceptés de cette étape
  accompagnent le prompt courant, sans recopier tous leurs anciens prompts.
- Le writer décrit un état visible et une modification localisée. Il doit
  préserver les caractéristiques non modifiées et expliquer une proposition,
  sans prétendre que le rendu est déjà corrigé.
- Source de l’étape et résultat sélectionné sont comparables en superposition.
  Déplacer le séparateur sur l’image ou avec le curseur (clavier/tactile aussi).
  Le suivi de souris au survol est facultatif. Les sélecteurs permettent de
  comparer deux essais ; le choix d’un essai à droite le sélectionne aussi en
  feedback. Les proportions restent intactes, sans recalage automatique.
- La frise affiche la base puis les résultats validés. Cliquer une miniature
  agrandit l’image ; le bouton à côté ouvre l’étape. Les étapes validées restent
  consultables et les essais de l’étape active restent regroupés en dessous.
- La comparaison et la conversation occupent un espace stable ; les paramètres
  avancés et les images séparées sont repliables. Les modifications non envoyées
  du formulaire sont conservées en mémoire de l’onglet pendant une navigation
  entre étapes (elles ne constituent pas une sauvegarde disque de brouillon).
- Chaque essai repart de la source fixe. `Valider et continuer` adopte le PNG
  sélectionné, son prompt et ses réglages, notamment `Ref boost` et steps.
  Pour les anciennes étapes sans ces métadonnées, l’interface utilise les
  réglages de l’essai parent s’il est disponible dans le projet chargé.

Le frontend demande explicitement l’assistance conversationnelle `2.0.0`,
opération `krea2.edit.conversation@2.0.0`. Le contrat API historique sans version
continue de produire du texte seul. Les révisions enregistrent leur version et
leur réponse ; les anciens échanges sont affichés sans inventer une réponse.
Stockage Edit schéma 4, lecture 1/2/3 conservée. Le workflow image demeure
`krea2.identity_edit@0.1.0`. La source réelle est jointe à chaque échange Edit ;
la politique d’envoi unique de la référence initiale concerne Création assistée.

## Presets de Création assistée

### Bibliothèque classée et prompts bilingues — 19 septembre 2026

Les presets sont classés dans quatre catégories logiques, affichées dans cet
ordre : **Work**, **Fun**, **NSFW**, puis **Archive**. Le gestionnaire compact de
Création assistée permet de changer une catégorie ou de retirer un preset du
catalogue. Ces opérations créent une nouvelle révision ou un marqueur de
suppression ; elles ne modifient jamais la copie immuable déjà intégrée à un
projet ou à un épisode.

Chaque preset conserve aussi sa langue de prompt, English ou 中文. Le choisir
présélectionne cette langue pour un nouveau projet, mais le sélecteur reste
modifiable. Pendant la conversation, le changement s'applique au prochain
échange et au prochain rendu. Une conversion du prompt courant reste une action
LLM explicite, proposée seulement quand la langue sélectionnée diffère de la
langue persistée ; aucune traduction cachée n'est ajoutée aux échanges normaux.

Le catalogue LoRA ajoute parallèlement la catégorie logique
**NSFW - Persona** pour les fichiers du sous-dossier `people`. Aucun fichier
n'est déplacé. `pussy_helper_v01alpha.safetensors` reste classé dans les détails
NSFW et `lenovo_krea2.safetensors` reste volontairement non classé.

Sur un essai réussi, **Créer un preset** ouvre la sauvegarde : nouveau nom ou
mise à jour d’un preset existant. Le snapshot contient le prompt et les réglages
enregistrés sur cet essai, son image et sa provenance. Les paramètres actuellement
édités pour le prochain rendu ne servent pas à cette sauvegarde.

Au démarrage d’un projet, choisir un preset présélectionne modèle image et LoRA.
Le premier échange reçoit le prompt et l’image d’exemple pour adapter leur style
au nouveau sujet. Ratio, résolution et seed d’origine sont conservés comme
provenance, mais ne sont pas imposés à la nouvelle création.

En cours d’atelier, choisir B remplace modèle et LoRA immédiatement ; prompt,
ratio, résolution, seed et historique restent ceux de l’atelier. Le prochain
échange reçoit l’exemple B. La sélection ne lance ni conversation ni rendu.
Si A puis B sont sélectionnés sans échange entre les deux, seul B est en attente.
Un rendu avant l’échange utilise donc l’ancien prompt avec les nouveaux réglages.

L’exemple reste en attente après un échec LLM, puis cesse d’être joint après
une réponse acceptée. Son nom apparaît sur l’échange concerné. Le contexte
textuel peut conserver son influence ensuite, conformément au choix utilisateur.
**Retirer** supprime la sélection et l’exemple en attente mais garde le prompt
et les réglages courants. **Réappliquer** recharge le preset et prépare à nouveau
son exemple ; cette action permet aussi de charger une mise à jour disponible.

Le catalogue `workspace/krea2_style_presets.json` conserve les révisions en
interne, avec un seul preset courant par nom dans le sélecteur. Les projets,
branches et nouveaux essais gardent leur snapshot exact. Mettre à jour un
preset ne modifie pas les projets existants ; une mise à jour depuis une liste
périmée est refusée. Aucun branchement automatique n’est créé par une sélection.
Stockage Assisted schéma 5, lecture 1/2/3/4 conservée. Les recettes Batch restent
indépendantes de ces favoris rapides.

## Vérifications préparées

- `tests/test_krea2_style_presets.py` : provenance, révisions immuables, sélection
  A/B, premier échange, reprise après rejet, suppression et retour de branche.
- `tests/test_krea2_edit_workshop.py` : réponse française, contexte récent,
  refus JSON sans perdre le prompt, nouvelle étape et transmission des réglages.
- Parcours HTTP ajoutés aux tests Web Assisted/Edit ; contrats UI et versions
  de cache actualisés. Tous utilisent des fakes et des répertoires temporaires.

Ces tests n’ont pas été exécutés. Contrôles réalisés : AST Python, syntaxe
JavaScript sans invocation, structure HTML/IDs et contrôle du diff. Aucun rendu
visuel navigateur ni essai modèle n’a été effectué.

La vidéo reste hors périmètre. La dérive progressive vers un rendu cartoon
rapportée par l’utilisateur reste à auditer séparément : la conservation des
réglages supprime une variation involontaire, mais ne démontre pas une amélioration
de qualité ni ne garantit la conservation exacte des pixels lors d’éditions successives.
