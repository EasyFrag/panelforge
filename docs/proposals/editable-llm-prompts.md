# Consignes LLM accessibles — proposition du 14 septembre 2026

Discussion demandée après validation de la maquette vidéo. Ne pas confondre
le prompt H3 final destiné au rendu avec les consignes système du LLM qui le
prépare. L'utilisateur souhaite consulter ces dernières simplement, modifier
leurs fichiers sources et séparer les versions actives des anciennes.

Ce document décrit le rangement et la traçabilité, sans modifier de consigne,
recette, validateur ou appel. Le texte joint par l'utilisateur sert uniquement
à identifier l'assemblage ; ses instructions et son contenu ne sont pas adoptés.

## Précision utilisateur : éditeur simple et historique durable

L'utilisateur veut pouvoir modifier une consigne, enregistrer, puis utiliser
automatiquement cette modification pour les prochains runs de la recette.
Sélectionner une ancienne version et l'appliquer doit la réactiver. Il souhaite
aussi consulter les échanges LLM une fois la vidéo terminée. Il accepte un
rangement de fichiers plus simple comme alternative si un écran serait trop lourd.

Recommandation : un petit écran **Recettes LLM**, accessible depuis « Consignes
LLM », limité aux recettes actuelles. Une recette, une étape Plan/Rédaction/
Ajustement, un éditeur, un sélecteur de révision, un bouton **Enregistrer et
appliquer**. Une révision choisie dans l'historique peut être réactivée par
**Appliquer cette version**. La portée est explicite (famille, mode ou modes
concernés), sans propagation aux autres familles. Un numéro automatique de
révision suffit ; pas de gestion de branches Git, de diff ou d'éditeur complexe
imposée à l'utilisateur. Les sources restent des fichiers et la révision active
une petite référence persistante ; pas de nouvelle base de données ou service.

Une sauvegarde crée une révision immuable et la rend active, sans écraser la
précédente. Tout nouveau cycle de préparation ou d'ajustement de la recette
utilise cette révision, y compris depuis un projet déjà ouvert. Les appels
déjà effectués restent inchangés. Un Writer poursuivant un Plan existant garde
le paquet de consignes de ce Plan ; une nouvelle préparation utilise le paquet
actif. Le changement devient ainsi le défaut persistant sans devoir sélectionner
la version à chaque lancement, sans modifier rétroactivement une préparation.
Un nouveau rendu utilisant un prompt H3 déjà rédigé ne fait pas d'appel LLM :
la modification des consignes prend effet à la prochaine préparation ou au
prochain ajustement, pas en réécrivant automatiquement le prompt lors du rendu.

Depuis un rendu terminé : **Échanges LLM** liste les appels qui y ont réellement
contribué, et les ajustements associés. Pour chaque appel : système exact, user/
contexte/schéma exacts, réponse et raisonnement s'il a été fourni, modèle, date,
étape, révision et résultat/erreur. Chargement à la demande ; les images restent
référencées par leurs assets, sans duplication de leurs octets. Une erreur de
préparation survenue avant l'appel est indiquée comme telle, sans inventer de
message « envoyé ». Les traces doivent être liées durablement à la préparation
et au rendu ; le journal tournant de vingt appels ne suffit pas.

Les anciennes traces déjà évincées ne peuvent pas être recréées fidèlement à
partir des fichiers actuels. Réutiliser seulement les traces dont l'association
au run est certaine, et signaler ce qui manque. Le stockage doit garantir les
futurs runs et ne pas présenter une reconstruction comme un appel historique.
Cette précision remplace l'approche « éditeur externe seulement » comme option
recommandée ; la simple arborescence reste l'alternative proposée par l'utilisateur.

## Constat dans l'état sauvegardé

- Le début `REFERENCE AND CONTINUITY RULES` existe dans
  `prompt_cookbooks/_blocks/video-preparation/1.0.0/common.system.txt`.
- Les manifests des dernières recettes à deux appels assemblent plusieurs blocs :
  commun, direction de la famille, Plan ou Writer, exemples. L'exemple reçu suit
  cet assemblage ; il n'existe donc pas sous la forme d'un unique fichier source.
- `application/prompt_composition.py::_sequence_request` ajoute encore les règles
  liées à la famille, le format attendu du Writer, les libertés créatives,
  l'audace et la politique de dialogue. Une partie de ce texte est dans Python.
  Le schéma JSON et le contexte de l'appel sont transmis séparément côté user.
- Dans le cas observé, la politique de dialogue est injectée par la liberté
  créative, puis par la politique de l'étape. Les fins des deux blocs diffèrent
  entre décision et conservation. Cela illustre l'intérêt d'une vue assemblée ;
  la refonte de rangement ne doit pas en profiter pour changer ces règles sans
  décision séparée et vérification de l'effet sur les familles.
- Le chargeur `LocalPromptCookbookCatalog` reconstruit `list()` sur le disque,
  et `get(id, version)` parcourt cette liste. Il lit tous les manifests avant de
  retourner une recette : un fichier ancien invalide peut gêner un choix actif.
  Le numéro de version épinglé ne protège pas d'une modification manuelle du
  contenu d'un fichier partagé à cette même version.
- Le rangement historique est surtout un filtre de sélecteur (`lab-core.js`).
  Audit : 78 manifests sous les répertoires de recettes, dont 66 déclarés public,
  2 internes et 10 anciens sans ce champ. Ce n'est pas le nombre de recettes
  visibles simultanément à l'utilisateur. Aucun répertoire physique `_archive`
  n'a été trouvé sous `prompt_cookbooks`.
- Le journal `workspace/llm_calls.json` garde déjà `system_prompt` et `user_prompt`
  exacts, modèles demandés/effectifs et réponse. Le lancement actuel le borne à
  20 appels : c'est un outil de diagnostic, pas une archive durable des versions.

Le mécanisme de fichiers n'a donc pas disparu ; il est dispersé et partiellement
complété par du texte dans le code. Les noms de famille, mode et étape ne suffisent
pas aujourd'hui à trouver rapidement toutes les sources effectives.

## Accès proposé dans l'interface

À côté de la **recette de préparation** : un bouton discret **Consignes LLM**.
Ne pas le placer sous « Prompt utilisé » du rendu, qui désigne le texte H3 final.
Le panneau s'ouvre sur la famille, la version et le mode déjà sélectionnés.

- **Plan / Rédaction**, et Révision au point où elle est utilisée.
- **Fichiers à modifier** : chemins lisibles, accès au dossier ou copie du chemin,
  liste courte des sources de cette étape et identification des blocs partagés.
- **Message assemblé** : texte système complet pour les réglages actuels,
  copier/exporter `.txt` ; section distincte pour contexte user et schéma technique.
- **Échanges du rendu** : copies réellement envoyées, date, étape, modèle et empreinte,
  accessibles après génération et conservées au-delà du journal tournant.
  Ne jamais présenter un assemblage calculé aujourd'hui comme le texte historique.

La prévisualisation utilise le même assemblage que le vrai appel, sans génération
LLM ni modification d'une session. Si le Plan manque, montrer le template et les
variables non résolues ; ne pas prétendre prévisualiser le Writer complet.
Une exportation du message final est une copie de diagnostic, pas la source qui
sera rechargée : l'interface doit distinguer clairement les deux.

## Fichiers de travail et versions conservées

Proposition de rangement logique, à valider avant migration :

```text
prompts/
  actifs/
    classique/    plan.system.txt, writer.system.txt, revision.system.txt, ...
    combat/       plan.system.txt, writer.system.txt, revision.system.txt, ...
    sensuel/      plan.system.txt, writer.system.txt, revision.system.txt, ...
  communs/        blocs neutres à versions exactes
  archives/       recettes et révisions conservées
```

`actifs` contient les véritables sources de travail éditables, pas des exports
inutilisés ni une seconde copie divergente des cookbooks. Un petit registre
explicite relie chaque identifiant/version/mode/étape aux sources ; les données
de contexte restent des variables, pas du texte utilisateur collé dans le système.
Extraire les formulations humaines encore dans Python, en conservant calculs,
validation, schémas et compilation en code.

L'écran proposé enregistre les fichiers et active leur révision, sans redémarrer
le Lab. Si l'alternative d'édition externe est finalement choisie, un bouton
**Actualiser les consignes** pourra valider et capturer les modifications.
Un contenu invalide est signalé ; il n'écrase pas la dernière révision utilisable.
Un seul mécanisme de stockage/activation doit servir ces accès, sans surveillance
permanente de toute l'arborescence nécessaire.

Le paquet de consignes est figé au début d'une préparation : un Plan en cours
et son Writer conservent la même révision, même si un fichier est modifié entre
les deux appels. Les historiques conservent leurs versions ; les nouveaux cycles
adoptent la révision active, même depuis un ancien projet. Le rechargement visuel
d'une page ne déclenche ni préparation ni changement d'un appel enregistré.
Enregistrer l'empreinte du paquet et le texte réellement envoyé avec l'appel
ou sa préparation, avec une référence durable indépendante du journal tournant.

Les blocs communs restent épinglés ; une modification propre à une famille ne
change aucune autre famille. Une amélioration commune passe par une nouvelle
version adoptée explicitement. Les archives conservent les identifiants et toutes
les dépendances transitives nécessaires aux anciennes recettes. Le chargeur
résout directement l'identité demandée, sans parcourir les archives à chaque fois.
Ne pas déplacer les dossiers historiques sans adapter cette résolution.

## Prochaine itération proposée

1. Accès aux sources et au texte assemblé, pour les dernières recettes H3/REF2V
   à deux étapes ; maquette vidéo validée appliquée dans un lot UX distinct.
2. Séparation du travail actif et des archives avec le registre explicite ;
   externalisation du texte système encore en code dans le périmètre retenu.
3. Conservation du texte assemblé à entrées identiques lors de cette migration,
   vérification des anciennes identités, isolation entre familles et cohérence
   de révision Plan/Writer. Tests hors ligne à préparer, exécution par l'utilisateur.

La modification de contenu I2V reste **P1 différée** et l'analyse vidéo adaptative
reste **P2**. Ne pas mêler ce rangement à une nouvelle politique de prompting.
L'extension des mêmes outils à Image Lab et à l'analyse média peut suivre ; ne
pas transformer ce premier périmètre en refonte générale de tous les modules.
