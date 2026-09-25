# Proposition — états visuels nécessaires aux prochaines histoires

Statut : proposition à aligner, pas implémentée. Version du code actuel conservée séparément le 25 septembre 2026.

## Objectif et périmètre

Les nouvelles histoires et les nouvelles suites doivent préparer une image dédiée lorsqu’une apparence importante doit rester reconnaissable entre scènes. Exemple : un personnage arrive enceinte avec un ventre visiblement arrondi, devient musclé ou conserve une robe transformée. Réutiliser le registre visual_continuity et les identités existantes.

Pas de réparation de Jus de trahison ni de migration des fabrications, scénarios, images, prompts ou vidéos existants. Aucun lancement en ouvrant un ancien projet. La reprise d’un ancien job doit conserver son contrat. Les trois onglets Références / Scènes / Multilangue restent en place. Les deux images départ/arrivée pendant une transformation visible restent hors de ce lot.

## 1. Écriture : décider du besoin visuel

Préciser les consignes des nouveaux appels : suivre les états déjà acquis à l’ouverture, les changements pendant l’épisode et ceux acquis entre épisodes. Ne pas se limiter aux transformations montrées à l’écran. Déclarer la silhouette, les attributs et la tenue à préserver ; une émotion reste une instruction de jeu, pas un état corporel persistant.

Critère d’image : différence d’apparence significative, importante pour comprendre ou reconnaître le personnage, et devant tenir au fil des plans/scènes. Utiliser tracking=reference et state.reference=true du registre existant. Un geste, une expression ou un accessoire banal reste textuel. Une annonce de grossesse, une citation ou un mensonge ne prouvent pas une grossesse visiblement représentée : pas de règle fondée sur un mot isolé, pas d’invention d’un stade de grossesse ou d’une ellipse.

Pour un état clair déjà présent à la première apparition, utiliser at=start ; pour un état acquis pendant un clip, at=end. Conserver les attributs inchangés, réutiliser une ancre héritée correspondant réellement à l’état et éviter de créer un doublon. Une seule identité et des états, pas plusieurs personnages.

## 2. Contrôle dans la relecture existante

Ajouter une projection de production visuelle à l’appel de relecture existant : personnages visibles, apparences/tenues demandées, états datés et demande de référence. Aucune bible secrète ni connaissance finale du héros ; conserver la lecture fondée sur gestes/paroles.

Vérifier deux directions : chaque état majeur joué est couvert par le registre ; chaque variante demandée correspond à un besoin visible réel. La présence d’un personnage uniquement en voix téléphonique ne crée pas un besoin d’image dans cette scène.

Pour une omission sans ambiguïté, autoriser une correction structurée limitée au registre visuel dans la réponse existante : aucun changement de réplique, d’événement, de décor ou de durée. Cibler des IDs explicites, contrôler la révision et valider l’ensemble du registre avant application atomique. Une proposition invalide ne doit pas effacer le scénario valide ni engendrer une boucle de réécriture. Une ambiguïté reste une suggestion concise à l’auteur, pas une apparence choisie arbitrairement.

Cette extension des réponses doit avoir un contrat versionné et rester compatible avec les réponses historiques. Les opérations et prompts des jobs déjà enregistrés restent inchangés. Aucun appel LLM systématique supplémentaire ; budget de correction automatique inchangé.

## 3. Fabrication : préparer les variantes dans le parcours habituel

Afficher les fiches d’état parmi les références à préparer, avec personnage, état et scènes concernées. Exemple : « Fraise · Enceinte — scènes 3 et 4 — image à préparer ». Préserver le parcours d’identité et les choix d’images existants.

Une variante se dérive de l’image d’identité retenue via le service Qwen existant. Déclarer une dépendance à cette image ; si elle manque, indiquer « En attente de l’image de Fraise ». Un import ou un résultat déjà accepté peut satisfaire la même fiche. La génération d’une nouvelle image est une tâche GPU visible, lancée avec la préparation des références, jamais comme effet caché de la relecture ou de l’ouverture de l’écran.

Étendre le lot existant pour distinguer création d’identité et édition d’état, sans envoyer une variante dans le chemin KREA de création indépendante. Réutiliser l’ordonnanceur, les IDs de projet/étape/essai, la reprise et les erreurs Qwen existants ; ne pas créer un second moteur de queue. Mémoriser l’image source et la description d’état utilisées pour détecter un résultat devenu obsolète. La sélection/validation de l’image suit le parcours de références existant.

## 4. Routage et dépendances lisibles

Avant de préparer ou lancer une scène, résoudre l’état visuel courant et vérifier son image. Une image obligatoire manquante/obsolète expose le nom précis de la dépendance et l’action pour la préparer. Les autres scènes indépendantes peuvent avancer. La file ne doit ni attendre indéfiniment sans motif ni retomber silencieusement sur l’identité initiale.

Une fois la variante retenue, les scènes stables utilisent l’état courant seul. Les scènes précédentes conservent leur apparence. Une ellipse commence directement dans l’état acquis. Une transition visible conserve la gestion actuelle et ne doit pas être présentée comme prenant déjà en charge deux images départ/arrivée.

Aucun changement des prompts vidéo archivés, médias ou copies multilangues existantes. Les futures copies réutilisent les références résolues de leur fabrication source.

## Ordre du patch et vérifications

1. Consignes et contrats des nouveaux appels, projection de contrôle, application bornée des corrections de registre.
2. Fiches et lot de variantes Qwen avec dépendance à l’identité et reprise explicite.
3. Contrôle des références requises au lancement, états d’attente lisibles et routage par scène.

Régressions ciblées à préparer : état acquis avant l’épisode ; état hérité réutilisé sans doublon ; grossesse annoncée seulement ; personnage hors champ ; muscles persistants et tenue inchangée ; correction de registre sans modification narrative ; sortie LLM invalide conservant le scénario ; image source remplacée en cours de préparation ; variante manquante sans repli silencieux ; ancien projet inchangé ; pas d’appel supplémentaire à l’ouverture. Tests exécutés par l’utilisateur conformément aux consignes du projet.
