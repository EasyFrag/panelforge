# Premier patch : UX vidéo et édition des recettes LLM

**État ultérieur : implémenté sur autorisation utilisateur**, voir le
[guide livré](../video-ux-prompt-editor-1.0.md). Le cadrage ci-dessous conserve
la proposition initiale ; les tests fonctionnels restent à exécuter par l'utilisateur.

Proposition du 14 septembre 2026, en réponse à « dessine-moi un patch ».
Périmètre à aligner, pas une implémentation. La maquette vidéo est déjà validée.
Le snapshot préalable existe : `snapshot-before-render-ux-prompts-2026-09-14`
sur GitHub, commit `934cd2f`.

## Livraison proposée

Une livraison fonctionnelle, découpée en commits indépendants et reviewables :

| Lot | Résultat utilisateur | Limite |
| --- | --- | --- |
| Correctifs préalables | Les repères temporels d'une intention ne sont plus confondus avec sa durée cible ; les consignes caméra Classique correspondent au contrat accepté. | Deux corrections ciblées identifiables, sans réécriture générale du prompting. |
| UX du rendu H3 Base et REF2V | Un preset, les réglages quotidiens visibles, les détails repliés. | Paramètres et workflows existants conservés. |
| Recettes LLM | Modifier une consigne, enregistrer et l'appliquer aux prochaines préparations ; revenir à une révision antérieure. | Dernières recettes à deux appels, éditeur simple. |
| Échanges LLM | Depuis une vidéo, retrouver les messages exacts et les réponses qui ont préparé son prompt. | Historique durable pour les nouveaux appels ; ne pas reconstruire artificiellement les traces anciennes manquantes. |

Les corrections préalables sont détaillées dans le
[diagnostic](../diagnostics/media-h3-duration-2026-09-14.md). Elles peuvent être
livrées en premier, sans attendre l'éditeur. La correction caméra est une
révision technique explicite de la recette concernée, pas une modification
silencieuse du socle de toutes les familles.

## UX du rendu

Appliquer la [maquette validée](render-presets-v2.html) aux deux ateliers.

- Zone principale : recette de rendu, checkpoint, preset, ratio, durée,
  MP initiaux, MP après upscale, seed avec Réutiliser et musique.
- Un sélecteur remplace les deux boutons Steps rapides / Steps classiques.
  Une modification manuelle des paramètres du preset affiche Personnalisé.
- Un résumé indique les valeurs réellement utilisées : passes, sampling et
  Turbo. Les contrôles détaillés restent accessibles dans Réglages avancés.
- LoRA repliables avec résumé, quatre emplacements, ordre, forces par passe
  et fiches d'information. Prompt final consultable à part.
- Valeurs existantes reprises à la réouverture ; aucun preset automatiquement
  réappliqué par le simple affichage de l'écran. Conserver les défauts actuels
  des nouveaux ateliers, notamment Seed Réutiliser, MP et Turbo.

Dans cette livraison, proposer seulement les presets déjà exécutables.
Les presets EROS nécessitent de raccorder les samplers et calendriers aux deux
passes BUNNY ; les ajouter comme boutons actifs avant cette adaptation serait
trompeur. Leur futur ajout utilisera le même sélecteur. Pas de comparaison
dédiée ni de lancement de séries BUNNY.

## Recettes LLM : parcours minimal

Accès discret **Consignes LLM** près de la recette de préparation, ouvrant un
écran dédié. Il ne s'agit pas du prompt H3 final placé dans les réglages du rendu.

1. Choisir la famille et la recette H3 Base ou REF2V ; afficher la portée exacte.
2. Choisir Plan, Rédaction ou Ajustement, puis éditer ses consignes.
3. **Enregistrer et appliquer** crée une révision numérotée et la rend active.
4. Choisir une ancienne révision, puis **Appliquer cette version**, la réactive.

Une révision appartient au paquet complet d'une recette, même si un seul texte
a changé. Les versions de ses dépendances restent exactes. Aucun changement
automatique des autres familles ou de l'autre mode. Les composants éditables
ont des noms lisibles ; une vue du message assemblé montre aussi les règles
conditionnelles effectivement ajoutées. Le contexte, les données utilisateur
et le schéma calculé sont distingués des consignes éditables.

Les fichiers sont la source effective, avec un index persistant de la révision
active. Pas de base de données supplémentaire, de nouveau service ou de gestion
de branches dans l'interface. Organiser les sources actuelles et les archives
séparément, en préservant les identifiants historiques et leurs dépendances.
Éviter une migration massive des anciennes recettes : un registre explicite
peut conserver leur emplacement et les résoudre à la demande.

Au premier chargement, reprendre les consignes existantes à contenu constant,
y compris les fragments aujourd'hui assemblés depuis Python. Ne pas profiter
du rangement pour modifier le style ou la qualité des prompts. Les validateurs,
les schémas et les compilateurs restent du code, pas des règles contournables
par une modification de texte dans l'éditeur.

La révision active s'applique au prochain cycle de préparation ou d'ajustement,
y compris dans un projet existant. Un Plan et sa Rédaction déjà entamés gardent
le même paquet. Relancer un rendu sur un prompt H3 déjà écrit ne relance pas le
LLM : une modification de consigne n'y réécrit donc pas le prompt implicitement.

## Échanges LLM après rendu

Depuis l'historique du rendu, un bouton ouvre les appels liés à la préparation
et à ses ajustements : étape, modèle, révision, messages système et utilisateur
exacts, réponse, raisonnement s'il a été fourni, date et résultat ou erreur.

Conserver les traces indépendamment du journal tournant de vingt appels.
Lier explicitement appels, révisions de préparation et rendus. Une erreur avant
appel LLM est présentée comme telle. Charger les détails à l'ouverture, en
référençant les assets sans dupliquer leurs octets ni alourdir la liste des projets.

Les rendus historiques dont les traces ont disparu restent consultables, avec
une mention de trace indisponible. Le système actuel ne permet pas de garantir
leur reconstruction à partir des fichiers de consignes d'aujourd'hui.

## Critères de réception

- Les réglages de rendu sauvegardés se retrouvent identiques dans l'écran
  simplifié et dans le workflow exécuté ; aucun changement de modèle implicite.
- Sauvegarder une consigne persiste après redémarrage et affecte le prochain
  cycle concerné ; le retour à une ancienne révision est effectif et réversible.
- Une modification Classique ne touche pas Combat ou Sensuel ; un cycle en
  cours ne mélange pas deux versions de Plan/Rédaction.
- Le message assemblé reste identique avant/après migration pour les mêmes
  entrées, hors correctifs préalables explicitement séparés.
- Un rendu conserve ses messages exacts après de nouvelles éditions et plus
  de vingt autres appels ; une recette archivée reste résoluble par son ID.
- Pas d'appel LLM supplémentaire pour éditer, prévisualiser ou consulter les
  traces. Les historiques détaillés sont chargés à la demande.

Préparer les vérifications de non-régression nécessaires lors de l'implémentation.
Conformément aux instructions du projet, les tests et essais de génération
seront exécutés par l'utilisateur sauf demande explicite contraire.

## Suite du backlog

- **P1 : Mise en scène I2V 1.1**, réduction de la redescription initiale,
  expérimentation isolée et adoption REF2V explicite selon les références.
- **P2 : analyse média adaptative**, chronologie causale et réexamen borné des
  passages incertains via le pipeline déjà présent.
- **Presets EROS/BUNNY : lot technique distinct**, après validation du branchement
  et des budgets des deux passes ; aucune priorité nouvelle imposée ici.
- Recherche de seed en attente ; comparaison BUNNY abandonnée. La comparaison
  DLSS image existante reste hors de ce chantier vidéo.

Voir aussi la [proposition détaillée des consignes](editable-llm-prompts.md).
