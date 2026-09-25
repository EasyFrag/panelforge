# Usine à vidéo — proposition du 25 septembre 2026

Statut : maquette de discussion, sans intégration applicative. Ouvrir [la maquette interactive](video-factory/index.html) dans un navigateur. Elle utilise des exemples et simule les traitements ; elle ne contacte ni PanelForge, ni ComfyUI, ni les modèles. Les modifications disparaissent au rechargement.

## Intention

Préparer plusieurs vidéos depuis les ateliers existants, puis lancer leur fabrication complète sans revenir remplir les étapes intermédiaires. Une ligne représente une vidéo finale et regroupe toutes ses dépendances.

Hypothèse proposée, à confirmer : une histoire produit une ligne par épisode final, avec les scènes à l’intérieur. Une scène seule peut aussi être envoyée comme vidéo indépendante.

## Écran proposé

- Un onglet **Usine à vidéo**, au même niveau que les ateliers actuels ; palette crème et verte de PanelForge.
- Une liste centrale : ordre, image/titre/source, preset, avancement précis, texte Instagram.
- Un panneau à droite : preset, images et rôles, préparation H3/REF2V, nombre de plans, intention ou prompt, rendu, réglages avancés et Instagram.
- Deux indicateurs de ressources : local et serveur. Motif d’attente lisible.
- Actions : lancer les lignes prêtes, pause des prochains départs, reprendre ; réordonner, dupliquer. En production : retirer un brouillon, annuler une ligne, consulter les sorties et reprendre une étape en erreur.
- Une histoire conserve son paramétrage. Le panneau donne accès aux scènes et, dans l’intégration future, à leur fabrication détaillée.

La maquette permet de sélectionner, filtrer, réordonner, appliquer/enregistrer un preset en mémoire, attribuer les rôles, modifier le prompt et certains réglages, ajouter une image exemple, dupliquer et activer Instagram. Le bouton de simulation fait terminer les étapes en cours puis choisit les suivantes ; il ne représente pas leur durée réelle.

## Entrées dans l’usine

| Source | Action proposée | Contenu transmis |
| --- | --- | --- |
| Image Lab, image retenue | Envoyer vers l’usine vidéo | Image sélectionnée, titre, lien vers la source et réglages existants |
| H3 Base / REF2V | Envoyer vers l’usine vidéo | Images et rôles, intention ou prompt existant, mode et réglages effectifs |
| Histoires, avant de lancer les scènes | Envoyer vers l’usine vidéo | Épisode, scènes, références, prompts déjà préparés, réglages par scène et assemblage |

L’envoi crée un brouillon durable, sans lancer de génération. Le preset favori du parcours peut être proposé. Une ligne devient **Prête** lorsque tous les choix humains nécessaires sont renseignés. Il peut rester des prompts/images/vidéos à calculer automatiquement ; « Prête » ne signifie pas que toutes les sorties intermédiaires existent.

Si une étape réclame encore un choix humain (référence non sélectionnée, rôle incompatible, intention vide, langue Instagram absente), la ligne reste **À compléter**, avec un lien vers le champ concerné. Les autres lignes peuvent démarrer.

## Presets et défauts

**Lèvres** : H3, image envoyée affectée à la dernière frame, un plan, intention type éditable, Bunny + Motion Repair, autres réglages hérités des défauts actuels, Instagram désactivé. La durée de 8 s et le texte présents dans la maquette sont des exemples, pas une modification des défauts de l’application.

Un preset contient des réglages et des emplacements de références, sans incorporer les images de la vidéo qui a servi à le créer. Les images suivantes remplissent ces emplacements. Une image supplémentaire ou un mode incompatible doit être expliqué, jamais ignoré silencieusement. Appliquer un preset ne touche que la ligne choisie ; les modifications suivantes sont propres à cette ligne, sauf enregistrement explicite d’un nouveau preset.

Ordre de résolution proposé : réglages effectifs de la source (sinon défauts actuels) → champs explicitement définis par le preset → ajustements de la ligne. La sélection d’un preset doit montrer ce qu’elle remplace, en particulier le prompt. Conserver la copie source permet de revenir à « Réglages source ».

Au lancement, conserver un instantané complet et versionné : assets et rôles, recettes, modèles, prompts, paramètres, seeds effectives, dépendances, paramètres Instagram. Changer ultérieurement un preset ou les défauts ne modifie pas les productions lancées. La maquette fige les champs au lancement ; en production, dupliquer ou créer une nouvelle révision pour modifier une production engagée.

Point de vocabulaire vérifié : **Bunny + Motion Repair est le rendu vidéo** dans le code actuel. Une préparation d’image éventuelle conserve son propre traitement existant et ses réglages ; elle n’est pas remplacée par Bunny. Le mode de préparation H3/REF2V et la recette de rendu restent distincts, avec validation de compatibilité des frames/références.

## Instagram, optionnel

- Désactivé à la création d’une ligne.
- Lorsqu’activé : Gemma 4 local, trois variantes, langue explicitement choisie. La langue peut être mémorisée dans un preset.
- Vidéo associée automatiquement à la sortie de la ligne : rendu H3 pour un clip, épisode assemblé pour une histoire. Aucun sélecteur manuel à remplir après le rendu.
- Générer et conserver les textes ; aucune publication sur Instagram n’est incluse.
- Vidéo consultable dès sa disponibilité. Si le texte échoue, afficher « Vidéo prête · texte à reprendre », puis reprendre uniquement le texte, sans refaire la vidéo.
- Le contrat social actuel expose français et anglais. La maquette propose ces langues ; toute extension devra être décidée séparément.

## Ordonnancement

Règle : **pour chaque ressource disponible, parcourir les lignes dans leur ordre et démarrer la première étape exécutable**. Une étape est exécutable si la ligne est lancée, ses dépendances sont terminées, ses paramètres sont complets et la ressource l’admet.

1. La vidéo 1 rend une scène sur le serveur. Le local prépare le prompt de la vidéo 2.
2. Le prompt 2 est prêt mais le serveur est occupé. Le local peut préparer le prompt 3.
3. Le serveur finit sa scène. Si la vidéo 1 a une autre scène prête, elle passe avant le rendu 2.
4. Si la vidéo 1 attend une autre ressource, le serveur lance le rendu 2. Lorsque la vidéo 1 redevient exécutable, elle reprend la priorité à la prochaine libération de la ressource nécessaire.

On ne coupe jamais un calcul en cours pour reprendre cette priorité. Une seule tâche par machine selon les règles actuelles ; local et distant avancent indépendamment. Les pauses thermiques, indisponibilités et réservations du coordinateur restent applicables. Pause empêche de nouveaux départs, sans tuer les calculs engagés.

Une erreur récupérable bloque la branche concernée et laisse les autres lignes avancer. Un incident global de machine ou une règle de pause générale garde sa portée actuelle. Afficher le motif et permettre la reprise de l’étape échouée, en conservant les sorties déjà obtenues. Pas de boucle de relance illimitée.

Cette politique privilégie les premières vidéos. Les dernières peuvent attendre longtemps si l’on ajoute constamment de nouvelles priorités en tête ; un mode équitable peut être une évolution ultérieure.

## Raccordement envisagé après alignement

Le dépôt courant contient une interface plus ancienne. L’interface récente, les histoires et le coordinateur ont été consultés en lecture dans `D:/Code/panelforge-krea2-flux`, conformément à la continuité. Aucun de ces fichiers n’a été modifié.

- `domain/episodes.py` : `default_render_setup()` définit Bunny 0.1.3, portrait, 0,9 MP, 9 steps, musique désactivée et Motion Repair à 0,6 / 0,2 ; les réglages effectifs de l’épisode peuvent les surcharger. Résoudre également les variantes/versionnements effectifs au lancement, sans forcer une ancienne recette.
- `features/lab/static/work-queue.js` : files local/serveur et garde-fous existants. L’usine ajoute des flux persistants au-dessus des tâches unitaires actuelles.
- `features/lab/static/h3-render-lab.js`, `episodes.js`, `social-lab.js` : réutiliser les services et contrats actuels pour produire les sorties et les textes.
- Contrat de flux : identité explicite, source/révision, preset/version, configuration résolue, dépendances, étapes et liens vers les jobs/assets existants. Aucun ID de nœud ComfyUI dans le code de la fonctionnalité.
- L’ordonnanceur soumet juste les étapes admises, pas tout le graphe d’avance dans une FIFO : sinon les tâches du flux 2 déjà en file empêcheraient la priorité souhaitée au flux 1. Préserver les tâches manuelles déjà admises et éviter un second ordonnanceur concurrent contournant les réservations.
- Idempotence d’envoi/lancement, réconciliation après redémarrage et rattachement aux exécutions existantes avant toute nouvelle soumission. Ne pas promettre une resoumission exactement une fois sans mécanisme d’idempotence du fournisseur.
- Reprise sélective : réutiliser toute étape terminée dont les entrées sont inchangées ; une modification invalide uniquement ses dépendants. Conserver les sources et leurs historiques.

## Points à discuter

1. Une ligne par épisode final, ou par scène avec regroupement d’épisode ? La maquette part sur l’épisode final.
2. Le preset Lèvres est-il seulement proposé à l’envoi d’une image, ou appliqué automatiquement depuis un parcours Lèvres identifié ?
3. Inclure dès la première version les finitions facultatives (DLSS, conversion, miniature) ? À défaut, conserver seulement celles déjà configurées par la source.

## Vérification de la maquette

Contrôle visuel dans Chrome sans interface ; aucune dépendance ajoutée, aucun appel applicatif, LLM ou GPU. Les exemples et le moteur de simulation servent à examiner l’ergonomie et la priorité, pas à valider le futur backend.

Vérification interactive : 37 contrôles DOM réussis dans Chrome en fenêtre large et étroite (presets, rôles, Instagram, filtre, lancement, priorité par machine, pause/reprise, terminaison des flux).
