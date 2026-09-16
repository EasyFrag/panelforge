# Atelier Épisode — cadrage en micro-scènes de 10 secondes

Discussion du 15 septembre 2026, suivie d'une autorisation d'implémenter l'espace
Histoires dans le bandeau principal. La première partie (propositions, discussion,
scénario et intentions) est livrée ; [guide](../stories-1.0.md). La suite de
production a ensuite été autorisée pour une première version : [guide Fabrication](../episodes-1.0.md).
H3 conserve ses moteurs et ses réglages ; le nouvel atelier coordonne les moteurs
actuels. P1 I2V et P2 analyse adaptative gardent leurs priorités.

## Fabrication 1.1 — retour utilisateur et alignement

Alignement confirmé, puis **implémentation autorisée et effectuée le 16 septembre**.
Voir [le guide à jour](../episodes-1.0.md). Le cadrage ci-dessous décrit le patch.
La v1 coordonne les
moteurs, mais son interface image a été trop simplifiée : checkpoint sans le
picker partagé, LoRA sans sélection UI, style texte seul. Les axes de créativité
sont fixés dans le service et seul le niveau d'audace est visible.

Proposition pour la prochaine itération :

- **Style d'épisode** : reprendre le catalogue de presets de style KREA2 Assisted
  (exemple image/prompt, checkpoint et LoRA), ou définir un style texte avec une
  image importée ou une fiche retenue. Appliquer explicitement le style commun
  aux prochaines préparations des personnages et décors. L'image guide le LLM
  pour les matières, palette, lumière et niveau de stylisation ; ne pas recopier
  son identité, sa tenue ou son décor. Aucun conditionnement supplémentaire du
  workflow image n'est promis. Un preset choisi doit rester une version figée
  pour l'épisode jusqu'à une nouvelle application explicite.
- **Fiches KREA2** : même picker checkpoint avec favoris/informations, même pile
  LoRA avec forces. Paramètres communs hérités et exception par fiche clairement
  signalée. Garder format/seed indépendants du style. Les presets de sampling
  Actuel 8+2, Finition 8+4 et Moody Beta 8+4 sont déjà dans la v1 ; conserver ce
  sélecteur distinct des presets de style et leurs réglages réels.
- **Scènes REF2V** : mêmes sliders audace, vie de la scène, caméra, mouvements
  additionnels et dialogues/réactions ; persister et transmettre chaque axe,
  au lieu de valeurs cachées. Dialogues/réactions à zéro par défaut, préserver
  les répliques exactes du scénario. Ne pas modifier les parcours H3/REF2V actuels.
- **Traçabilité** : enregistrer le style/preset et les réglages effectivement
  utilisés pour chaque prompt/essai. Une nouvelle sélection n'écrase pas les
  références déjà retenues ni les anciens prompts. Signaler les préparations à
  refaire et distinguer clairement les exceptions par fiche.

Manques suivants à garder séparés : réutiliser les fiches lors d'une nouvelle
version du scénario, continuité des objets/voix entre clips, fabrication en lot
et assemblage. P1 I2V, P2 analyse adaptative et import Video Lab restent différés.

## Alignement Fabrication demandé le 15 septembre

Alignement ensuite autorisé et implémenté le 15 septembre. L'utilisateur précise le parcours : scénario
validé (ou importé plus tard), génération des personnages et décors par un KREA2
Assisted simplifié, puis sélection d'une micro-scène dans un menu déroulant pour
préparer son prompt REF2V et rendre sa vidéo.

Proposition d'interface dans Histoires : **Histoire → Références → Scènes**.
« Valider et préparer la fabrication » ouvre les références de l'épisode. Chaque
fiche possède une description éditable, une génération KREA2 compacte, les essais
et une image retenue ; une image existante peut aussi être importée. Un style
visuel commun évite que les fiches dérivent entre elles. Utiliser les services
KREA2 Assisted actuels plutôt que créer un autre moteur de prompting d'image.

La vue Scènes présente un menu « Scène N — titre · durée · état », les références
associées, l'intention avec les dialogues exacts, un résumé des presets puis les
actions préparer le prompt et générer la vidéo. Les contrôles détaillés restent
repliables. Une même référence personnage/décor est réutilisée par toutes les
scènes où son identifiant figure ; les affectations et rôles restent modifiables
par scène. Personnage → Sujet / identité, lieu → Décor. Conserver le lien entre
personnage, image, numéro Picture local à la scène et locuteur du dialogue,
même après réordonnancement des références.

Defaults demandés pour cet atelier :

- REF2V Classique à deux appels expérimental, actuellement
  `minimax.h3.ref2v.classic.cinematic.planned@1.0.0` : Qwen 27B local pour le Plan,
  Gemma 4 local pour la rédaction, deux sélecteurs modifiables. Les variantes
  exactes peuvent reprendre les choix de l'utilisateur ; ne pas imposer une
  variante différente sans l'afficher.
- Rendu BUNNY actuel `minimax-h3-bunny@0.1.3`, réglages de base existants, durée
  reprise de la micro-scène (10 s par défaut).
- Pile initiale de cet atelier : Motion Repair actif, fichier du manifeste
  `minmax_nsfw/Motion_Repair.safetensors`, forces existantes 0,60 / 0,20. Le
  manifeste BUNNY contient également Combat V2 par défaut : constituer une pile
  explicite Motion Repair pour l'atelier narratif, sans changer le manifeste ni
  les valeurs des ateliers existants. LoRA/checkpoint/Turbo/steps restent éditables.

Points de persistance : une version du scénario est retenue pour la fabrication,
chaque scène reçoit un identifiant stable, des liens vers ses références et ses
propres essais. Un changement d'image ou de scénario signale les scènes concernées
à actualiser ; il ne réécrit pas les images, prompts et rendus historiques. Les
versions exactes des recettes et paramètres sont enregistrées dans l'épisode,
plutôt que suivre automatiquement une future « dernière version ». Les réglages
communs initialisent les scènes ; leurs personnalisations restent distinctes.

**Limite corrigée après vérification complète : neuf images REF2V au total.**
Le manifeste de base `minimax-h3-ref2v@0.2.4` expose trois loaders, mais
`Ref2VH3RenderPresetRecipe` ajoute les entrées quatre à neuf. C'est cet adaptateur
que `run_lab.py` injecte dans H3RenderService : la garde de création applique neuf,
pas trois. L'interface REF2V, les contrats de session/projet et BUNNY acceptent
également neuf références. Les descriptions des nœuds installés sur Bucket,
`MiniMaxH3ReferenceToVideo` et `MiniMaxH3AudioConditioningT8`, confirment toutes
deux `ref_images.max=9` (GET object_info le 15 septembre, sans génération).

L'annonce précédente de trois images et la question de repli personnages/décor
étaient donc erronées pour le parcours actuel. Trois personnages plus un décor
occupent quatre des neuf images disponibles. Retenir cette capacité pour l'atelier,
avec rôles et ordre modifiables ; aucun besoin de supprimer le décor par défaut.
Il s'agit d'un total d'images par rendu, pas de neuf personnages plus des décors.
Les neuf références ne constituent pas une garantie de fidélité visuelle à neuf
sujets ; aucun rendu de vérification n'a été lancé pendant cet audit.

L'ancien rendu Video Lab reste limité à trois images et le transfert historique
`sendToVideoLab` tronque explicitement à trois. Ne pas réutiliser ce chemin pour
l'atelier : réutiliser le rendu REF2V intégré. Aucun correctif fonctionnel demandé
dans cet échange, et aucune extension au-delà de neuf décidée.

L'import depuis Video Lab est explicitement différé par l'utilisateur. Distinguer la
durée de la vidéo analysée (>15 s, voire l'épisode complet) de la durée cible des
clips générés (~10 s). Une analyse longue doit produire un scénario structuré
avec scènes/personnages/décors/dialogues, puis passer par la même validation.
Le chemin d'import reste à valider ; conserver ce travail lié à P2 analyse
adaptative, sans le confondre avec une augmentation de durée du rendu REF2V.

## Parcours demandé

1. **Histoire** : proposer plusieurs histoires à partir d'une idée, puis dialoguer
   avec le LLM pour en choisir une et l'affiner. La sortie validée décrit toutes
   les micro-scènes, avec personnages, décors et répliques attribuées.
2. **Micro-scènes de 10 secondes** : chaque bloc devient une unité de rendu.
   Il précise son enjeu, ses personnages, son décor, l'action, les dialogues,
   l'état initial et ce qui a changé à la fin. Le texte doit laisser du temps
   aux réactions ; une réplique trop longue est répartie entre plusieurs blocs.
3. **Fiches personnages via KREA2** : description stable, propositions visuelles,
   image de référence retenue, éventuelles vues et expressions complémentaires.
   Cette référence est réutilisée dans toutes les scènes concernées. Une fiche
   légère de décor récurrent est proposée pour éviter les changements de lieu
   involontaires. Les objets importants et leurs états suivent aussi l'histoire.
4. **Storyboard textuel** : pour chaque micro-scène, intention narrative,
   actions et réactions attendues, références à utiliser, dialogues insérés
   automatiquement et raccord avec le bloc suivant. L'utilisateur préfère
   laisser au LLM la créativité de mise en scène, sans imposer de caméra ni
   de découpage dans l'intention.
5. **Fabrication des clips** : file de rendus H3/REF2V, aperçus, sélection des
   prises et reprise d'un seul bloc si nécessaire. Les deux appels actuels
   Plan/Rédaction sont conservés pour chaque clip.
6. **DLSS puis livraison** : upscale des prises retenues, assemblage de l'épisode
   et, si souhaité, sous-titres synchronisés à la parole réellement produite.

## Distinctions à conserver

- **Micro-scène = rendu de 10 s ; plan = cadrage à l'intérieur de ce rendu.**
  Une micro-scène peut être en plan unique ou comporter un champ/contrechamp
  et une réaction. Aucun quota de coupures à imposer à tous les blocs.
- Le storyboard textuel est la consigne de réalisation validée par l'utilisateur.
  Le Plan JSON H3/REF2V reste une étape technique interne existante.
- Les répliques du scénario sont la source des dialogues : le storyboard les
  reprend avec leur locuteur, sans reformulation automatique. Une modification
  du scénario doit signaler les seules scènes concernées comme à actualiser.
- Les fiches sont communes à l'épisode ; chaque clip ne reçoit que les références
  utiles, dans leurs rôles et leur ordre. La continuité ne repose pas uniquement
  sur la dernière frame du clip précédent.

## Choix de génération à discuter

### Ton narratif précisé après les essais REF2V

Le 15 septembre, l'utilisateur confirme que les intentions laissant de la
liberté au LLM fonctionnent plutôt bien. Il a demandé deux versions du même
échange accusation/révélation : durée explicitement fixée à huit secondes et
durée absente du texte, toutes deux sans consigne de plan caméra. Ce test ne
remplace pas automatiquement le format de production de dix secondes discuté.

Le générateur d'histoires recherché doit produire des concepts simples avec
un ton « skibidi / brainrot », des antagonistes très excessifs et des contrastes
forts. Quatre vidéos ont été examinées par captures et sous-titres visibles
(`Download(6).mp4`, `Download(2).mp4`, `Download.mp4`, `Download(5).mp4`) ;
aucune écoute ou transcription n'a été effectuée. Les observations suggèrent
des conflits immédiatement lisibles, des preuves ou objets concrets, une
escalade causale et des révélations visuelles. Les fins peuvent être morales,
ironiques, cruelles ou ouvertes ; ne pas généraliser la réconciliation du
pilote Lila/Victor à toutes les histoires.

Proposition à discuter : un appel propose trois concepts réellement différents
(accroche, antagoniste, escalade, révélation et fin), puis un appel développe
le concept retenu en scénario complet avec dialogues attribués. Les échanges
de révision restent facultatifs. Le découpage en micro-scènes et les intentions
viennent ensuite ; les deux appels Plan/Rédaction vidéo existants restent
distincts de ces appels d'écriture de l'histoire. Tester le ton sur quelques
synopsis avant de construire l'interface. Une courte recette éditable avec
des exemples contrastés et un rappel des idées déjà produites suffit comme
point de départ. Cette partie a ensuite été autorisée et implémentée dans Histoires.

REF2V permet de partir directement des fiches personnages et décors. I2V reste
possible ; il ajoute alors une image de mise en scène par micro-scène, à préparer
avant animation. Ce choix doit être visible et ne pas cacher une étape de
génération d'image non prévue dans le scénario de fabrication.

La continuité vocale entre clips reste à vérifier. Une indication de voix dans
une fiche ne constitue pas un verrouillage du timbre par le moteur actuel.

## Retrait des anciens ateliers

Sur demande utilisateur, Production V1/V2 sont retirés de la navigation et leurs
scripts ne sont plus chargés par la page du Lab. Les vues enregistrées en session
sur ces anciens ateliers reviennent sur Image Lab. Les données, le backend et
les éléments historiques masqués sont conservés ; aucune suppression de projets
ni interruption de processus. Le nouvel atelier ne dépendrait pas de leurs
anciens parcours de prompting.
