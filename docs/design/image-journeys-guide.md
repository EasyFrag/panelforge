# Parcours d’images autonome — V1

L’onglet **Parcours d’images autonome** se trouve dans Image Lab, à côté de **Modifier avec Minimax**.
Il construit les états successifs d’un même décor : travaux, aménagement et décoration, à cadrage et point de vue fixes.

## Utilisation

1. Choisir une image, saisir éventuellement une intention et le nombre de **nouvelles images** (5 par défaut, de 1 à 30).
2. Le volet replié **Modèles** permet de choisir séparément **Progression visuelle** et **Prompt MiniMax**.
   Les deux peuvent utiliser le même modèle. Le défaut reprend Gemma local de l’atelier MiniMax.
   Les modèles doivent accepter les images ; le catalogue ne certifie pas cette capacité. Un choix indisponible
   reste affiché et n’est jamais remplacé silencieusement.
3. **Créer la suite** lance le parcours côté serveur. Fermer l’onglet n’arrête pas la génération.
4. La destination tient en une phrase ; les grands jalons restent dans **Étapes prévues**, replié par défaut.
   La frise se remplit automatiquement. Une vignette ouvre l’image, l’action et sa relecture ; prompt et modèles
   sont accessibles dans le détail. Chaque image peut être téléchargée.
5. **Suspendre** laisse finir l’opération déjà engagée. Un rendu en cours est conservé, sans annulation implicite.
   Une fois suspendu, modifier l’intention ou les modèles puis **Reprendre**. Les images produites restent intactes.
6. **Préparer les transitions** transmet les états relus à l’atelier H3. Les intentions vidéo y sont préparées
   et relues avant envoi à l’usine ; ce bouton ne lance aucun appel vidéo ou rendu.

5 nouvelles images donnent 6 images avec le départ et jusqu’à 5 transitions. **Nouveau** ouvre un autre formulaire ;
les parcours existants se retrouvent dans le sélecteur, avec leur avancement.

## Consultation des images

La taille de base des miniatures est triplée : 450 × 330 px dans la frise, 216 × 198 px pour
l’image de départ. Les images conservent leurs proportions et la frise défile horizontalement.
Chaque miniature affiche une loupe et ouvre la vue agrandie, y compris l’image choisie avant
de lancer un parcours. Le survol ou le focus clavier affiche un aperçu ×3, limité à l’écran.
Échap, le défilement et le changement de vue masquent l’aperçu. Ce réglage d’affichage se charge
avec Ctrl+F5, sans redémarrer le Lab.

## Progression et limites

- Le LLM établit le cap et les grands jalons avant la première édition. Sans intention, il propose un chantier
  adapté au décor visible. Les travaux respectent leurs dépendances naturelles, même pour un décor imaginaire.
- Le chemin s’adapte aux résultats réels. L’analyse compare la source et le résultat ; l’image d’origine sert
  aussi d’ancre visuelle pour cette analyse dès la deuxième transformation. Le moteur MiniMax reçoit seulement
  l’état précédent comme référence de rendu ; les pixels d’origine ne sont pas verrouillés. Une synthèse et les
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
  branche de variantes ou geste d’ouvrier n’est ajouté à cette V1.

## Découpage

- `domain/image_journeys.py` : configuration, états, validation des décisions et contrat de séquence v1.
- `application/image_journeys.py` : journal, boucle serveur, pause/reprise, récupération, remise des états relus.
- `application/image_journey_prompting.py` : politique versionnée `image.journey.progression@1.0.0`.
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
python -m unittest discover -s tests -p "test_minimax*.py"
python -m unittest discover -s tests -p "test_navigation_and_resource_preview_browser.py"
python -m unittest discover -s tests -p "test_lab_web.py"
```

Le scénario navigateur nécessite Chromium local ; sinon il est ignoré. La qualification avec les modèles et
MiniMax réels reste à faire par l’utilisateur. Charger le backend au prochain redémarrage normal choisi par
l’utilisateur puis actualiser la page. Aucun service n’a été redémarré par cette implémentation.
