# Progression visuelle et création itérative d’images — brief transmissible

Date : 28 septembre 2026.
Statut : brief historique. Les deux volets ont ensuite été autorisés et implémentés localement. Pour la V1 retenue et son fonctionnement, voir [Parcours d’images autonome](../design/image-journeys-guide.md).

Alignement final : deux rôles (Progression visuelle et Prompt MiniMax), mode travaux avec destination et grands jalons,
cadrage et point de vue fixes, poursuite après une image trop similaire, pause avec modification de l’intention.
L’atelier autonome se trouve à côté de Modifier avec Minimax. Les propositions initiales ci-dessous sont conservées
comme historique ; le guide et la continuité décrivent la version implémentée. Le rejeu sémantique reste une évolution future.

## Contexte et premier patch à conserver

PanelForge possède des ateliers d’édition KREA, Qwen et MiniMax, ainsi qu’une usine à vidéo. L’utilisateur crée des états successifs d’un même décor, par exemple un arbre brut, une ouverture, une porte, un intérieur puis son aménagement.

Le premier patch prévu est un atelier de transitions d’images. Son principe est aligné : l’utilisateur ordonne des images existantes ; chaque paire consécutive devient une transition vidéo H3 first/last (FL2VA). Des intentions françaises sont proposées par LLM, éventuellement orientées par une indication personnelle, puis relues avant envoi des unités à l’usine. N images donnent N−1 transitions. Les actions peuvent être des travaux accélérés, du nettoyage ou un déplacement dans le décor.

Une description commune de l’ouvrier suffit au départ. L’usine conserve son parcours de préparation Plan → Prompt → Vidéo. L’UX doit être compacte, inspirée de l’usine vidéo et des ateliers image : frise, liste de transitions et panneau partagé de détail. L’utilisateur préfère cette approche à l’UX du mode histoire.

Le premier patch est désormais implémenté localement ; voir ../design/image-transitions.md. La proposition détaillée historique reste image-transition-workshop-2026-09-28.md, dans ce même dossier.

## Deuxième volet : demande explicite

L’utilisateur souhaite maintenant aligner un squelette de création autonome de la suite d’images, qui était jusqu’ici une ambition à long terme.

Entrées demandées :
- Une image de départ.
- Une intention initiale facultative.
- Un nombre d’étapes.
- Des LLM paramétrables selon leur rôle.

Le moteur d’édition d’image demandé est le nouveau MiniMax déjà intégré à PanelForge. Le système doit proposer et itérer seul, en analysant les résultats réels. L’interface et la première version doivent avoir un minimum de fonctionnalités et de manipulations.

La relecture humaine convenue pour les intentions vidéo ne devient pas une validation obligatoire entre toutes les générations d’images. Le lot d’images est conçu pour avancer automatiquement après lancement.

## Squelette proposé, à discuter

Convention proposée : K étapes désigne K nouvelles images ; avec le départ, la frise comporte donc K+1 images et peut alimenter K transitions vidéo. Exemple : 5 étapes → 6 images au total.

Au départ, le LLM observe l’image et reformule une direction courte à partir de l’intention. Si elle est vide, il choisit une progression cohérente avec l’image. Cette direction est conservée comme contexte commun et affichée, sans imposer une validation préalable.

La boucle avance une transformation à la fois :
1. Observer l’état courant, les changements déjà réalisés et le nombre d’étapes restantes.
2. Choisir la prochaine transformation avec une action courte et les éléments à conserver.
3. Rédiger le prompt d’édition MiniMax.
4. Générer une nouvelle image à partir de la dernière image retenue.
5. Comparer le résultat à sa source et à la transformation demandée, puis décider de la suite sur cette base réelle.

L’observation du résultat et la proposition suivante sont réunies dans le même appel du LLM de progression. Une relecture finale de la dernière image clôt la série. Il n’y a pas de scénario détaillé figé pour toutes les étapes avant la première génération.

Un changement de point de vue, comme passer de l’extérieur à l’intérieur de l’arbre, peut être proposé lorsqu’il sert la progression. Les repères du lieu et les changements déjà acquis doivent rester dans le contexte. Les images représentent les états après transformation ; outils, ouvriers et gestes intermédiaires seront décrits au moment des transitions vidéo si nécessaire.

## Deux rôles LLM proposés

| Rôle | Responsabilité |
| --- | --- |
| Progression visuelle | Observe les images, choisit la direction et la prochaine transformation, relit le résultat et adapte la suite. Ce rôle nécessite un modèle et un accès capables d’analyser les images. |
| Prompt MiniMax | Transforme l’intention d’édition et les éléments à conserver en prompt adapté au moteur MiniMax, en réutilisant le prompter spécialisé existant. |

Deux sélecteurs indépendants, pouvant désigner le même modèle. Le moteur d’image reste MiniMax pour cette version. Le choix des LLM des étapes H3 reste celui du parcours usine existant.

Pour limiter les appels, le rôle Progression combine constat et décision suivante ; le rôle Prompt ne reconstruit pas un second scénario. La génération doit réutiliser le parcours MiniMax existant, sans doubler son appel de prompt ou déclencher deux rendus.

## Limites minimales proposées

Une seule suite linéaire, une image candidate par étape. Pas de branches ni de recherche automatique de la meilleure variante dans cette première proposition.

Un écart compatible avec la direction peut être intégré dans la suite ; une erreur technique ou un résultat que le LLM juge inexploitable suspend la progression sur l’étape concernée. L’utilisateur peut reprendre après correction. Aucune boucle de réessais sémantiques automatique n’est proposée à ce stade. Cette limite est un choix de simplicité à discuter, pas une exigence déjà validée.

Une suspension demandée empêche de démarrer l’étape suivante ; elle n’annule pas implicitement un rendu déjà lancé. Le résultat de ce rendu reste enregistré. Sauvegarder après chaque étape permet une reprise sans refaire les images terminées ; la fermeture de l’onglet ne doit pas perdre la série.

Conserver par étape : image source et résultat précis, action visée, constat sur le résultat, prompt et modèle utilisés, état d’exécution. Le contexte du LLM comprend une synthèse courte de la progression et les repères visuels utiles ; ne pas renvoyer sans limite tout l’historique détaillé.

## UX proposée

Dans le même atelier, l’action « Créer une suite » ouvre un formulaire compact :
- Image de départ.
- Intention facultative.
- Nombre de nouvelles images.
- Un volet « Modèles » replié avec les deux choix de LLM.
- Un bouton de lancement.

En dessous, la frise se remplit au fur et à mesure. Chaque vignette affiche une action courte ; sa sélection montre l’image en grand et le détail de l’étape. Une ligne d’état indique l’étape courante et l’opération en cours : analyse, rédaction, génération ou relecture. Une commande de suspension/reprise suffit pendant l’exécution.

Une fois les images disponibles, « Préparer les transitions » les reprend dans le premier atelier. L’intention d’édition décrit l’état fixe à obtenir ; l’intention vidéo décrit comment passer d’un état à l’autre, avec des gestes, une durée et une caméra. L’historique de création aide cette préparation, mais les images réellement retenues restent la référence.

Les intentions H3 sont ensuite relues avant envoi à l’usine. La création de la suite ne lance pas automatiquement les vidéos.

## Points encore proposés, non acquis

- Convention K étapes = K nouvelles images.
- Deux rôles LLM, dont l’un réunit observation, relecture et décision.
- Une candidate par étape et suspension si un résultat bloque la progression ; corrections automatiques à envisager ultérieurement.
- Création de la suite dans le même atelier, par un formulaire compact.

Ce document reste le brief d’alignement de la création autonome. La demande d’implémentation ultérieure concerne le premier patch de transitions ; elle n’est pas étendue implicitement à cette boucle de génération d’images.
