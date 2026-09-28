# Versions d’écriture des histoires — 27 septembre 2026

## Utilisation

Dans Histoires, le sélecteur **Version d’écriture** se trouve à côté de **Mes histoires**. L’information ⓘ décrit la version. Le choix des modèles Qwen/Gemma reste indépendant.

- Nouvelle histoire : **Dernière · Expérimentale · v2** est sélectionnée. Son identifiant concret est enregistré dès la création.
- **Référence du 27 septembre · v1** conserve les consignes et la politique éditoriale antérieures, issues du point de sauvegarde local `c78e8e3`.
- Réouvrir une histoire conserve sa sélection. Changer de version enregistre uniquement une préférence pour les prochains appels explicitement lancés ; aucun scénario, média ou validation existante n'est réécrit ou invalidé.
- Le sélecteur est indisponible pendant une chaîne. Une reprise d'appel interrompu exige sa version d'origine. Pour un nouvel essai sous une autre version, sélectionner celle-ci puis lancer une nouvelle opération ; le brouillon original reste disponible.
- Les résultats, appels et brouillons archivés portent leur version d'origine. L'interface distingue le texte actuel du choix pour les prochains appels.
- Une suite créée comme nouveau projet propose également la dernière version, modifiable dans sa préparation. Continuer une unité prévue dans la même histoire conserve la version de cette histoire. Le chat de préparation reçoit lui aussi ses consignes archivées.

Pour une histoire ancienne, seule une empreinte connue permet une association automatique. Le seul numéro technique de révision 8 ne suffit pas. Une histoire sans correspondance reste lisible et demande un choix explicite pour ses prochains appels ; aucun remplacement silencieux de ses prompts.

## Expérimentale v2

1. Le relecteur distingue la demande originale des événements inventés par la conception. Pour une seule unité, il reçoit l'intention source ; pour plusieurs unités, la conception répartit des citations exactes de l'auteur entre les unités concernées. Leur appartenance au texte source et leurs identifiants sont vérifiés. Les secrets de la bible restent absents de la vue spectateur. Les citations pertinentes et la répartition sémantique restent une responsabilité du modèle, à vérifier sur des essais multi-épisodes.
2. Une réplique involontairement dans la mauvaise langue devient un défaut de livraison. Le lecteur doit fournir sa citation complète et la scène réelle ; une citation inventée n'est pas acceptée comme preuve. Le système réutilise la correction ciblée existante puis sa vérification, avec une seule tentative automatique. Les répliques exactes de l'auteur ne sont pas traduites silencieusement. Les emprunts, noms et passages bilingues voulus sont explicitement permis dans les consignes.
3. La conception doit inventer une progression et un aboutissement local en conservant le ressort de départ. Résolution n'impose ni réparation objective, réconciliation, morale ou punition. Le rendu réaliste n'impose pas une intrigue sage. Aucun exemple de scénario ou vocabulaire imposé n'est ajouté.
4. La rédaction reçoit une seule copie des preuves d'événements. La relecture reçoit un état visuel unique quand début et fin sont identiques, et conserve les deux lors d'une transformation. Les registres, identités, états acquis et contrats JSON restent disponibles.

Trois appels habituels pour une unité avec la direction d'écriture actuelle. Une correction nécessaire ajoute son appel et la relecture existante ; la limite n'est pas augmentée. Les préférences de style et estimations de durée restent informatives. Aucun gain de temps ou de qualité n'est encore mesuré sur une nouvelle génération.

Références, fabrication des scènes, Multilangue et miniatures ne sont pas remaniés. Les anciens contrats visuels restent lus avec leur format ; aucun média ni projet runtime n'a été migré pendant le patch.

## Archivage technique

Le catalogue explicite se trouve dans `prompt_sources/story.long/2.0.0/editions/catalog.json`. Deux paquets JSON contiennent les consignes, profils, constantes visuelles et prompt du chat de suite. Chaque entrée possède ID, date, libellé, résumé, empreinte éditoriale et SHA-256 du fichier. Un paquet publié ne doit plus être modifié : une évolution devient une nouvelle entrée, puis la cible `latest` est mise à jour.

La politique 1 garde les comportements précédents ; la politique 2 active fidélité, langue et compaction. La politique réellement utilisée est inscrite dans chaque job, distincte de la préférence choisie pour l'avenir. Les anciens brouillons sans cette nouvelle métadonnée restent sous leur politique d'origine.

Les sources mutables historiques restent disponibles pour les anciens outils, mais les nouvelles opérations du mode histoire résolvent le catalogue. Le versionnement porte sur l'écriture, pas sur un retour à une ancienne application entière ni sur la garantie de textes identiques d'un essai à l'autre.

## Vérification effectuée

Contrôles statiques uniquement : syntaxe Python, compilation V8 des sources JavaScript et fragments de fixture sans les exécuter, IDs HTML uniques, JSON et SHA du catalogue, comparaison des prompts de référence avec le snapshot Git, contrôle des espaces du diff. Aucun test fonctionnel ni appel LLM ou rendu lancé ; aucun service redémarré.

## Tests à lancer par l'utilisateur

Depuis `D:\Code\panelforge-krea2-flux` :

```powershell
D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_story_editions tests.test_story_editions_browser tests.test_story_quality_policy tests.test_story_tone tests.test_story_followup
```

Les nouveaux tests couvrent versions immuables, défaut à la création, réouverture, changement sans génération, verrouillage d'une chaîne, empreinte historique inconnue, reprise, récupération d'un ancien brouillon, attribution des contraintes par unité, langue et répliques exactes, limite d'une correction, API, suite et interface.

Au prochain rechargement habituel du backend, recharger l'interface avec Ctrl+F5. Pour comparer, créer deux essais avec la même intention et les mêmes modèles/réglages, l'un en référence et l'autre en expérimentale. Vérifier fidélité, progression, fin et langue avant de comparer le temps. Essayer ensuite un sujet inédit.

## Correctif technique des citations mono-unité

Le contrôle d'attribution est limité aux histoires de plusieurs unités, comme le prévoient les consignes v2. Avec une seule unité, le brief original est utilisé directement et le schéma ne demande aucune recopie. Un ancien brouillon expérimental contenant ce champ redondant peut être revalidé localement si le document source est toujours identique et si les autres contrôles passent. Le brut est conservé ; la normalisation est signalée.

Ce correctif du schéma et de la compatibilité n'altère aucun paquet de prompts archivé et ne crée pas de nouvelle édition d'écriture. Les citations multi-unités restent exactes et rattachées à une unité existante. Les régressions dédiées sont dans tests/test_story_author_requirements.py, à exécuter par l'utilisateur.
