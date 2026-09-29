# Usine — Lèvres, DLSS, copies English, inondations et groupes, 26 septembre 2026

Statut : implémenté localement après validation du patch. Dernière décision
utilisateur : conserver l’intention française inutilisée des copies English ;
afficher seulement un repère EN sur le titre. Aucun réglage runtime, média,
appel LLM, rendu, test fonctionnel ou service modifié/lancé.

## Demandes et constats

- L’utilisateur demande DLSS activé et Texte Instagram activé en anglais à
  l’application de Lèvres. Conserver Gemma 4 local et 3 variantes.
- H3, une image de fin et un seul plan restent les bases du preset.
- L’intention actuelle décrit seulement un gros plan, un mouvement lent et le
  retour à l’image de fin. Elle ne donne pas la chorégraphie de transformation.
- L’exemple réussi fourni par l’utilisateur dure 10 secondes : lèvres nues,
  rouge à lèvres orné, contact/compression, propagation de l’ornement du bas
  vers le haut, retrait du tube, sourire et image finale stable. L’exemple
  emploie des pierres bleues et sertissages dorés ; ces attributs illustrent
  une image particulière et ne doivent pas devenir obligatoires.
- Le défaut observé par l’utilisateur est un sourire final trop discret.
- L’application du preset Lèvres utilise maintenant default_render_setup(10)
  pour donner du temps à l’application et au sourire.
- Le preset Lèvres réduit les axes à 1/1/1, dialogue 0, audace 1 et liberté
  globale 25. Les gestes sont guidés ; matières et accessoires s’adaptent à l’image.

## Intention automatique implémentée

À partir de l’image fournie comme image de fin, construire un unique plan
beauté ASMR montrant une application qui transforme progressivement des
lèvres nues en lèvres correspondant à cette image. Déduire de la référence
l’identité, le cadrage, la lumière et surtout les couleurs, matières, motifs,
reliefs et finitions à reproduire. Adapter le rouge à lèvres, le tube, les
ongles et les éventuels bijoux de la main à cet univers, sans imposer une
couleur ou un matériau identique d’une génération à l’autre.

Au début, cadrer la même personne du nez au menton, sans les yeux : les lèvres
sont naturelles, nues et fermées. Une main tient près du menton un rouge à
lèvres dont le raisin présente la matière ou l’ornement visible sur les lèvres
de l’image finale. Dans un très léger travelling avant lent, la main approche
le raisin. Les lèvres s’entrouvrent légèrement ; le contact sur la lèvre
inférieure provoque une légère compression visible. Le rouge à lèvres glisse
lentement sur la lèvre inférieure puis supérieure. La matière se propage à
partir des zones réellement touchées jusqu’à reproduire le résultat de
référence sur les deux lèvres. Le raisin garde son propre aspect intact.

Achever l’application assez tôt, puis faire descendre complètement la main et
le tube hors du cadre. Réserver la fin au sourire : les commissures montent
nettement, les joues se soulèvent et les lèvres s’ouvrent en un sourire franc,
chaleureux et clairement lisible, avec les dents supérieures visibles. Le
sourire est installé avant les deux dernières secondes d’une vidéo de dix
secondes ; le tenir jusqu’à la fin, caméra stable et ornement conservé sur
les lèvres. Retrouver le cadrage, la matière et l’expression cible de l’image
de fin. Ambiance ASMR discrète, léger son de contact et accent sonore délicat
adapté à la matière, sans dialogue ni musique.

## Règles de préparation à conserver

- Cette intention guide le Plan puis le rédacteur ; le prompt H3 final reste
  produit dans le format du parcours, avec la référence associée à la fin.
- La durée du prompt et l’instant d’alignement de l’image doivent correspondre
  au réglage de rendu effectif. Défaut : 10 s. Si la durée
  est modifiée, adapter les temps, sans conserver une annotation 10.00 s erronée.
- Déroulé fixe : départ nu → application avec effet au contact → retrait →
  sourire tenu. Une seule prise ; une courte tenue finale fait partie du plan.
- Fin sur 10 s : application et retrait terminés vers 7 s, sourire installé
  vers 8 s et tenu jusqu’à 10 s. Ce séquencement sert de priorité narrative,
  sans garantie de précision temporelle du modèle.
- Le sourire de la référence doit être compatible avec l’expression demandée.
  Une image de fin peu souriante peut limiter l’amplitude obtenue ; une image
  déjà franchement souriante est préférable à des consignes contradictoires.
- Ne pas présenter l’intention comme une garantie de résultat : vérifier sur
  plusieurs images et matières avec les essais de l’utilisateur.
- Les lignes et prompts existants ne sont pas réécrits automatiquement.
  Réappliquer le preset en Préparation pour obtenir le nouveau comportement.
- La durée effective est ajoutée à la préparation Lèvres dès le départ ;
  les repères temporels de l’intention restent relatifs à cette durée.
  Modifier la seule durée d’un rendu avec prompt déjà prêt ne réécrit pas ce
  prompt, conformément au fonctionnement existant et à l’indication de la fiche.

## DLSS : cause du NaN % et correction implémentée

Le contrat DLSS enregistre job.progress comme un objet contenant notamment
percent, stage, stage_index, stage_count et label. L’adaptateur usine transmet
cet objet entier à progress(), alors que stageLabel multiplie step.progress
par 100 en supposant un ratio numérique. La conversion de l’objet produit NaN.

Lors de la lecture du journal, le job actif avait déjà atteint receiving,
avec progress=null ; aucune progression runtime n’a été corrigée manuellement.
Le défaut de contrat est confirmé dans le code indépendamment de cette phase.

Implémentation :

- Normaliser la progression dans l’adaptateur avant de la stocker dans une
  étape usine. Un ratio numérique fini entre 0 et 1, ou aucune mesure.
- Tenir compte du fait que percent est celui d’une phase DLSS ; s’aligner sur
  la conversion du coordinateur de machines à partir de l’index/du nombre de
  phases plutôt que présenter arbitrairement une phase comme tout le traitement.
- Protéger l’affichage avec une validation numérique, y compris pour les
  anciens objets déjà persistés. Pas de NaN, Infinity ou pourcentage aberrant.
- Sans mesure exploitable : En cours, ou Finalisation pendant la réception,
  avec le compteur de secondes qui continue. Ne pas fabriquer un pourcentage.
- Préparer une régression avec l’objet de progression réel, ses changements
  de phase et l’absence de pourcentage pendant receiving/importing.

## Copies English : prompt correct, intention source encore française

Diagnostic en lecture seule des trois lignes actuelles de Séance privée —
English : les prompts prêts contiennent respectivement 2, 3 et 3 répliques
balisées English, aucune French. Les étapes Plan et Prompt sont réussies ;
Vidéo et DLSS sont à suivre. Le rendu utilise le prompt préparé. En revanche,
l’intention garde le source_text français du scénario, y compris la mention
« Répliques françaises exactes » et les anciennes répliques françaises.

La correction précédente de capture du prompt localisé est donc effective
sur ces lignes. Elle n’a pas encore rendu l’intention cohérente avec ce prompt.
L’utilisateur confirme le modèle : injecter les répliques traduites directement
dans le prompt existant ; seule la vidéo doit être refaite, puis le DLSS demandé.

Décision finale de l’utilisateur : ne pas modifier l’intention, puisqu’elle
n’est plus utilisée pour ces prompts prêts. La proposition antérieure de la
recomposer en français avec les répliques anglaises est abandonnée.

Implémentation : badge EN à côté du titre dans la ligne et dans l’inspecteur,
avec infobulle « Répliques anglaises dans le prompt vidéo ». La langue vient
de runtime.episode_inputs.localization.language (English/en) pour une source
épisode. Ni le nom de la fiche, ni la langue Instagram ne servent à la déduire.
Aucune mutation du nom enregistré, de l’intention, des prompts, des empreintes
ou des états Plan/Prompt. Les lignes existantes localisées bénéficient du badge.

## Délimiter les scènes d’un épisode dans les trois onglets

La capture montre un en-tête Séance privée — English suivi de ses trois scènes,
puis de lignes Lèvres. Le tableau actuel ouvre un groupe avec un en-tête, mais
ne le ferme pas visuellement. La case de groupe filtre déjà par identifiant
d’épisode et ne sélectionne pas les Lèvres : le défaut confirmé est visuel.

Implémentation : un bloc discret autour des scènes de l’épisode, avec un en-tête
« Séance privée — English · 3 scènes », des bordures latérales et une vraie
bordure basse après la dernière scène, suivie d’un petit espace. Les lignes
Lèvres suivantes sont clairement à l’extérieur. Éviter un grand fond violet
qui se confondrait avec la ligne sélectionnée ; conserver les colonnes alignées.

Même principe dans Préparation, Production et Résultats. Le nombre affiché
reflète les scènes visibles dans l’onglet. Garder l’ordre de priorité : ne pas
réordonner automatiquement la file pour fabriquer un groupe visuel contigu.
Si un filtre ou une priorité coupe un groupe, chaque segment visible doit avoir
une ouverture et une fermeture. Ne pas créer un nouveau groupe Lèvres obligatoire.

## Petits hommes : intervention d’inondation plus ludique

Les deux derniers plans lus (Corée rural et Russie) utilisent une grande
raclette qui repousse l’eau pour dégager une bande de chaussée. Ce constat
porte sur les plans sauvegardés ; les vidéos n’ont pas été visionnées ici.
Le guidage actuel encourage déjà un outil extérieur, mais ne pousse pas assez
le détournement amusant d’un objet domestique pour les inondations.

L’utilisateur préfère la ventouse de débouchage. Exemple fort ajouté au preset :
une main géante presse la ventouse sur une bouche d’évacuation submergée, puis
la tire avec un petit pop ; un tourbillon aspire l’eau et la rue se vide comme
une baignoire. Le sol reste humide, les décors et les petits hommes restent
intacts. La main remonte hors du cadre et les petits hommes remercient en anglais.
Une seule intervention lisible dans un plan de 8 s, avec le temps de voir l’effet
et la réaction. L’effet doit suivre le geste, pas précéder le contact de l’outil.

Guider ce choix dès le Plan : objet quotidien détourné, geste simple et effet
visuel surprenant mais compréhensible. La ventouse sert de référence forte,
sans la rendre obligatoire sur toutes les générations. Éponge qui gonfle en
absorbant l’eau ou pipette géante sont d’autres pistes éventuelles. Pas de
nouveau preset, catalogue fermé ou appel LLM supplémentaire pour choisir l’objet.
Les plans déjà prêts ne sont pas régénérés automatiquement.

## Vérifications et prise en compte

Contrôles statiques : AST de huit fichiers Python, huit imports de modules,
parsing V8 du script usine et de six fragments de fixtures navigateur, sans
exécution. Avertissement existant Starlette/httpx à l’import du client de test.
Aucun service redémarré, aucune génération, relance ni édition du journal.

Régressions préparées, non exécutées selon AGENTS.md : six cas dans
`tests/test_video_factory_patch3.py`, scénario navigateur supplémentaire dans
`tests/test_video_factory_web.py` (groupes, sélection, ordre, EN, progression
ancienne/invalide et finalisation), attentes de presets actualisées dans les
tests existants. L’effet artistique se valide avec les essais de l’utilisateur.

```powershell
python -m unittest tests.test_video_factory tests.test_video_factory_results tests.test_video_factory_patch3 tests.test_video_factory_web tests.test_dlss
```

Le cache des fichiers usine est passé à `20260926.patch3`. Au prochain
redémarrage habituel du Lab, recharger avec Ctrl+F5. Réappliquer Lèvres ou
Petits hommes aux lignes de Préparation souhaitées pour adopter les nouveaux
réglages et intentions. Les sources, prompts et traitements existants restent
conservés tant que leurs réglages ne sont pas explicitement modifiés.
