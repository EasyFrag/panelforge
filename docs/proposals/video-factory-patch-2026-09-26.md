# Usine — patch proposé après les premiers essais, 26 septembre 2026

Statut : implémenté localement le 26 septembre 2026 après autorisation utilisateur. Aucun traitement en cours modifié, test exécuté, appel LLM/rendu ou redémarrage. Les constats ci-dessous conservent le cadrage ; voir aussi le guide `docs/video-factory.md` pour la mise en service.

## 1. Fin de vidéo et refroidissement — correctif prioritaire

Constat utilisateur : vidéo disponible mais étape Vidéo et ligne encore « En cours », alors que le serveur affiche son refroidissement.

Lecture du code : l’adaptateur usine appelle `execute_attempt` de manière synchrone ; ce dernier enregistre le rendu réussi, puis attend `cooldown_while_owned` avant de rendre la main. L’usine enregistre seulement ensuite la réussite de son étape. Ce couplage explique le décalage visible. Au moment de la lecture, les deux lignes désert et métro sont désormais `succeeded` dans le journal, avec sorties vidéo ; DLSS et IG étaient désactivés. Il ne s’agit donc pas de deux rendus toujours bloqués.

Comportement proposé :
- Vidéo réussie dès que sa sortie a été récupérée, validée et enregistrée. Le cooldown appartient à la machine, pas à la vidéo terminée.
- Si aucune étape ne reste, la ligne passe en Résultats pendant le cooldown. Sinon Vidéo est cochée, avec l’étape suivante clairement indiquée.
- Le serveur conserve son délai et ses protections thermiques avant toute nouvelle vidéo. Le travail local admissible peut avancer pendant ce temps, selon ses propres ressources et protections.
- Garder la reprise après interruption et la réconciliation des identifiants existants ; ne jamais relancer un rendu uniquement pour rafraîchir son statut.
- Vérifier séparément l’affichage « récupération/import » et la fin réelle ; un fichier simplement visible dans Comfy ne suffit pas à déclarer la réussite.

## 2. Preview uniquement en fabrication manuelle

Demande utilisateur : désactiver le nœud de preview dans l’usine et dans le batch Histoires, y compris le batch lancé directement depuis Histoires ; conserver son usage dans H3 Base et REF2V manuels.

BUNNY possède déjà `preview_enabled`, qui contrôle réellement l’insertion des nœuds. Il était vrai dans les deux essais usine lus. L’application doit fixer le contexte d’exécution batch sans modifier les réglages du parcours manuel d’origine ; couvrir aussi les autres recettes supportées via leurs manifestes versionnés.

Conserver la vidéo finale, son lecteur dans les résultats, les keyframes nécessaires au texte IG et la progression textuelle. Ne pas confondre suppression du calcul de preview et masquage de l’aperçu dans le navigateur. Aucun gain chiffré ou identité pixel à pixel revendiqués sans mesure.

## 3. Résultats utilisables et rangement

Demandes déjà exprimées : dossiers locaux `Petits hommes/date`, `Histoire/date`, `Levres/date` ; lien depuis les résultats, prioritairement vers le DLSS.

Proposition :
- Actions directes « Ouvrir le dossier », « Copier le chemin », « Télécharger la vidéo », avec la version DLSS en évidence si disponible.
- Ouvrir le dossier local réel via le Lab local ; ne pas reposer sur un lien navigateur file://. Depuis un autre poste, distinguer le dossier de la machine du Lab et proposer copie du chemin / téléchargement sans annoncer un dossier local au navigateur distant.
- Conserver la famille de classement quand un réglage fait passer le preset en Personnalisé ; les scènes issues d’une histoire restent sous Histoire. Une source sans famille connue est classée sous Autres.
- Date proposée précédemment : date locale de disponibilité de la vidéo finale (DLSS si activé), figée pour le résultat. Vidéo et texte doivent rester associés même si leurs étapes finissent de part et d’autre de minuit.
- Noms lisibles, même radical pour vidéo/texte et identifiant court pour éviter les collisions ; histoire/épisode/scène dans le nom si applicable.
- Le classement local et l’éventuelle copie serveur sont distincts. Préserver les références aux médias existants ; pas de déplacement rétroactif de la bibliothèque dans ce patch sans demande.
- Échec d’écriture/copie : signaler précisément l’export à reprendre, sans refaire la vidéo ou le texte déjà produits.

### Texte Instagram

Actuellement conservé dans les projets Social Lab et dans le résultat d’étape usine ; le détail usine permet d’ouvrir Texte IG. Cet atelier a déjà « Tout copier ». L’affichage usine ne reprend pas le champ `emojis` séparé, uniquement hook/caption/hashtags.

Proposition : les deux accès, sans choix exclusif.
- Trois variantes consultables dans le détail du résultat ; bouton Copier sur chaque variante, directement dans l’usine.
- La copie contient accroche, légende, emojis et hashtags avec leurs sauts de ligne, sans titres techniques « variante 1 ».
- Un fichier `<nom>_Instagram.txt` à côté de `<nom>_DLSS.mp4`, contenant les trois variantes clairement séparées et la langue. Téléchargement du TXT également depuis l’interface.
- Texte brut Unicode / UTF-8 : accents, emojis composites et retours à la ligne conservés de bout en bout. Reprendre le contenu intégral, pas seulement le champ caption ; vérifier que les emojis déjà intégrés ne sont pas ajoutés une seconde fois.
- Si DLSS échoue ou est désactivé, le texte reste consultable/copiable/téléchargeable depuis l’application. Les reprises d’export ne nécessitent pas un nouvel appel LLM.

## 4. Petits hommes — créativité à guider dès le Plan

Retour utilisateur : première vidéo trop littérale, pas d’objet extérieur. Dans le plan désert enregistré, le modèle écrit explicitement que la main est le seul élément ajouté et ne modifie ni le désert ni le chameau ; son action consiste à relever un homme. Dans le second plan il déplace l’eau avec ses doigts. Ces observations concernent les plans lus, pas une évaluation visuelle des vidéos par l’agent.

Conséquence : une simple invitation à être inventif dans le rédacteur final serait trop tardive. Le Plan doit recevoir l’autorisation et l’objectif d’inventer un moyen d’intervention. Le rédacteur conserve ensuite cette solution. Garder le pipeline existant de deux appels dans une première itération.

Direction retenue pour la nouvelle intention par défaut : une main apporte normalement un objet, outil ou matériau extérieur au décor, choisi librement pour résoudre le problème visible. Un objet familier à échelle humaine devient monumental pour les petits hommes. Une intervention principale, un effet visible causé par cette intervention, puis réaction/remerciement ; rester lisible dans un plan de huit secondes.

- Pas de catalogue fermé d’objets ni de correspondance rigide sécheresse=bouteille / incendie=douche.
- Quelques exemples courts montrent des mécanismes variés (apporter une ressource, dissiper un phénomène, réparer/dégager), sans devoir les recopier. Choisir de préférence des générations validées par l’utilisateur.
- Historiques retrouvés : bouteille/glace puis verdure, pommeau de douche contre incendie, retrait d’un rocher. Ce dernier illustre le dégagement, pas encore un exemple validé de réparation.
- L’image ancre le départ, l’identité et les proportions ; l’intention autorise explicitement l’arrivée d’un accessoire et les changements nécessaires au résultat. Ne pas laisser les invariants figer le problème à résoudre.
- Conserver un niveau de variété évalué sur plusieurs images ; aucun prompt ne garantit à lui seul l’inventivité ou l’adhésion vidéo. Envisager une courte étape d’idéation supplémentaire seulement si ce guidage reste insuffisant, car elle ajoute du temps au batch.
- Accessoire extérieur attendu dans l’intention par défaut, avec choix libre de l’objet. L’intention reste éditable et prioritaire ; aucune contrainte cachée n’est ajoutée au rédacteur.
- Anomalie secondaire relevée dans le plan métro : `thank you` étiqueté French. Verrouiller la langue anglaise de cette réplique si conservée ; cette langue est indépendante de celle du texte IG.

## 5. Défauts et validation future

Demande confirmée dans la discussion précédente : Petits hommes active DLSS et Texte IG par défaut ; IG anglais, Gemma 4 local, trois variantes, options désactivables. Appliquer aux nouvelles préparations / applications explicites du preset, sans réécrire les essais en cours.

Périmètre implémenté : statut/cooldown, preview batch, accès et exports des résultats, défauts et guidage Petits hommes, suppression multiple. Les nouveaux défauts ne sont pas appliqués rétroactivement aux lignes déjà préparées.

À vérifier lors de l’implémentation autorisée : succès pendant cooldown sans nouvelle admission serveur ; résultat accessible après rafraîchissement/reprise sans doublon ; graphes batch sans preview et manuels conservés ; exports Unicode/association/collisions/reprise ; qualité créative sur plusieurs intentions avec l’utilisateur. Aucun test ni appel LLM/rendu n’a été exécuté pendant ce cadrage.

## 6. Préparation — supprimer la sélection en masse

Dernière demande utilisateur : ajouter « Supprimer la sélection (N) » à la barre d’actions de Préparation, à côté des autres actions de lot. Bouton désactivé sans sélection ; toutes les lignes cochées peuvent être retirées en une action, y compris via Tout sélectionner.

Le retrait porte sur les entrées de l’usine uniquement ; images, projets sources et médias restent conservés. Les lignes déjà en production utilisent les commandes d’annulation existantes. La suppression unitaire et l’action serveur multiple `remove` existent déjà ; le bouton de lot manque dans l’interface. Conserver la validation de l’état Préparation au moment de l’action, pour ne pas retirer silencieusement une ligne lancée entre-temps.

Bouton implémenté avec compteur et désactivation sans sélection. Les brouillons des lignes supprimées ne nécessitent pas de sauvegarde. Aucun élément réel de la file n’a été supprimé pendant l’implémentation.


## Détails de livraison et validation préparée

- Les livraisons usine sont publiées sous `<dlss-output-root>/dlss/<famille>/<date>`. Le fichier Comfy/asset d’origine reste accessible. Le classement crée un lien physique sur le même volume lorsque disponible, sinon une copie atomique ; aucun déplacement rétroactif des médias. Les résultats usine déjà terminés sont publiables au prochain démarrage, sans génération.
- Un worker de fichiers distinct des GPU conserve son état dans le journal usine. Le défaut d’export ne remet pas en échec une vidéo réussie. Reprendre l’export n’effectue aucune génération. Un TXT modifié extérieurement est préservé et signalé.
- `batch_mode` est persisté sur l’essai H3/REF2V, avec valeur false pour les historiques. BUNNY désactive son réglage de preview ; les autres recettes utilisent des liaisons explicites ajoutées à leurs manifestes versionnés, sans changement des graphes manuels ni de leurs empreintes source.
- Vérifications réalisées : AST Python, JSON/manifestes, imports dans le venv du projet, analyse syntaxique JavaScript et `git diff --check`. Tests fonctionnels préparés, non exécutés conformément à AGENTS.md ; aucun appel LLM, rendu ou redémarrage.
- Tests ciblés : `python -m unittest tests.test_video_factory tests.test_video_factory_results tests.test_video_factory_web tests.test_machine_work tests.test_h3_bunny tests.test_h3_render tests.test_episodes tests.test_episode_reference_refresh`.
