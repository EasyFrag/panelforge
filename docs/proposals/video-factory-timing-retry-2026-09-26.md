# Usine : durées, reprise, suppression et versions traduites — 26 septembre 2026

Statut : implémenté localement après autorisation de l’utilisateur. Contrôles
statiques effectués ; tests préparés mais non exécutés. Aucun traitement,
appel LLM, serveur ou suppression réelle lancé par l’agent.

## Durées des étapes

Dans Production et Résultats, chaque badge Plan / Prompt / Vidéo / DLSS /
Texte IG affiche en dessous sa durée en secondes. Le compteur progresse
pendant l’étape, puis se fige après réussite, erreur ou annulation.

- Secondes arrondies ; <1 s pour une durée inférieure à une seconde.
- Rien pour Off, en attente ou sans horodatage disponible, notamment les
  sorties déjà fournies lors de l’envoi.
- Durée de la dernière tentative : la reprise efface les dates de l’étape
  échouée, en conservant les temps des étapes réussies.
- Mesure du temps de l’étape, pas de la durée du clip ni du seul calcul GPU.

## DLSS et reprise unique

La demande d’Incendie France était rejetée avant la création du job DLSS :
identifiant de 89 caractères, limite de 80. L’usine utilise maintenant un
identifiant déterministe de 72 caractères (préfixe + empreinte ligne/tentative).
Le démarrage automatique de Comfy DLSS existait déjà ; ce rejet l’empêchait
d’être atteint. La disponibilité réelle du serveur n’a pas été testée.

Le libellé est toujours **Reprendre la chaîne**, quelle que soit l’erreur.
L’action est accessible sur la ligne, dans la fiche et sur la sélection.
Seules les étapes échouées/annulées repartent ; les réussites sont conservées.
Si seul le rangement des fichiers a échoué, la même action reprend cet export
sans relancer de génération. Les doubles clics et les reprises actives sont
protégés.

## Images agrandissables

Les miniatures de Préparation, Production et Résultats, ainsi que les images
de référence des fiches, s’ouvrent en grand via une loupe +. L’image conserve
ses proportions. Fermeture par croix, Échap ou clic en dehors de la fenêtre.
Le clic sur l’image ne modifie ni la sélection ni les réglages.

## Suppression dans tous les états

Dernière extension utilisateur : **Supprimer** apparaît dans chaque fiche,
y compris en production et pour les résultats réussis, en erreur ou annulés.
La suppression multiple est disponible dans les trois onglets ; les lignes de
Résultats possèdent aussi un accès direct.

- Si aucune étape n’est active, l’entrée disparaît immédiatement de l’usine.
- Pendant une étape active, demander son annulation, afficher Suppression en
  cours et retirer l’entrée après confirmation de l’arrêt. La demande est
  persistée ; les enfants vidéo/DLSS sont réconciliés sans soumission aveugle,
  y compris après redémarrage et lorsque la file est en pause.
- Les callbacks de publication et d’annulation tardifs ne recréent pas la ligne.
- L’épisode source, ses scènes, ses images et ses vidéos restent conservés.
  Il s’agit de supprimer le traitement usine, pas les fichiers.
- Une suppression libère le nouvel envoi de la même scène en Préparation.
  Une ligne encore présente reste protégée contre un envoi identique ; une
  annulation seule ne vaut pas suppression ni reprise automatique.

Le journal lu contenait Le rejet (scène 1) annulée alors que les scènes 2 et 3
étaient présentes. Le contrôle des doublons incluait toutes les lignes, même
annulées. Les notifications d’envoi indiquent maintenant les scènes déjà
présentes avec leur état, en plus du nombre de nouveaux éléments ; accès à
l’usine depuis la notification.

## Histoires : conserver la version linguistique affichée

L’épisode Séance privée — English possède bien trois traductions prêtes.
Les préparations traduites ont un projet de rendu mais aucune session de
rédaction : l’ancienne capture les ignorait et reprenait les entrées originales
en français. Une préparation française avait ainsi été ajoutée à la scène 2.

- La capture reconnaît les préparations localisées et prend le prompt injecté
  du projet de rendu validé. Plan/Prompt sont fournis, sans appel LLM.
- Vérifier que le prompt correspond aux traductions validées et que l’ordre
  des images correspond au projet ; refuser une traduction incomplète ou un
  prompt incohérent avec un message indiquant Multilangue.
- Retrouver la préparation localisée valide même si une ancienne préparation
  usine française a été ajoutée après elle.
- Réutiliser une vidéo existante seulement si son prompt et ses réglages
  correspondent. Le rattachement au bon épisode accepte une préparation
  localisée sans session et conserve son marqueur localized ; un prompt
  français ne peut plus être rattaché à une scène anglaise validée.
- Les trois projets traduits lus contiennent respectivement 2, 3 et 3 répliques
  English, aucune French, avec le bon ordre des images. Aucun fichier runtime
  modifié pour ce diagnostic.

L’erreur JavaScript « view is null » venait du diagnostic Histoires : une vue
absente et un identifiant de séquence absent pouvaient passer un premier test,
puis provoquer un accès à view.kind. L’accès est maintenant protégé.

## Chargement et vérifications utilisateur

Au prochain redémarrage habituel du Lab, recharger avec Ctrl+F5. Cache de
video-factory.js/css et stories.js en 20260926.patch2.

Les lignes déjà envoyées gardent leur préparation actuelle. Pour une ancienne
ligne anglaise préparée en français : Recharger depuis l’histoire si elle est
en Préparation, ou Supprimer puis renvoyer la version English. Les générations
en cours n’ont pas été modifiées automatiquement.

Tests préparés :

```powershell
python -m unittest tests.test_video_factory tests.test_video_factory_timing_retry tests.test_video_factory_results tests.test_video_factory_web tests.test_episode_localization tests.test_stories_browser
```

Contrôles réalisés par l’agent : syntaxe Python, imports, syntaxe JavaScript,
identifiants DOM usine et git diff --check. Aucun test fonctionnel exécuté,
conformément à AGENTS.md. Changements KREA2 de l’autre conversation conservés.
