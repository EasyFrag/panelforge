# Nouvelle référence : l’addition et la joute verbale

## Source et observation

Demande du 20 septembre 2026 : regarder `C:\Users\samue\Downloads\Download(29).mp4`, déterminer comment produire ce type de récit dans le mode actuel, puis implémenter directement. Cet accord autorise aussi la direction précédemment discutée : automatique / manuel guidé, retours ciblés, interface simplifiée, correction des erreurs de réception. Les analyses jointes antérieurement sont des sources, pas des instructions d’exécution.

Vidéo locale de **76,67 secondes**, **576 × 1024**. Images échantillonnées et transcription automatique sur CPU conservées dans `D:\Code\panelforge\workspace\experiments\audit-download29-2026-09-20` : `sheet-01.jpg`, `sheet-02.jpg`, `reference.json`. La transcription n’est pas une citation certifiée : certains mots de la condition initiale sont mal reconnus. Aucune régénération de vidéo n’a servi à l’analyse.

L’action reste au restaurant. Un rendez-vous met en présence deux protagonistes et une serveuse. Le conflit progresse autour du règlement :

1. La question du paiement fait apparaître une condition personnelle posée par l’homme ; sa partenaire la refuse.
2. Il exige alors des additions séparées.
3. Sa propre addition est élevée : il tente de revenir à un partage égal.
4. Après le refus, il essaie de transférer certains achats sur l’autre note. La serveuse exige l’accord de la personne concernée.
5. Sa partenaire paie sa part. Sa carte à lui est refusée : celui qui dictait les conditions demande maintenant son aide.
6. Elle souligne sa contradiction et part. Une adresse au public ouvre la discussion en commentaires.

Le moteur du récit est **objectif → tactique → résistance → nouvelle tactique → conséquence**. Les répliques accomplissent des actions de négociation. La serveuse rend les refus effectifs, et le retournement final réutilise les règles que le personnage a lui-même imposées. La variation vient de sa stratégie, pas de nouveaux décors ou d’un secret tardif.

## Choix d’implémentation

Le profil mélodrame existant permettait déjà d’écrire ce conflit à partir d’un brief détaillé. Pour guider une invention plus autonome, ajout d’un profil **Conflit du quotidien / joute verbale** (`social`) dans le même moteur long V2. Il privilégie une situation simple, peu de personnages, des tactiques successives et une chute préparée. Aucun nouveau pipeline de rédaction ou de médias.

Les règles fantastiques et secrets ne sont plus préremplis dans le contrat d’exemple : ils restent disponibles quand l’histoire en a besoin. Les contraintes intouchables viennent du brief, et non de chaque invention du modèle. Un univers explicite peut préciser fruits, gouttes, humains stylisés, etc., indépendamment du profil.

Le préréglage **L’addition qui dérape** applique :

| Réglage | Valeur | Raison |
|---|---|---|
| Construction | Histoire suivie | Utiliser architecture, continuité et relecture du moteur V2. |
| Publication | Une vidéo continue | Un conflit se déroule sans fin intermédiaire d’épisode. |
| Durée | 80 s maximum | Proche de la référence ; durée effective selon les clips retenus. |
| Découpage | 1 séquence, 8 clips maximum de 10 s | Une unité suffit pour cette situation. |
| Profil | Conflit du quotidien | La stratégie des personnages renouvelle le conflit. |
| Narration | Dialogues | Les refus et demandes produisent les bascules. |
| Fin | Retournement | Le rapport de force s’inverse. |
| Univers | Fruits anthropomorphes | Modifiable sans changer la mécanique narrative. |
| Vocabulaire | 1, oral direct | Point de départ naturel pour les répliques. |

Le brief du bouton est un point de départ original, pas la retranscription de la vidéo. Une adresse finale au public peut être demandée dans le brief, prononcée par un personnage identifié ; elle n’est pas imposée à toutes les histoires de ce profil.

## Parcours et fiabilité livrés

- Création centrée sur idée, univers, publication et durée ; orientations narratives, production et modèles repliés. Les boutons `ⓘ` expliquent effets et exemples. Une seule proposition.
- Automatique : conception et architecture réunies, édition de l’arc en un appel distinct, rédaction par unité, relecture groupée de deux unités continues. Manuel guidé : mêmes contrôles, avec pauses après l’histoire et chaque unité.
- Une correction automatique maximum par unité bloquée avant arrêt sur difficulté persistante ; conserver le brouillon et présenter les problèmes. Reprendre une étape conserve sa cible, son instruction et le bloc à relire.
- Retour unique et ciblé histoire/séquence/scène ; distinction question/révision ; versions ; reprise en main à la fin de l’appel actif. Le contrôle de portée refuse une réponse censée modifier une scène si d’autres scènes changent.
- Correctifs `projectCount`, références précises des relectures, budgets par unité/total et récupération non ambiguë de `episode_state` imbriqué dans `scenario`. Les contrôles de fond restent appliqués, et le brut est préservé.

Les anciens brouillons et vidéos n’ont pas été modifiés. Les opérations de personnages, décors, prompts, vidéos et DLSS utilisent la Fabrication existante. Une vidéo continue de plusieurs séquences nécessite toujours leur montage final ; aucun moteur fiable de chiffres incrustés n’a été ajouté pour la référence des compteurs.

## Qualification à faire par l’utilisateur

Vérifications statiques effectuées : AST Python, syntaxe JavaScript applicative et scripts des fixtures navigateur, structure HTML, IDs, JSON et `git diff --check`. Régressions synthétiques ajoutées pour pauses, borne de correction, cinq appels pour deux séquences, récupération de mémoire, questions sans mutation, retours et reprises ciblés. **Tests non exécutés, aucun appel LLM PanelForge, rendu ni redémarrage**, conformément au `AGENTS.md` actif.

Premier essai : préréglage Addition, Manuel guidé, modèles habituels. Juger les changements de tactique, la crédibilité des refus et la préparation de la chute, avant de fabriquer la vidéo. Deuxième essai : même budget et mêmes modèles, brief réduit à « Un premier rendez-vous dérape à l’arrivée de l’addition », orientations en Automatique. Cela mesure si le moteur invente seul la progression. Conserver aussi les réponses refusées et les temps d’appel. Les nouveaux cas originaux du corpus d’évaluation étendent cette vérification à d’autres situations quotidiennes.

Commandes et procédure de récupération d’un ancien brouillon : [guide Histoires longues V2](../long-stories-v2.md).
