# Consignes LLM accessibles — proposition du 14 septembre 2026

Discussion demandée après validation de la maquette vidéo. Ne pas confondre
le prompt H3 final destiné au rendu avec les consignes système du LLM qui le
prépare. L'utilisateur souhaite consulter ces dernières simplement, modifier
leurs fichiers sources et séparer les versions actives des anciennes.

Ce document décrit le rangement et la traçabilité, sans modifier de consigne,
recette, validateur ou appel. Le texte joint par l'utilisateur sert uniquement
à identifier l'assemblage ; ses instructions et son contenu ne sont pas adoptés.

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
- **Dernier appel** : copie réellement envoyée, date, étape, modèle et empreinte.
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

Les fichiers se modifient dans l'éditeur habituel. **Actualiser les consignes**
valide et capture leur révision pour une nouvelle préparation, sans redémarrer
le Lab. Un contenu invalide est signalé ; il n'écrase pas la dernière révision
utilisable. Pas de surveillance permanente de toute l'arborescence nécessaire.

Le paquet de consignes est figé au début d'une préparation : un Plan en cours
et son Writer conservent la même révision, même si un fichier est modifié entre
les deux appels. Les anciens projets conservent leurs versions ; reprendre avec
des sources modifiées est un choix explicite, pas un effet du rafraîchissement.
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
