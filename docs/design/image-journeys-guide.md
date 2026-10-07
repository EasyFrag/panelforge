# Parcours d’images autonome — V1 et V2

L’onglet **Parcours d’images autonome** se trouve dans Image Lab, à côté de **Modifier avec Minimax**.
Il construit les états successifs d’un même décor : travaux, aménagement et décoration, à cadrage et point de vue fixes.

## Construction ou À rebours

Le sélecteur **Construction / À rebours** en haut est indépendant de V1/V2 et conservé après création.
**À rebours** est sélectionné par défaut dans l’interface, avec **3 nouvelles images**.
Ce mode prend une **Image finale fournie**, puis retire
progressivement finitions, façades et structure jusqu’au **terrain plat sans bâtiment**.
Aucune étape dédiée aux fondations, au terrassement, aux réseaux enterrés ou à la démolition.
Les consignes demandent un changement principal substantiel par image et, si le budget le permet,
un volume encore bien visible dans l’avant-dernière génération, juste avant le terrain plat.

La génération suit **bâtiment terminé → états antérieurs → terrain plat**. La frise affiche par défaut
l’ordre de construction : **terrain plat → états de construction → bâtiment terminé**.
Le bouton discret **Inverser l’ordre** inverse l’affichage et le prochain transfert vers Transitions.
Le choix est conservé pour ce parcours dans la session du navigateur, sans changer le calcul ni les images.
N nouvelles images visent N rendus en plus de l’image fournie ; avec une seule nouvelle image,
la demande va directement au terrain plat. Si le moteur atteint malgré tout le terrain vide plus tôt,
le parcours inverse se termine après sa relecture, avec le nombre réellement produit et un message
explicite. Il ne lance aucune image « sans changement » pour remplir le compteur. Une étape manquante
peut ensuite être demandée avec **+** entre deux états conservés. Les styles et matériaux viennent de l’image, miniature ou réaliste.
L’intention préremplie s’adapte au sens choisi ; changer de mode avant création conserve séparément
les deux brouillons, même vides. **Nouveau** rétablit les défauts. Un parcours chargé garde son intention.

MiniMax édite l’état précédent avec le bâtiment terminé comme référence permanente de géométrie
et de matières, sans restaurer les éléments déjà retirés. Au premier appel, l’état précédent étant
l’image terminée, elle n’est envoyée qu’une fois (Picture 1). Ensuite, Picture 1 désigne l’état
à éditer et Picture 2 l’image terminée. Les deux références gardent leurs pixels à environ 3 MP :
le workflow **1.3.0** contourne le redimensionnement de chaque référence occupée. Modèles, VAE,
18 passes et masque décoché par défaut restent conservés. Une référence guide le rendu ; elle ne
garantit pas une fidélité parfaite ni l’atteinte visuelle du terrain plat. La dernière image reste relue.

Les **+** gardent leurs bornes dans l’ordre de génération, indépendamment de l’affichage.
Quand la frise est inversée, l’ajout depuis la dernière sortie se trouve à gauche de la première
vignette ; les autres **+** insèrent entre les deux voisins visibles. Le dialogue suit leur ordre affiché.
Une insertion édite le voisin suivant dans l’ordre de génération ; à rebours, cela peut remettre
une partie de structure. L’analyse voit les voisins et la référence terminée.
Le transfert vers Transitions utilise les images cochées, exactement dans l’ordre affiché.

Le contrat accepte journey_direction = forward ou reverse. Un ancien journal sans champ reste
en construction, sans migration ni réécriture. La commande de création reste idempotente, y compris
avec un ancien client qui omet le sens lors d’une nouvelle tentative. Le sens, la version et la référence
sont enregistrés dans les étapes pour garder le même comportement après une suspension/reprise.

### Jalons, budget et arrivée anticipée

Les jalons sont conservés par l’application une fois le plan établi. Le modèle les reçoit comme
contexte, mais n’a plus à recopier leurs libellés ni la destination dans chaque réponse. Les éventuels
champs répétés par un ancien format de réponse ne remplacent pas le plan enregistré ; une vraie
modification de l’intention permet toujours un nouveau plan. Cette correction concerne le mode inverse.

Un même jalon peut couvrir plusieurs retraits substantiels. `through_milestone` désigne le nombre de
jalons entièrement atteints après l’édition : il peut rester égal au nombre déjà atteint, y compris zéro.
Tant qu’il reste plus d’une image, le dernier jalon ne peut pas être annoncé comme cible de l’édition ;
les consignes demandent explicitement de conserver une structure et d’échelonner les retraits.

Une relecture valide est conservée même si sa proposition suivante est invalide. L’image n’est pas
régénérée : une nouvelle décision prépare l’édition restante avec le motif du refus. Ce motif est tracé
dans l’analyse, séparément de la réponse brute. Les réponses malformées ou sans véritable constat visuel
restent refusées. Un verdict `unusable` suspend toujours le parcours.

Lorsque la relecture accepte le terrain vide et confirme tous les jalons, le parcours se termine sans
demande de rendu supplémentaire. La limite demandée reste enregistrée ; `generated` reste le nombre réel.
L’interface indique par exemple **2 nouvelles images sur 3 demandées · Terrain dégagé**. Une ancienne
replanification déjà sur un terrain accepté peut aussi terminer, uniquement si le plan, l’image courante
et sa relecture correspondent. Une image rejetée ou un ajout manuel différent n’est pas déclaré terminé.

### Reprise et références du parcours inverse

Un simple changement de fins de ligne Windows/navigateur dans l’intention ne relance plus la
planification et ne remplace plus une étape en attente. Une véritable modification de l’intention
continue de permettre un nouveau plan. Une préparation sans nouvelle image utilise un statut neutre ;
elle ne remplace jamais la relecture d’une image produite.

Pour les étapes inverses à deux références, l’application complète le prompt avec les rôles fixes
de l’image actuelle et du bâtiment terminé. L’oubli isolé du second label par le prompteur n’interrompt
plus l’étape. La réponse brute et le prompt réellement utilisé restent distincts dans le journal.
Les références inventées, l’absence de la source ou les formats invalides restent refusés.
Ce traitement est local et n’ajoute aucun appel LLM ou rendu.

Après mise à jour et redémarrage habituel, **Reprendre** relit l’image conservée d’un parcours bloqué
sur une reformulation de jalon ; aucune modification artificielle de l’intention n’est nécessaire.
Si un ajout manuel est suspendu, il faut le terminer ou l’abandonner dans son dialogue avant cette reprise.
Les anciennes sorties déjà rejetées (par exemple un bâtiment réapparu) restent archivées et exclues des
transitions : le correctif ne les remplace pas et ne lance pas automatiquement de nouveau rendu.

## Version du parcours

Le petit sélecteur en en-tête propose **V1 — Actuelle** et **V2 — Scène vivante**.
**V2** est présélectionnée pour un nouveau parcours. Le choix est conservé après création,
même pendant une suspension ; les parcours historiques restent en V1.

La V2 ajoute une vie secondaire visible mais discrète dans les mêmes images de travaux : personnes
ou véhicules qui changent de position, entrées et sorties cohérentes lorsque la scène s’y prête.
Les travaux restent centraux. Cadrage, point de vue, architecture, éléments fixes, travaux acquis,
textures, couleurs et lumière restent à préserver hors transformation explicitement demandée.
Il s’agit d’états fixes successifs, sans effet de flou de mouvement et sans image ni appel supplémentaire.

La planification décrit ces changements dans l’action transmise au prompter MiniMax et, s’il est activé,
au masque. La relecture distingue les déplacements voulus d’une dérive du décor ; les déplacements seuls
ne valident pas une étape de travaux. Les boutons **+** utilisent la version du parcours : une insertion
doit rester cohérente avec les deux images voisines, qui sont conservées.

Ces consignes guident les modèles ; leur rendu visuel reste à apprécier sur les prochains parcours.
Le réglage **3 MP / 18 passes**, le masque **décoché par défaut** et les modèles configurables restent identiques.

Le contrat de création accepte `journey_version: "1" | "2"` (V2 si omis pour une nouvelle commande).
La version du parcours est distincte du compteur de révision `version`. Les anciens journaux sans
ce champ sont lus en V1, sans migration ; leurs anciennes commandes restent rejouables.

## Utilisation

1. Choisir une image, adapter l’intention et le nombre de **nouvelles images** (5 par défaut, de 1 à 30).
   En mode Construction, les nouveaux parcours préremplissent l’intention avec le texte de monde miniature surréaliste : objets du quotidien,
   bâtiment achevé à la dernière image et population variée. Ce texte reste librement modifiable ou effaçable.
   **Nouveau** le rétablit ; ouvrir un parcours existant conserve son intention enregistrée, même vide.
2. Le volet replié **Modèles** sépare **Progression visuelle**, **Prompt MiniMax** et **Analyse du masque**.
   Les deux premiers gardent Gemma local par défaut ; le masque présélectionne Qwen local
   (`local::unsloth/Qwen3.8-27B-GGUF`) pour un nouveau parcours. Les rôles peuvent partager un modèle.
   Les modèles doivent accepter les images ; le catalogue ne certifie pas cette capacité. Un choix indisponible
   reste affiché et n’est jamais remplacé silencieusement.
3. **Créer la suite** lance le parcours côté serveur et replie le bandeau **Image de départ et réglages**.
   Le bandeau reste réouvrable ; son état ne change pas à chaque actualisation. Fermer l’onglet n’arrête pas la génération.
4. La destination tient en une phrase ; les grands jalons restent dans **Étapes prévues**, replié par défaut.
   La frise se remplit automatiquement. Une vignette ouvre l’image, l’action et sa relecture ; prompt et modèles
   sont accessibles dans le détail. Chaque image peut être téléchargée.
5. **Suspendre** laisse finir l’opération déjà engagée. Un rendu en cours est conservé, sans annulation implicite.
   Une fois suspendu, rouvrir le bandeau pour modifier l’intention ou les modèles puis **Reprendre**.
   Le bouton de reprise reste visible à côté de l’avancement même lorsque le bandeau est replié.
6. Cocher les images souhaitées puis **Préparer les transitions** pour transmettre la sélection à l’atelier H3. Les intentions vidéo y sont préparées
   et relues avant envoi à l’usine ; ce bouton ne lance aucun appel vidéo ou rendu.

5 nouvelles images donnent 6 images avec le départ et jusqu’à 5 transitions. **Nouveau** ouvre un autre formulaire ;
les parcours existants se retrouvent dans le sélecteur, avec leur avancement.

## Consultation des images

L’atelier utilise toute la largeur disponible. Les vignettes sont disposées dans une grille à colonnes
automatiques (environ 190 px minimum, images affichées sur 280 px de haut). Les étapes reviennent à la
ligne : aucun défilement horizontal n’est nécessaire pour voir la suite. Les proportions des images sont
conservées. Chaque vignette ouvre l’image agrandie, l’action et la relecture ; loupe, aperçu au survol ou
au focus clavier et téléchargement restent disponibles. L’interface s’adapte aussi aux petits écrans.

## Sélection pour les transitions

Une petite coche indépendante du zoom apparaît en haut à gauche de chaque vignette, y compris **Départ**.
Toutes les images disponibles sont cochées au départ. Décocher une image la conserve dans le parcours.
Les images en attente de relecture ou jugées inutilisables ne sont pas sélectionnables. Une sélection
explicite peut sauter ces images et utiliser les états relus suivants, y compris les insertions manuelles.

L’ordre de la frise prime sur l’ordre des clics : sélectionner **1, 3, 5** prépare **1 → 3**, puis **3 → 5**.
Le départ est facultatif ; le bouton exige au moins deux images et affiche le nombre retenu et les
transitions correspondantes. Les exclusions sont conservées par parcours dans la session du navigateur,
y compris lors du polling, d’une insertion, d’un changement de parcours et d’un rafraîchissement de page.
Une nouvelle image disponible est cochée par défaut.

Une sélection ou un ordre différent prépare une frise indépendante ; renvoyer les mêmes états
dans le même ordre rouvre la frise correspondante. Les frises existantes ne sont pas réécrites. Ce bouton ne lance pas de vidéo.
Le serveur vérifie les identifiants sélectionnés et leur disponibilité avant de créer une frise.

`POST /api/image-lab/journeys/projects/{id}/transitions` accepte `frame_ids` et `frame_order`.
Les IDs sont ceux des étapes (automatiques ou manuelles), pas ceux des assets ; au moins deux IDs
distincts et disponibles sont requis. `frame_order` vaut `generation` (défaut historique) ou
`reverse_generation`. Le serveur trie la sélection selon ce choix, indépendamment de l’ordre des clics.
L’interface fournit explicitement l’ordre affiché. Les anciens appels sans corps ou sans ordre gardent
leur comportement et leurs exports idempotents. Le projet public expose `transferable_frame_ids`.

## Réglage des nouveaux parcours : 3 MP et masque automatique

Les nouveaux parcours utilisent `fixed-3mp-v1` : environ 3 × 1024² pixels, dimensions arrondies
aux multiples de 32 et limitées à 4096 pixels par côté, **18 passes**, VAE **INT8 ConvRot** du
workflow MiniMax still conservé ; le lanceur utilise désormais 1.3.0 (références natives multiples). Le départ est préparé une seule fois en PNG/Lanczos.
Exemple : 1120 × 1984 devient 1344 × 2368. Toutes les sorties gardent ensuite ces dimensions.
`resolution=source`, `reference_mode=native` : aucun redimensionnement intermédiaire à 1 MP.
L’image importée avant préparation reste conservée dans `original_source_asset_id`.

**Masque automatique · préserver le décor** est décoché par défaut pour les nouveaux parcours. Ce réglage est enregistré à la
création, puis appliqué à chaque étape automatique et aux ajouts/insertions avec **+**. Il ne nécessite
ni dessin ni validation entre les images. Cocher cette option avant de créer un parcours pour l’activer.
Les parcours existants conservent leur choix enregistré.

Après chaque rendu, le rôle **Analyse du masque** reçoit la source exacte, le rendu brut et l’action
de l’étape. Un appel supplémentaire délimite automatiquement les modifications utiles par contours
normalisés, avec plusieurs zones et exclusions possibles. Les consignes couvrent les objets retirés,
leurs anciennes emprises, les ombres, les reflets et les raccords locaux ; elles excluent la dérive
globale de texture, couleur ou contraste non demandée. Ce n’est pas une différence de pixels.

Pillow transforme les contours en masque, ajoute une petite marge et un raccord doux, puis compose le
rendu avec la source. **Là où le masque vaut zéro, les pixels RGBA8 de la source sont recopiés exactement.**
Les dimensions doivent être identiques : aucune remise à l’échelle ni harmonisation globale pendant
la composition. La source est le dernier état protégé, donc les travaux précédents sont conservés.
Pour une insertion, c’est l’image suivante dans l’ordre de génération qui sert de source : l’insertion ajuste
l’avancement demandé (retrait en construction, ajout partiel possible à rebours) et laisse les deux
étapes voisines existantes intactes.

La relecture, la référence de l’étape suivante, le téléchargement principal et l’export des transitions
utilisent **le résultat recomposé**. Le rendu brut n’est pas publié comme nouvelle étape pendant le
calcul du masque. Dans le détail d’une image, ouvrir **Masque automatique** pour basculer entre
**Résultat protégé / Avant / Rendu brut / Masque**, y compris en taille réelle et au téléchargement.
Les journaux conservent les IDs de ces assets, les contours, le modèle et la version de la politique.
Le détail affiche le modèle réellement utilisé pour le masque. Le sélecteur est modifiable avant
création ou sur un parcours suspendu, puis enregistré par **Reprendre**. Il s’applique aux analyses
à venir ; les plans de masque déjà calculés et les images existantes restent conservés. Les ajouts
et insertions copient ce choix au lancement. Un ancien parcours sans `mask_model_id` continue
d’utiliser son modèle de progression jusqu’à sélection explicite. Les anciens appels API qui
omettent ce champ gardent ce comportement ; une reprise sans le champ conserve le choix enregistré.

La localisation est réalisée par le modèle visuel, sans modèle de segmentation supplémentaire installé.
Ce premier mécanisme ne garantit pas une segmentation au pixel près : un contour trop large peut laisser
de la dérive à l’intérieur, un contour trop serré peut couper un ajout. La qualité des contours et des
raccords reste à qualifier sur les vrais parcours. Un masque vide recopie la source et laisse la relecture
normale traiter une image similaire ; aucun garde-fou esthétique bloquant supplémentaire n’est ajouté.

En cas d’erreur technique du masque, **Reprendre** réutilise le rendu déjà obtenu. Un plan de masque
enregistré est réutilisé si seule la composition a été interrompue. Après redémarrage, aucune nouvelle
analyse ne part sans reprise explicite. Les profils et images des anciens parcours ne sont pas migrés ;
un nouveau parcours est nécessaire pour utiliser ces réglages. L’atelier MiniMax manuel garde ses défauts.

L’onglet temporaire **Test**, son API, son worker et ses workflows de diagnostic sont retirés.
Les fichiers de résultats et les journaux déjà présents dans le workspace sont conservés. Les anciennes
comparaisons intégrées au parcours restent compatibles sans interface de lancement, comme auparavant.

Charger le backend au prochain redémarrage normal du Lab, puis Ctrl+F5. Aucun rendu, appel LLM ou
redémarrage n’a été lancé pendant cette implémentation.

## Progression et limites

- Le LLM établit le cap et les grands jalons avant la première édition. Sans intention, il propose un chantier
  adapté au décor visible. Les travaux respectent leurs dépendances naturelles, même pour un décor imaginaire.
- Le chemin s’adapte aux résultats réels. L’analyse compare la source et le résultat ; l’image d’origine sert
  aussi d’ancre visuelle pour cette analyse dès la deuxième transformation. Le moteur MiniMax reçoit seulement
  l’état précédent comme référence de rendu ; si activé, le masque recopie ensuite les pixels hors modification. Une synthèse et les
  cinq dernières actions bornent le contexte.
- Chaque analyse de résultat propose aussi la transformation suivante. La dernière image reçoit une relecture
  dédiée. Un cap ou un jalon réécrit sans modification de l’intention est rejeté.
- Une image trop similaire est conservée : la prochaine transformation doit être plus visible. Aucun rejeu
  sémantique automatique en V1. Cette possibilité est conservée comme évolution future.
- Un résultat inexploitable suspend le parcours et reste visible. Reprendre relit ce même résultat selon
  l’intention éventuellement corrigée ; aucune image supplémentaire n’est produite tant que le blocage demeure.
- Une erreur technique suspend l’opération concernée. Une reprise explicite peut relancer un appel ou rendu
  ayant échoué. Les résultats réussis et les commandes déjà enregistrées sont réutilisés.
- Après un redémarrage, le parcours attend une reprise explicite. Le suivi MiniMax peut terminer un rendu déjà
  en file et le parcours le récupère sans en soumettre un second. Une confirmation d’envoi ComfyUI perdue conserve
  la limite du service MiniMax : vérifier sa file avant de reprendre lorsqu’un message le demande.
- Le nombre d’images est une limite ferme. Si certains jalons restent inachevés à la dernière relecture, le
  parcours le signale et n’ajoute pas d’images automatiquement. Aucun changement de point de vue, autre preset,
  branche de parcours ou geste d’ouvrier n’est ajouté à cette V1.

## Découpage

- `domain/image_journeys.py` : configuration, états, validation des décisions et contrat de séquence v1.
- `application/image_journeys.py` : journal, boucle serveur, pause/reprise, récupération, remise des états relus.
- `application/image_journey_prompting.py` : consignes V1 conservées, `image.journey.progression@1.1.0`.
- `application/image_journey_policies.py` : routage selon la version enregistrée du parcours ou de l’opération.
- `application/image_journey_v2_prompting.py` : progression, planification et relecture manuelles V2 (`@2.0.0`), demande au prompter adaptée.
- `application/image_journey_trials.py` : compatibilité et récupération des anciens essais, sans UX de lancement.
- `application/image_journey_protection.py` : localisation durable et composition avant relecture.
- `application/image_journey_mask_prompting.py` : politique `image.journey.mask@1.0.0`, rôle Analyse du masque.
- `domain/image_journey_masks.py`, `infrastructure/image_journey_masks.py` : contours bornés et composition locale.
- `application/image_journey_rendering.py` : petit adaptateur au prompter MiniMax existant et à sa file GPU.
- `infrastructure/storage/image_journeys.py` : fichiers atomiques sous `workspace/image_journeys`, index explicite.
- `features/lab/image_journeys_web.py`, `static/image-journeys.js`, `static/image-journeys.css` : API et atelier.

Les étapes MiniMax sont des projets enfants identifiés de façon déterministe, gérés par le parcours et masqués
de la liste des projets manuels. Ils réutilisent le workflow et la planification existants. Les assets sont
référencés par ID ; aucun ID de nœud ComfyUI n’est ajouté au code du parcours. Aucune dépendance ajoutée.

`GET /api/image-lab/journeys/projects/{id}/sequence` expose `schema_version`, `project_id`, `destination` et
`frames` ordonnés (`asset_id`, `label`, `origin`). Seul le préfixe relu et exploitable est transférable.
L’intégration transitions est facultative pour le service de parcours. Les frises créées sont des copies
indépendantes ; une nouvelle image ne modifie pas une frise déjà relue ou envoyée.

## Validation à effectuer par l’utilisateur

Les tests ci-dessous utilisent des fakes ; ils ne font pas d’appels LLM ni de rendus réels. Ils n’ont pas été
exécutés pendant l’implémentation, conformément à `AGENTS.md`.

```powershell
python -m unittest discover -s tests -p "test_image_journeys*.py"
python -m unittest discover -s tests -p "test_image_journey_comparisons.py"
python -m unittest discover -s tests -p "test_image_journey_trials.py"
python -m unittest discover -s tests -p "test_minimax*.py"
python -m unittest discover -s tests -p "test_navigation_and_resource_preview_browser.py"
python -m unittest discover -s tests -p "test_lab_web.py"
```

Le scénario navigateur nécessite Chromium local ; sinon il est ignoré. La qualification avec les modèles et
MiniMax réels reste à faire par l’utilisateur. Charger le backend au prochain redémarrage normal choisi par
l’utilisateur puis actualiser la page. Aucun service n’a été redémarré par cette implémentation.

## Ajout et insertion

Les petits **+** apparaissent après chaque image, même lorsque la grille revient à la ligne.
Le parcours doit être terminé ou suspendu, avec ses rendus en cours récupérés avant de modifier la
séquence. Un formulaire ouvert conserve la demande saisie pendant le rafraîchissement de l’atelier.

- **Entre deux images** : le dialogue montre les deux états et demande l’état intermédiaire voulu,
  par exemple « le deck seul avant la porte ». Progression visuelle observe les deux images ; MiniMax
  édite l’état suivant dans l’ordre de génération pour ajuster les travaux et préserver la forme du deck déjà obtenu.
  Une nouvelle image relue est insérée. Les images et étapes existantes ne sont pas régénérées.
- **À la fin** : le dialogue montre la dernière sortie réellement obtenue, même si l’ancienne relecture
  a échoué. La demande libre produit une nouvelle image à partir de cette sortie.
- Le modèle de progression et le prompter MiniMax restent ceux du parcours. Les étapes manuelles
  utilisent son profil de rendu (3 MP / 18 passes pour les nouveaux parcours). Elles sont comptées séparément du
  nombre initial d’images automatiques ; ajouter une étape ne reprend pas toute la génération.
- Chaque opération est persistée avant les appels et avant sa mise en file. Après erreur/redémarrage,
  **Reprendre** réutilise les prompts et sorties réussis ; **Abandonner** clôt une opération suspendue
  sans changer la séquence. Un rendu déjà soumis doit d’abord être récupéré. Une relecture techniquement
  interrompue reprend sur son image, sans la régénérer. Un résultat trop similaire reste conservé.

Les boutons **HQ ×2** sont retirés de la frise. Aucun nouvel essai HQ ne peut être lancé par
l’interface du parcours. Les anciens résultats et journaux restent conservés ; une opération ancienne
encore en cours reste consultable et peut être reprise ou abandonnée depuis son suivi.

Le blocage « prochaine transformation manquante » est corrigé pour une relecture qui retourne `null`
avant épuisement du budget : la relecture et la sortie sont enregistrées, puis une décision initiale
distincte demande la prochaine transformation. Son schéma exige une action. Le nombre demandé reste
un nombre d’images à produire ; on ne le transforme pas en maximum et on n’invente pas d’action locale.
Les anciennes erreurs enregistrées ne sont pas réécrites ; **Reprendre** applique la nouvelle logique.

### Contrats complémentaires

- `domain/image_journey_edits.py` : bornes explicites, validation d’une action et de sa relecture.
- `application/image_journey_edits.py` : opérations persistées avec phases et reprises indépendantes.
- `application/image_journey_edit_prompting.py` : prompts des rôles existants pour une demande ponctuelle.
- `manual_steps` et `sequence_order` : étapes et ordre canonique distincts de `steps` (budget automatique).
  L’ordre d’affichage et de transfert peut être inversé sans modifier ces données.
- `image_operations` : journal d’ajouts, d’insertions et d’essais HQ. Les HQ n’entrent pas dans cet ordre.
- `POST .../projects/{id}/image-operations` : version, commande idempotente, kind, after_frame_id,
  before_frame_id, intention ou prompt. Les bornes doivent toujours désigner deux images consécutives,
  ou la dernière pour un ajout. `source` désigne l’image de départ.
- `POST .../image-operations/{operation_id}/resume|cancel` : reprise/abandon explicites.

La remise des états relus reprend l’ordre actualisé. Les frises déjà préparées restent des versions
antérieures, sans réécriture. Un changement d’ordre prépare aussi une frise distincte.

### Vérifications à exécuter par l’utilisateur

Depuis la racine du code actif, avec son environnement Python :

```powershell
python -m unittest discover -s tests -p "test_image_journey*.py"
python -m unittest discover -s tests -p "test_minimax*.py"
```

Les nouveaux cas utilisent uniquement des doubles : insertion sans régénération, source réelle après
relecture échouée, ajout après ajout, ordre exporté, HQ natif à dimensions doublées sans LLM, commandes
idempotentes, conflit de version/bornes, reprise après redémarrage, accusé de file perdu, relecture
échouée, décision prématurément vide et validation HTTP. Le scénario navigateur couvre les dialogues
d’ajout/insertion, la saisie conservée au polling, les coches et leur persistance, le transfert sélectif,
le retrait des boutons HQ, le zoom et la grille sans défilement horizontal.
`tests/test_image_journey_selection.py` couvre les exclusions, l’ordre avec insertions, les images
indisponibles, les IDs et ordres invalides, les exports idempotents dans chaque sens et la compatibilité
des anciens appels. Le scénario navigateur couvre aussi l’ordre construction par défaut à rebours,
son inversion, sa persistance, le transfert sélectif dans chaque sens et les bornes des **+**.
`tests/test_image_journey_endpoint.py` couvre le plan immuable et sa reprise, les jalons partiels,
les propositions prématurées, les relectures conservées, l’arrêt anticipé sans appel superflu, la reprise
des anciens points de planification, les sorties rejetées, le budget normal et l’export dans l’ordre choisi.
Ces tests sont préparés mais ne sont pas exécutés par l’agent, conformément à AGENTS.md.

### Régressions V1/V2 (préparées, non exécutées)

`tests/test_image_journey_versions.py` ajoute dix cas sur les passerelles factices : défaut V2, choix V1,
version invalide, anciens journaux et rejeu des commandes, budget inchangé, prompt et masque informés
des déplacements, export sélectif, reprise et verrouillage API, insertion entre deux images et reprise
de relecture d’un ajout. Le scénario navigateur vérifie le sélecteur, le retour au défaut V2 et les anciens parcours.

### Régressions spécifiques au masque (préparées, non exécutées)

`tests/test_image_journey_masks.py` couvre la copie exacte hors masque, les exclusions et zones disjointes,
les raccords doux, le masque vide, les coordonnées invalides, le refus d’une composition avec changement
de dimensions, la chaîne protégée et son export, la pause, la reprise sans nouveau rendu, la reprise
après composition interrompue et les ajouts/insertions sans réécriture des images existantes.
La commande `python -m unittest discover -s tests -p "test_image_journey*.py"` inclut ces cas.
