# Parcours d’images autonome — V1 et V2

L’onglet **Parcours d’images autonome** se trouve dans Image Lab, à côté de **Modifier avec Minimax**.
Il construit les états successifs d’un même décor : travaux, aménagement et décoration, à cadrage et point de vue fixes.

## Images en attente dans la frise

Dès qu’une étape est préparée, une vignette noire occupe son emplacement : étape automatique
ou ajout **+**, au milieu ou aux extrémités. Elle suit **Inverser l’ordre**. Elle indique la
préparation, puis **En file · n° N** lorsque le rendu possède un rang dans la file globale du
serveur (les tâches des autres ateliers comptent aussi), puis **Génération en cours**. Le rang
s’actualise avec le suivi existant du Lab, sans requête supplémentaire ni nouvelle génération.
Si le suivi ne fournit pas de rang, aucun numéro n’est inventé.

La vignette devient l’image dès que celle-ci est disponible ; un ajout abandonné disparaît.
Un clic sur un ajout en attente rouvre son dialogue avec ses références. Les emplacements
en attente ne sont ni sélectionnables pour Transitions, ni des références pour un nouveau **+**.
Pendant une correction, **2 essais** permet toujours de consulter le premier résultat.

Patch d’interface uniquement : **Ctrl+F5** suffit ; le backend, les critères de relecture
et le plafond d’une correction restent inchangés. Scénario navigateur complété, à exécuter
par l’utilisateur.

## Une correction automatique en Aménagement réaliste

Les nouvelles étapes **Aménagement réaliste**, y compris les ajouts **+**, disposent de **deux essais
au total : le rendu initial et une seule correction automatique**. Aucun changement pour Miniature,
ni activation rétroactive sur une étape déjà enregistrée avant ce correctif.

Le prompt MiniMax décrit d’abord une image inoccupée dans l’univers fourni et l’état visible attendu,
sans récit de chantier actif. La relecture réaliste **1.3.0** distingue maintenant :

- **Progrès exploitable, complet ou partiel** : conserver les avancées visibles vers la destination,
  puis adapter la prochaine transformation au travail restant et au budget. Une demande incomplètement
  exécutée ou un jalon anticipé compatible ne suffit plus à déclencher une correction.
- **Absence de progrès** : un résultat pratiquement inchangé peut recevoir l’unique correction.
- **Défaut bloquant manifeste** : personnes interdites, point de vue nettement différent, disparition ou
  remplacement du lieu, recul important qui annule les travaux acquis, ou image illisible/inexploitable.
  Une légère variation de cadrage, de texture, de couleur, de lumière ou de thème ne suffit pas.
  Toute avancée identifiable vers la cible reste exploitable, même modeste ou partielle.

La relecture fournit des différences visibles localisées, le travail restant, les défauts bloquants et
l’atteinte réelle de la destination. Les booléens historiques de réalisation complète et de fidélité du
décor restent informatifs : `scene_preserved=false` seul ne bloque plus une avancée. L’ancienne valeur
`untargeted_damage` reste lisible dans les réponses historiques, sans être un motif de retry.
Des personnes seules avec un progrès utile, même partiel, sans autre interdit net conduisent au nettoyage
du résultat fautif (référence unique de rendu, masque désactivé). Sinon, la correction régénère depuis
la source initiale validée, avec le diagnostic. Elle ne consomme pas une nouvelle étape du parcours.

Lors de la relecture de la correction, le premier essai est fourni comme **INITIAL_ATTEMPT**, en plus
du résultat corrigé et des références habituelles. Le modèle réévalue les deux et choisit le meilleur
résultat exploitable, avec un motif visible dans l’aperçu. Le premier peut être retenu automatiquement :
ses pixels, prompt, masque éventuel et provenance deviennent ceux de l’étape active. La suite et
Transitions suivent cette image ; les deux essais et leurs diagnostics restent archivés.

Cette comparaison utilise la relecture existante, sans nouveau rôle ni appel de critique ajouté.
Une référence visuelle supplémentaire peut augmenter le coût en tokens de cette relecture.
Si aucun essai n’est exploitable après deux rendus, le parcours reste suspendu avec les choix manuels.
Une réponse structurée invalide suspend également sans déclencher un rendu supplémentaire.
Un résultat déjà utilisé par une image manuelle suivante n’est pas remplacé automatiquement.
À budget épuisé, une destination encore incomplète est signalée ; aucun rendu n’est ajouté pour finir.

Ce contrôle reste une appréciation visuelle du modèle, sans garantie de conservation exacte des pixels.
Les consignes et la génération Miniature ne changent pas.

Une seule vignette représente l’étape. **2 essais** ouvre l’aperçu avec **Initial / Correction**,
leurs images, prompts et diagnostics ; l’essai retenu est indiqué. L’image initiale reste consultable
pendant la correction. Les essais non retenus restent sauvegardés mais ne sont pas exportables vers
Transitions. La correction n’ajoute pas une étape au budget et ne modifie pas les voisins.

Après le second rejet, ouvrir **2 essais → Initial → Accepter cet essai et continuer** permet de
retenir le premier jet. Pour la dernière étape, le bouton propose **Accepter cet essai et terminer**.
Sur un ajout **+**, il propose **Accepter cet essai**. La vignette, l’image envoyée vers Transitions
et la source de la suite deviennent celles de l’essai choisi, sans le régénérer. Son prompt et son
diagnostic d’origine sont conservés, avec la mention **Acceptée manuellement**. L’aperçu reste dans
l’ordre **Initial / Correction** : l’essai choisi indique **Essai retenu**, l’autre reste consultable.

Ce choix s’applique à l’étape suspendue, une fois la correction terminée. Il n’est pas disponible
pendant un rendu ou si une image suivante déjà sauvegardée dépend de cette étape. Les parcours
bloqués existants qui ont conservé leurs deux essais bénéficient de ce choix sans migration.
Le choix manuel reste disponible en complément du choix automatique ; la limite d’une correction est conservée.

Le budget et les identités des requêtes persistent après suspension ou redémarrage. **Reprendre**
après deux rejets peut relire l’image mais ne lance pas de troisième rendu automatique. **Régénérer**
reste une décision manuelle explicite : elle repart de la source initiale même après un nettoyage,
garde l’historique et ne réarme pas la correction automatique. Si une image manuelle existe déjà
après l’étape rejetée, celle-ci reste soumise à une décision manuelle pour préserver ses dépendances.

Tests préparés, à exécuter par l’utilisateur : `test_image_journey_retries.py`,
`test_image_journey_retain_attempt.py`, `test_image_journey_progress_review.py`, `test_image_journey_realistic.py`, `test_image_journeys_browser.py`. Aucun service n’est redémarré
par le patch ; charger le backend au prochain redémarrage habituel puis **Ctrl+F5**.

## Décider sur une image bloquée

Une image effectivement rejetée à la relecture propose deux actions compactes sous sa vignette et
dans son aperçu. Un résultat rejeté d’un ajout **+** propose les mêmes choix dans son dialogue.

- **Régénérer** écarte l’essai de la frise et refait la même transformation depuis sa source d’édition,
  avec le motif du rejet transmis au prompter et au masque éventuel. Nouvelle tentative de rendu,
  mêmes dimensions et même emplacement : elle ne consomme pas une étape automatique supplémentaire.
  Le journal et les fichiers de l’essai écarté restent conservés ; ses voisins ne sont pas régénérés.
- **Accepter et continuer** conserve les pixels malgré le diagnostic, rend l’image sélectionnable
  pour les transitions et prépare la suite depuis l’état réellement obtenu. Pour la dernière image,
  **Accepter et terminer** clôt le parcours sans appel supplémentaire. Le diagnostic du modèle reste
  enregistré ; l’interface indique **Acceptée manuellement**. Les consignes du preset restent actives
  pour les images suivantes. Sur un ajout manuel, **Accepter l’image** valide seulement cet ajout.

Ces actions concernent un rejet visuel valide. Une réponse LLM malformée, une erreur de fichier ou
un rendu encore en cours garde la reprise technique existante. **Reprendre** seul ne régénère pas
une image déjà produite. Les commandes vérifient la version, l’ID de l’étape et l’ID exact de l’image ;
un double clic ou une réponse réseau perdue ne doit pas créer un second remplacement. Terminer ou
abandonner un ajout en cours avant de décider sur une image automatique.

Le backend annonce `prepend_images` et `image_resolutions` dans `/spec`. Charger les changements
au prochain redémarrage habituel, après les générations en cours, puis **Ctrl+F5**. Aucun parcours
enregistré n’est modifié ou relancé automatiquement par l’installation de ce correctif.

## Identité du monde en Aménagement réaliste

La première analyse disponible décrit brièvement en anglais le monde de l’image fournie : matières,
rendu, échelle et éventuel mélange de matériaux. Cette description est sauvegardée séparément des
travaux et reste ancrée à la référence originale. Les nouvelles surfaces, états bruts et états usés
respectent aussi ce monde : laine, LEGO, papier, monde réaliste ou mélange déjà présent.
Les meubles peuvent être retirés sans traiter la matière constitutive du monde comme un revêtement
à enlever. Quelques coussins en laine ne transforment pas une pièce ordinaire en univers textile.

Cette mémoire accompagne la suite automatique, les ajouts **+** aux trois emplacements, les reprises
et les régénérations. MiniMax reçoit la description dans la demande puis dans le prompt compilé.
Le nettoyage d’ouvriers conserve le monde actuel du résultat et n’essaie pas de corriger son style.
Une demande explicite de changement d’univers prime pour l’édition concernée. Les écarts de thème
ne créent aucun nouveau rejet : la relecture conserve les progrès utiles et guide la suite.

Aucun appel LLM supplémentaire ni nouveau contrôle d’interface. Les anciens parcours sans mémoire
la renseignent lors d’une prochaine analyse habituelle depuis la référence originale. Une réponse
ancienne qui omet cette métadonnée reste exploitable ; les images et prompts déjà sauvegardés ne
sont pas réécrits. La reconnaissance du monde dépend du modèle, pas d’une segmentation automatique.

## Miniature ou Aménagement réaliste

Le sélecteur **Miniature / Aménagement réaliste** distingue les consignes du parcours. Miniature
conserve le comportement historique, notamment le choix V1/V2. Les anciens parcours sans champ
`journey_preset` restent sur ces politiques, sans migration. Le preset est fixé à la création.

**Aménagement réaliste** part de l’image du lieu terminé et utilise **À rebours**. Le champ
**État de départ souhaité** est facultatif et vide par défaut : par exemple « Grotte vide, humide
et austère » ou « Arbre intact, feuilles au sol ». Sans texte, Progression visuelle choisit un départ
plausible et avance automatiquement. Le lieu reste présent ; seules ses installations, couches,
surfaces ou ouvertures concernées sont ramenées à des états antérieurs. Aucun retour systématique
au terrain plat, ni étape dédiée aux fondations. Pas de personnages dans les images générées ; le
sélecteur Scène vivante est masqué et les politiques du preset priment sur cette ancienne version.

Le nombre demandé reste un budget de nouvelles images, en plus de l’original : grandes transformations
avec trois images, états plus détaillés lorsque cinq images ou davantage le permettent. Les couches
techniques sont plausibles et choisies pour le lieu, pas un relevé réel ni une recette obligatoire.
Le dernier rendu vise l’état initial retenu. Le contrôle existant peut terminer plus tôt si cet état
est réellement atteint, avec le nombre produit affiché et sans refaire une image sans changement.

Les consignes propres au preset couvrent planification, relecture, ajouts **+** et prompt MiniMax.
La référence terminée reste permanente, avec les rôles Picture 1 / Picture 2 ; conservation du lieu
et absence de personnages sont aussi ajoutées au prompt final. Cela ne garantit pas l’obéissance
du moteur : la qualité visuelle reste à qualifier sur des rendus. Réglages 3 MP / 18 passes,
deux rôles LLM et masque décoché par défaut conservés. Le diagnostic de qualité est inclus dans
la relecture existante ; une correction éventuelle ajoute son prompt, son rendu et sa relecture.

Les brouillons restent séparés pendant le changement de preset ; **Nouveau** revient aux défauts
Miniature / À rebours / trois images. Reprendre permet de modifier l’état de départ, pas le preset.
L’ordre affiché et exporté reste état initial → aménagement terminé par défaut. Les origines des
images exportées portent le preset pour un futur traitement vidéo ; aucune politique de transitions
spécifique n’est introduite ici. Ne pas déduire que les anciens réglages vidéo Miniature sont adaptés.

Le serveur annonce `journey_presets` dans `/spec`. Si l’ancien backend tourne encore, le nouveau
choix est indisponible avec une indication de redémarrage. Charger le backend au prochain démarrage
habituel puis Ctrl+F5. Tests préparés, réservés à l’utilisateur : `test_image_journey_realistic.py`
et le scénario existant `test_image_journeys_browser.py` ; aucun appel réel requis par ces suites.

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
vignette ; le **+** opposé permet d’aller au-delà de l’image fournie, à droite. Les **+** intérieurs
insèrent entre les deux voisins visibles. Le dialogue suit leur ordre affiché.
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
Les sorties déjà rejetées (par exemple un bâtiment réapparu) restent exclues des transitions jusqu’à
une décision explicite : **Régénérer** pour les remplacer ou **Accepter** pour les conserver. Aucun
rendu ne se lance automatiquement lors du chargement du parcours.

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

Les petits **+** apparaissent entre chaque image et aux deux extrémités, même lorsque la grille
revient à la ligne. Ils gardent leurs ancrages lorsque l’affichage est inversé.
Le parcours doit être terminé ou suspendu, avec ses rendus en cours récupérés avant de modifier la
séquence. Un formulaire ouvert conserve la demande saisie pendant le rafraîchissement de l’atelier.

- **Entre deux images** : le dialogue montre les deux états et demande l’état intermédiaire voulu,
  par exemple « le deck seul avant la porte ». Progression visuelle observe les deux images ; MiniMax
  édite l’état suivant dans l’ordre de génération pour ajuster les travaux et préserver la forme du deck déjà obtenu.
  Une nouvelle image relue est insérée. Les images et étapes existantes ne sont pas régénérées.
- **À la fin** : le dialogue montre la dernière sortie réellement obtenue, même si l’ancienne relecture
  a échoué. La demande libre produit une nouvelle image à partir de cette sortie.
- **Au-delà de l’image fournie** : un dialogue avec un seul voisin et une demande libre permet
  d’ajouter un état de l’autre côté. L’original reste la référence permanente et garde ses pixels.
  On peut répéter cet ajout, puis insérer entre les nouveaux voisins comme ailleurs dans la frise.
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
  `sequence_order` accepte désormais `source` à une position explicite pour les ajouts avant
  l’original ; les anciens journaux sans cet ID gardent leur ordre historique, sans migration.
  L’ordre d’affichage et de transfert peut être inversé sans modifier ces données.
- `image_operations` : journal d’ajouts, d’insertions et d’essais HQ. Les HQ n’entrent pas dans cet ordre.
- `POST .../projects/{id}/image-operations` : version, commande idempotente, kind, after_frame_id,
  before_frame_id, intention ou prompt. Les bornes doivent toujours désigner deux images consécutives,
  ou la dernière pour un ajout. `kind=prepend` utilise `after_frame_id=null` et `before_frame_id`
  égal à la première image canonique. `source` désigne toujours l’image fournie.
- `POST .../image-operations/{operation_id}/resume|cancel` : reprise/abandon explicites.
- `application/image_journey_resolutions.py` : acceptation/régénération persistées ; les sorties
  écartées restent dans `abandoned_steps` ou l’ancien `image_operations` annulé.
- `POST .../projects/{id}/image-resolutions` : version, commande idempotente, `step_id`,
  `output_asset_id`, `action=accept|regenerate`. L’acceptation vise ces pixels uniquement.
  Les étapes acceptées gardent leur `review` et reçoivent `user_acceptance` ; les régénérations
  prennent de nouveaux IDs d’étape, de prompt et de rendu. Les frises déjà exportées sont inchangées.

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
`tests/test_image_journey_resolutions.py` ajoute 16 cas : décisions sur les pixels exacts, reprise
des anciens rejets, budget et voisins conservés, absence de double rendu, acceptation finale sans
appel LLM, exceptions techniques, ajout manuel rejeté, extrémité avant source, insertion voisine,
export inverse et contraintes du preset après acceptation. Le scénario navigateur couvre les deux
actions, le double clic, le dialogue manuel et le déplacement du nouveau + lors de l’inversion.
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
