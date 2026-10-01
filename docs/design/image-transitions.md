# Transitions d’images

L’onglet **Transitions**, à côté de l’usine, prépare les vidéos intermédiaires entre des images déjà disponibles. N images ordonnées donnent N−1 transitions. Sans référence supplémentaire : H3 first/last (FL2VA). Avec une image d’ouvrier : REF2VA, avec les rôles départ/arrivée, identité et échelle.

## Parcours

1. Créer une frise et lui donner un nom dans les réglages communs.
2. Ajouter des fichiers, ou ouvrir **Depuis un atelier** pour choisir des versions précises dans KREA, Qwen ou MiniMax. **Sélectionner la chaîne validée** coche le départ et les résultats acceptés ; les autres essais terminés restent sélectionnables.
3. Réordonner les vignettes par déplacement ou par les flèches. Le bouton de remplacement accepte un fichier ou une version d’atelier. Retirer une vignette ne supprime aucun asset ni projet source.
4. Sélectionner les transitions à préparer. Une action courte peut être saisie dans la liste ; le panneau de droite contient l’indication personnelle et les réglages particuliers.
5. Facultatif : ouvrir **Ouvriers et échelle**, choisir/importer un ouvrier, choisir l’organisation du chantier et régler son échelle depuis une paire.
6. Choisir **Slow** ou **Fast** dans le sélecteur **Rythme**, puis cliquer sur **Proposer les transitions**. Le LLM voit les deux images de chaque paire, l’ouvrier et le montage d’échelle s’ils sont renseignés, les réglages communs et les indications disponibles. Les propositions sont françaises et restent à relire.
7. Corriger si nécessaire, puis **Valider la sélection** ou **Valider cette transition**.
8. **Envoyer à l’usine** ajoute les versions relues à sa préparation. **Voir dans l’usine** ouvre les unités reçues ; leur lancement utilise le parcours habituel Plan → Prompt → Vidéo, avec DLSS facultatif.

Les champs non enregistrés sont signalés. **Enregistrer** les conserve ; les actions de préparation, validation, import, navigation entre paires et envoi enregistrent également les champs avant de poursuivre. Actualiser permet de recharger une modification venant d’une autre fenêtre, en demandant confirmation avant d’abandonner des champs non enregistrés.

## Miniatures et agrandissement

La frise affiche les images dans une zone de 360 × 252 px sur ordinateur, soit trois fois la taille initiale ; elle reste défilable horizontalement et s’adapte aux écrans étroits.

Le bouton **Masquer les images** replie la frise horizontale ; **Afficher les images** la rouvre. Ce choix reste mémorisé pendant la session, par frise. La barre d’actions reste visible au défilement, sous la navigation principale. Les images des paires passent de 34 × 38 à 86 × 110 px ; la comparaison à droite dispose d’une hauteur de 300 px et d’un panneau plus large.

Toutes les miniatures — frise, paires, comparaison à droite, ouvriers, montage et sélection depuis un atelier — proposent un aperçu flottant au survol ou au focus clavier. Il agrandit l’image visible ×3, dans la limite de l’écran, sans déformer son format. L’aperçu disparaît en quittant la miniature, au défilement ou avec Échap.

Chaque miniature dispose aussi d’un bouton loupe qui ouvre la vue agrandie. Dans la liste des paires, cette loupe ne change pas la transition sélectionnée ; le clic sur l’image ou sur la flèche conserve la navigation habituelle. L’agrandissement reste disponible pendant l’analyse.

Le front se recharge avec **Ctrl+F5**. Les nouvelles routes de sélection/placement nécessitent aussi le chargement du nouveau backend au prochain redémarrage habituel choisi par l’utilisateur.

## Réglages

Les réglages communs comprennent description de l’ouvrier, rythme, caméra, ambiance sonore, musique, conservation, durée, cadrage et DLSS. **DLSS dans l’usine** est coché par défaut pour les nouvelles frises et reste désactivable ; les frises existantes conservent leur choix enregistré. Le cadrage automatique choisit le format H3 supporté le plus proche de la première image.

Trois modèles sont paramétrables : propositions visuelles, plan H3 et prompt H3. Les identifiants locaux/serveur du catalogue existant sont conservés ; aucun remplacement silencieux d’un modèle absent. L’analyse des paires nécessite un modèle et un accès capables de lire les images. Les valeurs initiales reprennent les modèles de l’usine : Gemma Unsloth pour les propositions et le prompt, Qwen local pour le plan.

Chaque transition peut remplacer la durée, la caméra et le rythme communs. Un déplacement vers l’intérieur d’un arbre peut ainsi avoir un rythme différent des travaux accélérés. Les paramètres détaillés du rendu restent ajustables dans l’usine.

## Slow et Fast

Le sélecteur **Rythme** est visible près de **Proposer les transitions** :

- **Slow — accéléré modéré** : progression posée, gestes fluides et lisibles, quelques opérations essentielles et sons synchronisés. Ce nom désigne la version plus douce, pas du ralenti.
- **Fast — avance rapide** : toute la captation est fortement comprimée, avec gestes saccadés, sauts de pose et de position, instants sautés, bref flou des membres et des outils, étapes de travaux rapprochées et sons en rafales. Les mouvements déjà visibles dans le décor suivent la même accélération. L’entrée et la sortie sont expéditives, sans longue attente finale.
- **Personnalisé** : conserve le texte libre du rythme. Modifier la description du rythme sélectionne automatiquement ce mode.

Les nouvelles frises utilisent **Fast**. Les frises antérieures gardent leur texte et apparaissent en **Personnalisé**, sans modification de leurs validations ou des unités déjà envoyées. Pour comparer sur une frise existante : sélectionner Fast, proposer à nouveau, relire puis envoyer la nouvelle version. Une intention corrigée manuellement reste conservée ; accepter la nouvelle proposition avec le bouton prévu si elle convient.

Le preset remplit les consignes de proposition puis est repris explicitement, en tête de l’intention transmise à l’usine, pour les étapes Plan et Prompt H3. Fast y emploie notamment « aggressively fast-forwarded time-lapse » et « staccato, frame-jumping beats ». La durée choisie, la caméra et les deux références restent celles de la transition : les ellipses temporelles ne demandent ni montage ni assemblage magique. Le rythme spécifique d’une paire remplace intégralement le preset commun ; l’interface signale ces exceptions.

Choisir un preset ne lance aucun appel. Changer le rythme retire la validation des paires concernées, qui doivent être relues. Les vidéos et unités déjà reçues dans l’usine restent inchangées.

Exemple d’intention Fast rédigé pour illustrer le traitement, sans appel LLM :

> Toute la captation montre le chantier en avance rapide extrême : l’ouvrier change de pose par bonds, avec des instants sautés et un bref flou des bras et des outils. Après le départ vide, il apporte le bois en une rafale de déplacements, débite puis fixe les éléments au rythme d’impacts très rapprochés ; chaque série de gestes fait progresser visiblement la plateforme. Il ramasse les chutes et emporte ses outils dans les derniers instants. L’image finale retrouve exactement la plateforme terminée, sans ouvrier.

Le changement porte sur les consignes de génération ; son intensité réelle reste à qualifier sur une vidéo H3. Le backend sera chargé au prochain redémarrage habituel du Lab, puis **Ctrl+F5** chargera les assets `20260929.refs1`.

## Ouvriers, effectif et échelle visuelle

Dans **Ouvriers et échelle**, **Choisir un ouvrier** ouvre deux listes compactes : **Mes ouvriers** (images déjà utilisées, réutilisables entre frises) et **Images récentes des ateliers** (KREA, Qwen et MiniMax). **Importer** accepte PNG, JPEG ou WEBP. Il n’y a aucun atelier de génération de personnage supplémentaire.

L’organisation du chantier propose exactement :

- **Ouvrier solo** : une seule personne.
- **Petite équipe** : quelques ouvriers, avec des tâches complémentaires.
- **Petit chantier** : organisation coordonnée et engins légers selon les besoins.
- **Gros chantier industriel** : équipes, transport et levage mécanisés adaptés aux travaux.

Les trois derniers niveaux ne fixent pas un effectif numérique arbitraire : le LLM le propose selon l’action. L’image définit une identité pour le solo, un style et une tenue pour une équipe ; la consigne évite les clones mécaniques. Le niveau industriel ne change pas la taille des humains.

Après sélection, ouvrir une paire puis **Régler l’échelle** dans le panneau de droite. Le décor de départ est affiché ; déplacer le personnage au sol, régler sa hauteur avec le curseur ou la poignée, puis **Enregistrer l’échelle**. Les flèches du clavier déplacent le personnage ; Maj donne un déplacement plus grand. Position et hauteur sont normalisées par rapport à l’image, indépendamment de la taille de la fenêtre.

Le partage vise par défaut cette paire et les suivantes du même cadrage. Il s’arrête avant un déplacement caméra déjà identifié ou un autre groupe de placement explicitement défini. **Cette paire seulement** crée un réglage local. L’ajout d’une nouvelle image en fin de frise reprend le groupe précédent, sauf après un déplacement caméra. Un réordonnancement ne propage pas automatiquement une échelle aux nouvelles paires. Si une transition est ensuite reconnue comme un changement de caméra, les montages hérités au-delà de ce changement demandent un repositionnement. La détection exhaustive des cadrages n’est pas automatique : vérifier le décor et ajuster localement si nécessaire.

Le montage est un nouvel asset PNG calculé localement, sans appel de génération : les originaux A/B restent inchangés. L’image d’ouvrier est normalisée en RGBA, débarrassée de ses marges transparentes, avec un côté maximal de 2048 px. Préférer une image **en pied, sur fond transparent**. Un fond opaque reste visible dans le collage ; cette version ne fait pas de détourage automatique. Les consignes demandent d’ignorer le rectangle du collage, mais son impact visuel reste à qualifier.

## Transmission aux intentions et à H3

La proposition reçoit les références dans l’ordre stable :

1. Départ.
2. Arrivée.
3. Ouvrier : apparence et tenue.
4. Montage : taille et placement dans le décor, lorsqu’il est défini.

Le LLM doit lire l’échelle **avant** de choisir les moyens du chantier : outils, transport, levage et coopération. Des humains minuscules peuvent traiter des allumettes comme des poutres et les lever avec des grues à leur échelle, si la transformation le justifie. Une image d’ouvrier porte seule identité, apparence, corps et tenue ; le montage porte seul l’échelle et le placement. Ne redécrire aucun de ces attributs dans l’intention, le Plan ou le prompt, même lorsque la description serait correcte.

La description textuelle est disponible uniquement sans image d’ouvrier. Avec une référence, le champ est désactivé et vide à l’écran ; son ancien contenu reste conservé mais exclu des requêtes. Les anciennes intentions, titres automatiques, noms/historiques des images et mesures du placement ne sont pas envoyés à la nouvelle proposition. Aucun ratio ne remplace le montage visuel.

La présence d’un ouvrier bascule la nouvelle unité en **REF2VA** : références first_frame, last_frame, subject_reference, puis composition_reference si disponible. Le profil et le cookbook REF2V existants transmettent ces références au Plan et au Writer. A/B définissent les transformations ; le montage peut montrer un état de chantier antérieur et ne constitue pas une étape intermédiaire imposée.

Le contrat worker.visual-only@1 est transmis explicitement de la frise à l’usine et à la composition. L’en-tête distingue l’identité et l’échelle à partir des assets et des numéros Picture réellement liés. Le LLM doit conserver dans les actions « personnage de Picture 3, à l’échelle et au placement de Picture 4 » ; aucun ratio ni description physique ne sont ajoutés par le compilateur. La disparition d’un de ces liens bloque l’acceptation du Plan/Prompt de travaux. Les déplacements de caméra seuls ne doivent pas acquérir un personnage. En REF2VA, les états de départ/arrivée sont des références guidées par le prompt : ils ne bénéficient pas du même conditionnement de bornes que FL2VA. L’échelle réelle, les raccords et la fidélité aux états nécessitent donc une qualification sur des rendus.

**Retirer la référence** retire ses placements de la frise et retrouve FL2VA pour les prochaines unités. Les images et unités déjà envoyées restent conservées.

## Relecture et versions

- Depuis image.transitions.propose@3.1.0, l’action désigne la modification visible entre les deux images. Une construction partielle est décrite par ses pièces et sa géométrie, sans anticiper le monument ou l’objet complet. L’intention borne la progression à cet état, sans construction supplémentaire suivie d’une réduction ; cette règle vise l’assemblage, pas une démolition demandée ni un déplacement de caméra.
- Le proposeur ne reçoit plus les noms ou historiques de retouche des images, ni les anciens titres/intentions automatiques, avec ou sans référence d’ouvrier. Les images restent transmises à l’identique. La provenance reste disponible dans la frise. Les notes, actions corrigées et contraintes manuelles sont conservées ; avec image d’ouvrier, l’ancien texte d’intention reste exclu conformément au contrat visuel.
- Sans image d’ouvrier, sa description textuelle reste une consigne utilisateur transmise au Plan. Pour éviter qu’un nom de monument soit réintroduit par ce champ, préférer une description de l’échelle du chantier : « Des ouvriers réalistes et minuscules manipulent les allumettes comme des poutres, sur un chantier à leur échelle. » Les réglages enregistrés ne sont pas réécrits automatiquement.
- Depuis image.transitions.propose@3.0.1, l’intention proposée vise deux ou trois phrases (environ 40–70 mots, sans couper les consignes essentielles) : rythme annoncé une fois, gestes concrets et résultat. Les détails de réalisation restent au Plan/Writer ; les consignes Fast et les références visuelles sont conservées. Les intentions déjà enregistrées ne sont pas réécrites.
- Une proposition distingue observations, opération suggérée et incertitudes. Un outil inféré n’est pas présenté comme un fait visible.
- Une intention modifiée manuellement est conservée lors d’une nouvelle analyse. La nouvelle proposition apparaît séparément et ne la remplace qu’au clic explicite.
- Une réponse arrivée après modification des images ou consignes n’est pas appliquée.
- Remplacer une image retire la validation des transitions adjacentes ; si cette image sert aussi de décor à un montage partagé, ce montage doit être refait. Les intentions restent consultables.
- Réordonner conserve les transitions dont les deux voisins restent les mêmes, et crée celles nécessaires au nouvel ordre.
- La relecture est liée aux images, au texte, à l’effectif et aux références exactes envoyées. Changer l’ouvrier ou l’échelle impose une nouvelle relecture. Un montage lié à un ancien ouvrier/décor bloque la proposition et la validation jusqu’à correction ou retrait.
- L’envoi répété de la même version retrouve l’unité existante. Les entrées exactes sont enregistrées avant réception par l’usine pour permettre une reprise après interruption.
- Modifier la frise ne modifie jamais une unité déjà envoyée. Une nouvelle version relue crée une nouvelle unité ; les anciennes restent accessibles.
- L’ordre de la frise détermine celui des nouvelles unités lors de l’envoi. La priorité des unités déjà présentes reste gérée dans l’usine.
- Le retour depuis une ancienne unité signale une frise modifiée ou une transition retirée.

## Exécution et stockage

Projets : `workspace/image_transitions/index.json` et `workspace/image_transitions/transitions-<id>.json`. La sauvegarde est atomique et utilise des révisions explicites. Les références pointent vers des assets précis, avec leur origine dans l’atelier. workers.json conserve les 100 derniers ouvriers choisis/importés, sans scan de répertoires d’assets. Le projet conserve worker_reference, des scale_setups immuables et les scale_setup_id attribués aux transitions.

Les propositions passent par le gateway LLM partagé, son journal et sa coordination des machines. Un lot est traité paire par paire, avec deux à quatre images réduites pour l’analyse et un contexte textuel commun. Fermer l’onglet n’annule pas la tâche côté serveur. Après redémarrage, une analyse interrompue est signalée ; elle n’est pas rejouée implicitement.

L’onglet conserve les liens et les états légers des unités de l’usine. Il ne duplique pas le moteur H3, ses workflows ni les opérations Plan/Prompt. La référence d’ouvrier exprime une continuité souhaitée ; la qualité des raccords et des actions demande une qualification visuelle.

La création autonome de nouvelles images reste dans son atelier distinct, documenté dans docs/design/image-journeys-guide.md ; ce patch ne la modifie pas.

## Vérifications et mise en service

Préparés : tests de domaine/service, sources et HTTP dans `tests/test_image_transitions.py`, et un scénario navigateur avec API simulée dans `tests/test_image_transitions_browser.py`. Ils couvrent les références exactes, la relecture, la conservation des corrections, les réponses obsolètes, l’envoi dédupliqué et sa reprise après interruption. Le patch Slow/Fast ajoute huit cas sur la propagation des presets, leur validation HTTP, les versions envoyées, les exceptions par paire et la compatibilité des anciennes frises ; le scénario navigateur prépare aussi la sélection et l’enregistrement du rythme avant proposition.

**Tests non exécutés**, conformément aux consignes du projet. Aucun appel LLM, rendu ni redémarrage de service effectué pour cette évolution.

Pour lancer les tests ciblés depuis le checkout actif, avec `src` dans `PYTHONPATH` :

```powershell
$env:PYTHONPATH = 'D:\Code\panelforge-krea2-flux\src'
& 'D:\Code\panelforge\.venv\Scripts\python.exe' -m unittest discover -s tests -p 'test_image_transitions*.py'
```

Le nouveau backend sera chargé au prochain démarrage habituel du Lab ; actualiser ensuite la page. La validation visuelle se fait alors sur une courte frise, en relisant les intentions avant le lancement dans l’usine.

Sauvegardes et diagnostic isolé du patch : `D:/Code/panelforge/.agent/diagnostics/image-transitions-20260928/`.

Diagnostic du patch Slow/Fast : `D:/Code/panelforge/.agent/diagnostics/transition-pace-presets-20260929/`. Contrôles statiques de cette évolution : six fichiers Python parsés/compilés, trois sources JavaScript compilées sans invocation, 88 règles CSS parsées, 1 955 IDs HTML uniques et 38 références présentes. Tests et scénario non exécutés.

Patch échelle de l’ouvrier : contrat de proposition `image.transitions.propose@1.2.0`, descriptions de schéma Plan/Writer renforcées et transmises aussi aux phases de longueur fixée. Compilateur de prompt inchangé. Cinq fichiers Python parsés/compilés et HTML contrôlé, sans exécution fonctionnelle. Une régression de compilation ajoutée et les cas existants de transmission/schéma complétés, à lancer par l’utilisateur dans `test_image_transitions.py` et `test_classic_cinematic.py`. Sauvegardes et reçu : `D:/Code/panelforge/.agent/diagnostics/transition-worker-scale-20260929/`. Au prochain redémarrage habituel du backend, actualiser la page avec Ctrl+F5.


Patch références visuelles du 29 septembre : contrat image.transitions.propose@2.0.0, 14 nouveaux cas de régression dans tests/test_image_transitions_references.py et scénario navigateur complété pour choix du personnage, effectif, placement partagé, loupes et repli conservé. Tests préparés, non exécutés. Contrôles statiques : 13 fichiers Python compilés, 4 sources JavaScript compilées sans invocation, 122 règles CSS parsées, IDs HTML uniques et 68 sélecteurs résolus. Aucune nouvelle dépendance.

Assets front : 20260929.refs1. Sauvegardes, diff et reçu : D:/Code/panelforge/.agent/diagnostics/transition-visual-references-20260929/. Après le prochain redémarrage habituel du backend choisi par l’utilisateur, faire Ctrl+F5. Choisir un ouvrier en pied, régler une échelle volontairement petite, proposer une paire puis relire les outils/effectifs avant l’envoi à l’usine. Vérifier ensuite que les 3–4 images et leurs rôles sont présents ; lancer une vidéo seulement lorsque souhaité pour qualifier le résultat.


## Correctif du 29 septembre — identité et échelle exclusivement visuelles

Proposition image.transitions.propose@3.0.0. Les intentions précédentes au contrat visuel sont conservées et signalées, mais leur revalidation/envoi est bloqué jusqu’à une nouvelle proposition appliquée ou une réécriture manuelle avec les liens Picture. Une correction manuelle existante reste affichée : la nouvelle proposition apparaît à côté, à appliquer explicitement. Les unités déjà envoyées ne sont pas réécrites.

Les schémas Plan/Writer n’exigent plus de description physique ni de ratio pour ces préparations. Le repli sans image d’ouvrier et les autres recettes gardent leurs contrats. Les consignes s’appliquent aussi aux observations et invariants. Le ratio historique du tronc est rejeté s’il revient ; ce contrôle lexical ciblé ne remplace pas la relecture sémantique de toute la prose produite par le LLM.

Tests de régression ajoutés dans tests/test_worker_visual_policy.py et fixtures visuelles adaptées ; non exécutés. Ils portent sur la contamination réelle par l’ancien texte, les références effectivement liées, la persistance, les anciennes suggestions et la perte du lien d’échelle au Writer. Aucune génération de qualification ni redémarrage de service effectué.

Au prochain démarrage habituel du backend, actualiser la page puis reproposer la paire existante, appliquer la nouvelle proposition si une correction manuelle était conservée, relire et envoyer une nouvelle unité. L’ancien rendu ne change pas. La fidélité d’échelle du générateur reste à vérifier lors d’un rendu volontaire.

Diagnostic et sauvegardes : D:/Code/panelforge/.agent/diagnostics/transition-visual-only-20260929/. Cache du script Transitions : 20260929.visual2.
