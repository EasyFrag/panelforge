# Plan proposé — fidélité, langue et prompts des histoires

Statut : implémenté après validation explicite « va y go », le 27 septembre 2026. Le détail opérationnel, les limites et les vérifications sont dans [Versions d’écriture](../story-writing-editions.md). Les sections ci-dessous conservent le planning validé.

## Objectif

Obtenir une histoire claire et inventive à partir de quelques lignes : conserver la situation demandée, développer une conséquence intéressante et livrer des dialogues utilisables dans la langue choisie. Le rendu réaliste ne doit pas atténuer automatiquement le comique ou la mauvaise foi.

Base sauvegardée avant ce plan : commit `c78e8e309c4e3cd73ca06b1c7228de26ab865d7b`, tag `snapshot-pre-story-fidelity-2026-09-27`. Version locale ; publication non effectuée. Les documents de ce planning sont postérieurs à la version.

## 1. Rendre la relecture fidèle à la demande originale

Constat : `unit_requirements.required_on_screen` vient des événements choisis par le concepteur. Le lecteur peut valider une dérive déjà introduite dans le plan.

Prévoir deux sources distinctes : ce que l'auteur demande réellement et ce que la conception a choisi pour le mettre en scène. La seconde ne remplace pas la première. Un passage source de l'auteur reste identifiable ; ne pas transformer des inventions du concepteur en obligations d'auteur.

- Pour une histoire autonome d'une seule unité, transmettre l'intention originale pertinente et les choix explicites, séparément des preuves attendues du plan.
- Pour plusieurs unités, transmettre seulement les contraintes d'auteur applicables à l'unité relue. Prévoir une projection liée au texte source et à l'unité dans la conception existante, sans appel supplémentaire. Ne pas simplement renommer le contrat actuel généré par le modèle en « intention originale ».
- La projection multi-unité est le point technique à traiter soigneusement : référence au texte source vérifiable, périmètre valide, aucune exigence de révélation prématurée. Une contrainte ambiguë ne devient pas un blocage automatique. Les tests devront vérifier la couverture des demandes réservées aux unités suivantes.
- Le lecteur doit toujours justifier ce qui est compris par une parole ou une action présente dans les scènes ; les consignes ne constituent jamais la preuve qu'un événement a été montré.

Ne pas transmettre en bloc la bible et les secrets futurs. Une omission ou contradiction explicite peut bloquer ; « je préférerais une autre chute » reste une remarque.

## 2. Corriger la mauvaise langue parlée

Constat : deux répliques hybrides de La Coupe Demandée ont été détectées puis classées comme simples avertissements.

Distinguer explicitement dans la relecture le défaut de langue d'une préférence stylistique. Une réplique contenant des propositions involontairement dans une autre langue doit être localisée et corrigée. S'appuyer sur l'analyse du lecteur existant, avec une catégorie de défaut reconnue par le contrat et le traitement des corrections ; ne pas rendre bloquant le seul comptage heuristique de mots anglais.

Conserver noms propres, anglicismes usuels, argot, citations et passages bilingues voulus. Les répliques exactes demandées par l'auteur gardent leur priorité : une contradiction entre cette demande et la langue générale appelle une explication, pas une réécriture silencieuse.

Réutiliser une seule correction ciblée, puis la relecture existante. Préserver faits, locuteurs, intention et registre. Si le défaut reste présent après la limite existante, montrer la réplique et une action claire ; ne pas afficher « prêt » ni lancer une boucle illimitée.

## 3. Donner plus de responsabilité créative au concepteur

Ajuster les consignes de conception, de rédaction et du profil comédie pour qu'elles se complètent :

- inventer une évolution et un aboutissement local, même avec une idée très courte ;
- maintenir le ressort de départ et distinguer la croyance des personnages de ce que voit le public ;
- une résolution conclut le conflit, sans imposer amélioration objective, réconciliation, morale ou punition ;
- une fin ouverte peut conclure un mouvement dramatique tout en réservant la suite ;
- le registre visuel réaliste concerne l'image et n'impose pas une intrigue sage.

Aucun scénario-type, mot cru obligatoire, gag préfabriqué ou exemple de réplique injecté dans les prompts. Le coiffeur et le colis servent de cas d'évaluation hors prompts, pas de patrons à reproduire. La faiblesse subjective d'un gag ne devient pas un nouveau motif de correction automatique.

## 4. Alléger les prompts sans perdre leurs garanties

Dédupliquer les preuves déjà présentes dans `selected_unit` et `unit_requirements` côté rédaction. Chaque rôle reçoit une seule représentation utile ; le lecteur conserve les exigences dont il a besoin.

Réduire les consignes de format répétées qui sont déjà clairement portées par le schéma. Conserver le schéma JSON, les IDs autorisés, les contrats de connaissance et les contrôles qui ont corrigé les erreurs précédentes.

Alléger `visual_state_review` uniquement là où plusieurs champs expriment la même chose. Préserver l'identité, les états acquis, la scène de transition et les changements physiques durables. Aucun changement de logique de création ou d'affectation des variantes dans ce patch.

Mesurer les caractères/tokens d'entrée avant et après ; le gain de temps ou de raisonnement reste à confirmer sur de nouveaux essais. Ne pas réduire le budget de sortie pour forcer artificiellement une réponse courte.

## Parcours et compatibilité

Trois appels habituels pour une unité : conception, écriture, relecture. Une erreur avérée peut ajouter la correction ciblée et sa vérification ; aucun nouvel appel systématique. Les suggestions de style et estimations de durée restent informatives.

Un seul nouveau choix est proposé par le dernier alignement : la version d'écriture, à côté de Mes histoires (voir complément ci-dessous). Aucun autre réglage utilisateur ajouté. Le patch concerne l'écriture ; Références, Scènes, Multilangue, miniatures et génération vidéo ne sont pas remaniés. Les histoires existantes, leurs validations et leurs médias ne sont pas migrés ou régénérés automatiquement. Versionner les consignes et les éventuels contrats nouveaux en préservant les anciens snapshots et empreintes.

## Ordre du travail après validation

1. Ajouter la source d'auteur à la relecture et le traitement explicite du défaut de langue, avec compatibilité des contrats.
2. Réviser les consignes de progression et de fin, sans exemples d'intrigue.
3. Dédupliquer le contexte et les consignes mesurés, puis vérifier que les garanties utiles restent disponibles à chaque rôle.
4. Préparer les régressions ciblées : mauvaise langue, emprunt autorisé, réplique exacte, limite de correction, suggestion non bloquante, intention source distincte du plan, secret réservé à une unité future, lecture des anciens projets et continuité visuelle préservée.
5. L'utilisateur exécute les tests locaux puis compare de nouveaux essais sur les mêmes intentions et réglages. Regarder fidélité, lisibilité du mensonge, conséquence, naturel/langue des dialogues, nombre d'appels et durée. Un troisième sujet inédit permet de vérifier que le moteur n'apprend pas seulement les deux cas d'audit.

La comparaison Qwen seul / Qwen avec Gemma rédacteur viendrait ensuite, à réglages identiques, si les défauts persistent. Elle n'est pas une condition préalable et aucun changement de modèle par défaut n'est proposé ici.

## Validation de cette préparation

Sauvegarde Git vérifiée avec un index temporaire ; branche active, HEAD et index habituel conservés. Aucun code applicatif, réglage, scénario ou média modifié. Aucun test, appel LLM, rendu ou redémarrage lancé.


## Complément proposé — versions d'écriture sélectionnables

Demande utilisateur : conserver la version actuelle appréciée et sélectionner des versions historiques de prompts dans l'en-tête, à côté de Mes histoires. La dernière expérimentale doit être le choix initial. Alignement seulement ; aucune implémentation dans ce tour.

### Présentation

Un sélecteur « Version d'écriture » à côté de « Mes histoires », distinct du choix de modèle Qwen/Gemma. Exemple après le prochain patch : « Dernière expérimentale — v2 » et « Référence du 27 septembre — v1 ». Ces noms v1/v2 sont des libellés UX proposés, pas les numéros actuels de contrats ou de recettes. Une courte information donne date et principales différences ; pas d'éditeur de prompts ni longue liste de réglages.

La référence actuelle correspond au snapshot local c78e8e309c4e3cd73ca06b1c7228de26ab865d7b, déjà créé. Elle reste accessible après les évolutions. Le mot référence désigne une base de comparaison, pas une qualification de stabilité ou de tests.

### Comportement proposé

- Nouvelle histoire : dernière expérimentale présélectionnée. À la création, résoudre cet alias vers une version concrète et enregistrer son identifiant et son empreinte. L'ajout d'une nouvelle expérimentale ne déplace pas automatiquement les projets existants.
- Réouverture : afficher et utiliser la version enregistrée du projet. Cette exception au défaut « dernière » protège les histoires en cours ; elle est proposée explicitement à l'utilisateur.
- Changement volontaire de sélection : affecter les prochains appels explicitement lancés par l'utilisateur. Aucun appel, réécriture ou régénération au simple changement. L'historique doit distinguer la version utilisée pour chaque résultat de celle choisie pour le prochain travail.
- Traitement ou chaîne automatique en cours : version fixe jusqu'à la fin ou à l'arrêt de la chaîne ; changement indisponible pendant cette période. Ne pas mélanger rédaction et relecture de versions différentes lors d'une même chaîne. Une relance destinée à récupérer un appel interrompu conserve le paquet d'origine ; adopter une autre version relève d'une nouvelle opération explicite.
- Continuer l'histoire existante conserve sa version ; un nouvel épisode créé comme nouveau projet suit la règle de nouvelle création et affiche le choix avant lancement. Le transfert de personnages et d'état narratif reste indépendant de la version d'écriture.
- La sélection s'applique à l'ensemble cohérent de l'écriture longue (conception, rédaction, relecture, correction et conversation concernée), pas aux prompts image/vidéo ni au choix du modèle. Éviter d'afficher une promesse globale si un chat utilise encore des consignes en dur ; inventorier ces chemins avant d'implémenter.

### Garantir un vrai retour arrière éditorial

Lecture du code : `LongStoryRecipes.snapshot()` fournit les textes, profils et une empreinte ; `Stories.start()` le recharge à chaque appel. La révision 8 est un indicateur de capacités, pas un identifiant unique de chaque édition des textes. L'empreinte et les traces aident au diagnostic, mais il n'existe pas encore de catalogue de versions sélectionnables et figées par projet.

Créer un petit catalogue explicite de paquets immuables, avec ID, libellé, date, résumé, empreinte et compatibilité des contrats. Commencer par la version actuelle et la prochaine expérimentale. Ne pas proposer arbitrairement tous les commits Git comme des moteurs chargeables.

Archiver les consignes complètes et versionner les comportements éditoriaux nécessaires : projection du contexte, politique de relecture/correction et contrat compatible. Les futures améliorations de fidélité/langue ne doivent pas modifier silencieusement le comportement de la référence. Les correctifs techniques communs à l'application restent possibles ; ce sélecteur ne rembobine pas toute l'application.

Pour les projets anciens, retrouver une version uniquement lorsqu'une empreinte/sauvegarde correspondante est connue. Ne pas présenter « révision 8 » comme preuve suffisante et ne pas remplacer une version inconnue par la dernière en silence. Ce cas devra être affiché explicitement et traité sans altérer les textes sauvegardés.

Même version d'écriture ne signifie pas sortie textuelle identique : modèle, réglages et génération peuvent varier. Sauvegarder les consignes permet de comparer les éditions du moteur dans des conditions identifiées.

### Ordre et validation

Étape préalable au patch qualité : figer la référence actuelle, ajouter catalogue/sélection et attacher les versions aux projets et chaînes. Ensuite seulement créer la prochaine expérimentale et y appliquer les quatre axes du planning.

Préparer des tests ciblés : dernière version par défaut sur création, réouverture fidèle, absence d'appel au changement, impossibilité de basculer en cours de chaîne, reprise avec la version initiale, compatibilité des anciennes empreintes, archivage immuable et identification réelle des consignes dans les traces. Les tests et essais LLM restent à lancer par l'utilisateur selon les consignes du projet.
