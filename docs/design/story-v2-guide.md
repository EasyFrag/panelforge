# Histoire V2 — préparation jusqu’à l’usine

Mise à jour du 4 octobre 2026. Implémentation locale dans `D:/Code/panelforge-krea2-flux`, à charger au prochain démarrage normal du backend, puis actualiser le navigateur. Aucun service redémarré, aucun appel LLM ni rendu de qualification lancé pendant cette livraison.

Le snapshot GitHub précédant la création initiale de V2 reste le commit [d40dc0038697cfb6ffdc6169c49e045233c7afa3](https://github.com/EasyFrag/panelforge/commit/d40dc0038697cfb6ffdc6169c49e045233c7afa3), branche `snapshots/pre-story-v2-2026-09-29`, tag `snapshot-pre-story-v2-2026-09-29`. La sauvegarde précédant V2.1 est publiée sur master : [30453c4](https://github.com/EasyFrag/panelforge/commit/30453c4f346667b6c560c00293ba8715c16519c7), tag `snapshot-pre-story-v21-2026-10-01`. Le patch V2.1 décrit ici reste local.

## Version d’écriture

Le sélecteur en haut du formulaire propose **V2 — Actuelle** et **V2.1 — Dialogues denses**. Une nouvelle histoire démarre sur V2.1 ; les autres derniers réglages restent mémorisés, notamment les 8 secondes si elles ont été choisies. La version reste attachée à cette histoire et à chaque cycle d’écriture ; le sélecteur est verrouillé après création. Pour comparer, créer une autre histoire avec la même idée et choisir V2 avant de lancer. Une histoire ancienne sans ce champ est lue comme V2, sans migration des fichiers ni modification des références existantes.

V2.1 travaille les conversations dès l’écriture : échanges continus entre clips, réactions utiles et conséquences compréhensibles. Pour une scène surtout dialoguée, le repère souple est 2 à 2,75 mots/s, soit 16–22 mots en 8 s ; une action ou un silence important peut justifier moins. Le plafond existant de six répliques et 3,5 mots/s reste vérifié. La durée choisie et le total restent contrôlés, sans accélération forcée ni chevauchement demandé.

La retouche Gemma reste optionnelle au même endroit. En V2.1, elle peut scinder/regrouper des répliques et ajouter de courtes réponses dans l’échange existant, en préservant les événements, informations, secrets et la fin. La réponse contient les répliques structurées, avec locuteur, mode vocal et destinataires. Les contrôles conservent les scènes, durées, rôles parlants et modes vocaux ; un personnage silencieux ne reçoit pas spontanément de dialogue. La cohérence de sens reste une consigne éditoriale, pas une garantie du validateur. Le contrôle final reste optionnel et les nombres d’appels habituels ne changent pas.

Les références V2.1 utilisent un catalogue `visual_states`, vide par défaut, uniquement pour les changements matériels nécessaires de tenue, cheveux ou apparence physique. Les scènes désignent ces états par `state_id` ; une liste vide réutilise la base. Le texte d’état est résolu depuis le catalogue, jamais repris d’une indication libre par scène. Un même état partage une image ; les doublons exacts normalisés et les répétitions de la base sont éliminés. Émotions, regards, poses, voix et silences restent du jeu, sans catégorie de variante dédiée. Les objets non liés à une scène ne créent plus de référence ; l’auteur réserve le catalogue aux objets distinctifs nécessaires.

Les prompts V2 historiques restent séparés et inchangés. V2.1 utilise ses propres consignes d’écriture/relecture/retouche et son contrat ; l’export de production et les services image/vidéo partagés restent utilisés. Aucun appel LLM supplémentaire ni changement du prompteur vidéo. L’automatique s’arrête toujours dans Préparation.

Tests de régression préparés : `tests/test_story_v21.py`, plus assertions dans le test navigateur existant. **Non exécutés** selon AGENTS.md. Commande utilisateur : `python -m unittest discover -s tests -p "test_story_v2*.py"` depuis le checkout actif, avec son environnement habituel.

## Ton du scénario

Dans **Idée et réglages**, un seul sélecteur **Ton** propose **Selon l’idée** et **Sketch provocateur**. Selon l’idée conserve les consignes antérieures, sans profil imposé. Le dernier choix est mémorisé avec les autres réglages et enregistré dans chaque histoire ; ouvrir une ancienne histoire ne lui applique pas le choix d’une autre. Le profil est utilisable avec V2 et V2.1, sans nouvelle version à sélectionner.

Sketch provocateur demande une accroche dans les premières secondes, une situation compréhensible, des réactions excessives, des voix distinctes, de la mauvaise foi et un langage franchement cru. En français, il vise une oralité jeune de quartier sans lexique imposé ni répétition obligatoire. Le scénariste peut inventer des détails et amplifier les situations autour de l’idée, en respectant les événements et la fin explicitement demandés. La fin peut être une chute, une décision de vengeance ou un cliffhanger fort préparé par le récit ; aucun réglage de fin supplémentaire.

La retouche conserve le mordant et les intentions comiques en clarifiant les formulations. La relecture juge la compréhension et la fidélité sans exiger un langage poli, une morale ou une résolution fermée. Les règles de durée, de paroles distinctes, de destinataires et de références restent celles de la version choisie. Modèles, options de retouche/contrôle et nombre d’appels restent inchangés. Le profil ne touche pas le prompteur vidéo.

Le choix est figé pendant un cycle actif. Une modification après écriture est enregistrée sans réécrire automatiquement les scènes : utiliser **Retravailler** avec un retour pour appliquer la nouvelle direction au scénario. L’historique conserve le ton ; restaurer une version ancienne sans ce champ rétablit Selon l’idée. Les traces d’appel identifient le profil et sa politique `+sketch-1.0.0`. Le ton seul ne recrée pas les références d’un scénario inchangé.

Si le navigateur charge le nouveau formulaire avant le prochain démarrage du backend, le sélecteur reste désactivé et son champ n’est pas envoyé à l’ancienne API. Après chargement du backend mis à jour puis actualisation du navigateur, il devient disponible. Aucun service n’est redémarré par ce patch.

Régressions préparées dans `tests/test_story_v2_tone.py` et le scénario navigateur existant, **non exécutées** selon AGENTS.md. Les assertions vérifient la persistance, les anciens projets/clients, la restauration, les cinq appels maximum avec correction et contrôle, l’arrêt en Préparation et les identités de production conservées. La qualité comique et orale reste à qualifier sur un nouveau scénario généré par l’utilisateur.

## Parcours

Histoires seules pour commencer. Une idée, un univers, un style visuel, une durée visée de 10 à 180 secondes et une durée par scène de 10 secondes par défaut. Le lecteur affiche un résumé de deux phrases maximum, puis une phrase d’action, une phrase d’intention et les dialogues de chaque séquence. Retouches directes et retours de réécriture restent disponibles.

- **Manuel** : écrire et relire, corriger, valider le scénario, puis générer sa sélection. La première image réussie est retenue automatiquement ; les variantes sélectionnées démarrent dès que leur référence d’identité est disponible, puis la miniature quand ses sources sont prêtes. Aucun clic de validation intermédiaire. Le parcours s’arrête après le lot pour revoir les images et retoucher celles qui le nécessitent. Le bouton **Envoyer en préparation** dépose les scènes dans l’usine.
- **Automatique** : écrire et relire, générer et retenir les références, préparer les états modifiés et la miniature, puis déposer les scènes dans le bac **Préparation**. Le parcours s’arrête là.

**Aucun Plan ni prompt vidéo n’est rédigé dans Histoire V2. Aucune vidéo n’y est lancée.** Ces étapes commencent lors du lancement explicite dans l’usine. L’envoi transmet les intentions, dialogues, références et réglages ; même un nouvel envoi écarte les anciens résultats de Plan/Prompt et les anciennes sessions de rendu. Les rendus ultérieurs restent consultables depuis la vue Vidéos.

Le choix automatique d’une image n’est pas une validation esthétique. En cas d’échec, la reprise est explicite et ciblée. Une pause suspend l’enchaînement ; les travaux déjà soumis aux ateliers continuent. La reprise attend un lot encore actif au lieu de le recréer. Avant un nouveau lot, elle récupère les résultats liés aux demandes MiniMax/Qwen déjà enregistrées, même si le crash a précédé la confirmation de mise en file. Un rendu terminé ou encore en cours est réutilisé si ses sources et sa demande correspondent ; seuls les éléments manquants ou échoués sont relancés. Les sorties récupérées sont ajoutées aux images de la fiche existante. Un choix manuel ultérieur est conservé. Après un redémarrage, un parcours interrompu demande une reprise explicite.

## Réglages compacts

**Univers** et **Style visuel** sont des menus déroulants. Univers propose Fruits anthropomorphes et Humains · France contemporaine ; Style propose Animation 3D expressive et Cinéma réaliste. Les fruits reprennent la description adultes avec bras, jambes, vêtements et visages expressifs ; la 3D reprend les couleurs vives. Les deux choix restent indépendants et mémorisés avec les autres réglages. **Personnalisé…** révèle un champ uniquement si nécessaire. Toute ancienne description hors des choix proposés est affichée comme personnalisée et conservée exactement ; les valeurs envoyées à l’écriture restent les textes existants, sans nouveau champ ni migration backend. Ctrl+F5 suffit à charger ce changement d’interface.

Le bloc **Réglages** contient quatre sous-blocs repliables : **Idée et réglages**, **Réglages Dialogues**, **Réglages Image + miniature**, **Réglages Vidéo**. Le bouton principal reste accessible lorsque les réglages sont repliés. Les derniers choix sont repris pour l’histoire suivante, avec une idée vide et V2.1 sélectionnée par défaut. La mise à jour des valeurs de départ du 29 septembre reprend une fois les choix image/vidéo enregistrés côté serveur et conserve les choix narratifs du cache précédent ; les changements suivants restent mémorisés. Les choix enregistrés sont persistés côté serveur ; les modifications du formulaire sont aussi mémorisées dans ce navigateur.

### Images

| Réglage initial | Valeur |
| --- | --- |
| Assistance | V6 · directions modulaires |
| Inspirations locales | Désactivées |
| Preset personnel | Bananita fresh |
| Langue des prompts image | English |
| Direction artistique | Aucune, choix disponible |
| Prompteur image | Unsloth Gemma 4 31B QAT |
| Workflow | KREA2 + Flux Klein |
| Checkpoint | Kroma (`Krea2/kroma-v0.3-turbo.safetensors`) |
| Format / résolution | 9:16 / 2,1 MP |
| Finition | Finition 4 steps · 8 + 4 (`finish_4`) |
| LoRA image | Sélection simple, aucune par défaut |
| Variantes et miniature | MiniMax Image Edit, Qwen disponible |
| Prompteur d’édition | Unsloth Gemma 4 31B QAT |
| Miniature | Activée, désactivable |

Le preset personnel applique les réglages qu’il contient ; un ancien preset sans workflow n’en invente pas un. Les choix restent modifiables après application. La direction artistique utilise le catalogue partagé et exige V6. Le preset Bananita fresh est référencé par son identifiant stable `style-642721e10d124d5a83ad6bb907ef8fd3`. Le checkpoint Kroma et les autres valeurs de la capture sont des valeurs de départ explicites ; les histoires déjà enregistrées gardent leurs réglages.

La langue des prompts image est indépendante de la langue parlée des dialogues. MiniMax/Qwen utilisent le même choix de moteur et de prompteur pour les variantes et la miniature, avec des projets distincts ouvrables dans les ateliers existants.

### Vidéo

| Réglage initial | Valeur |
| --- | --- |
| Plan / rédaction du prompt | Qwen3.8-27B / Gemma 4 31B QAT |
| Nombre de plans | Auto |
| Audace / vie / caméra / mouvements / dialogues | 3 / 3 / 3 / 3 / 1 |
| Recette | BUNNY 0.1.3 + VAE int8 (`0.1.3+vae-int8-convrot.1`) |
| Preset | Rapide · 9 / 4 / 5 |
| Format | 9:16 |
| MP initiaux / finaux | 0,9 / 0,9 |
| Durée | Celle de chaque séquence |
| Seed | Automatique, distinct par séquence ; valeur explicite possible |
| Musique | OFF |
| LoRA | Motion_Repair, 0,6 puis 0,2 |
| DLSS | Activé après le rendu dans l’usine |

Recette, checkpoint, preset, format, résolution, musique et LoRA sont modifiables avec les composants partagés. Liberté créative et réglages avancés sont repliés. Spectrum est indisponible avec BUNNY. Les réglages sont transmis à Préparation sans appel des modèles vidéo.

## Références, états et miniature

Les fiches sont visibles et ouvrables dès la validation du scénario, avant toute génération. Description, import, sélection et agrandissement sont disponibles. Ouvrir une fiche ne lance rien.

En V2 historique, une apparence temporaire explicite crée une référence dérivée attachée uniquement à sa séquence. En V2.1, seuls les états matériels du catalogue décrits plus haut déclenchent une variante. Deux états identiques d’un même personnage partagent une variante ; deux états différents repartent de l’identité stable. Une grossesse ne se propage donc pas implicitement après la naissance. Sélectionner une variante prépare aussi son identité si elle manque. Régénérer une identité inclut ses variantes déjà préparées ; un ancien état issu d’une autre image d’identité bloque l’envoi tant qu’il n’est pas corrigé.

La miniature est une composition à partir des images retenues. Le prompteur reçoit un choix de références séparées, avec des rôles explicites : jusqu’à neuf images pour MiniMax et seize pour Qwen, priorité aux personnages puis au décor et aux accessoires. En un seul appel, il choisit les références utiles à une situation lisible et cite uniquement celles-ci. L’application transmet cette sélection au rendu et renumérote ensemble images et labels. Chaque image effectivement envoyée doit toujours être citée ; les labels inconnus sont refusés. Cette sélection est réservée aux miniatures Histoire V2, sans modifier le contrat des variantes ou des retouches ordinaires. Le contexte initial et la réponse brute restent conservés, séparément du contexte de rendu sélectionné. Le workflow versionné MiniMax conserve ces entrées multiples ; aucun collage préalable. Une miniature peut être refaite seule depuis sa carte. Si elle est activée, son absence bloque l’envoi. Les formats de miniature sont ceux communs aux moteurs : 1:1, 3:2, 2:3, 3:4, 16:9 et 9:16.

Les projets dérivés et leurs commandes ont des identifiants stables pour éviter les doublons après une réponse perdue. Une reprise d’erreur peut relancer simultanément la miniature et les variantes en échec sans reprendre les images réussies ou les références manuelles non sélectionnées. Les appels de prompteur des images dérivées sont espacés par le suivi et passent par les services coordonnés existants ; les rendus utilisent leurs files habituelles.

## Cohérence narrative et consignes

L’écriture éditoriale reste indépendante (`story.v2.*@1.2.0`). L’auteur écrit, le relecteur vérifie la compréhension et l’auteur effectue au plus une correction ciblée. La première relecture reste systématique.

**Retouche légère optionnelle**, désactivée par défaut dans Réglages Dialogues : troisième modèle indépendant, Gemma 4 Unsloth proposé. Elle intervient après la première relecture et la correction éventuelle. Le modèle reçoit l’histoire complète. En V2 historique, sa réponse peut modifier uniquement la phrase d’action et le texte des tours de parole existants ; personnages, locuteurs, ordre, présences, apparences, intentions et durées restent identiques. En V2.1, le nombre et l’ordre des tours peuvent évoluer dans les limites décrites dans Version d’écriture. Les consignes demandent de conserver toutes les informations, les événements et la fin. Ces contraintes structurelles ne garantissent pas à elles seules la qualité du style ni la préservation sémantique.

**Ajouter une étape de contrôle final** : case sous le modèle **Relecture**, décochée par défaut. Elle est indépendante de la retouche et utilise le modèle de relecture. Le dernier choix est mémorisé pour les histoires suivantes. Cochée, elle contrôle la version corrigée ou retouchée et, après retouche, compare aussi les scènes avant/après. Si le texte n’a nécessité ni correction ni retouche, la première relecture suffit et n’est pas doublée. Décochée, la dernière version est utilisée directement ; les validations techniques restent actives.

| Options | Sans correction de fond | Avec correction de fond |
| --- | --- | --- |
| Sans retouche, contrôle final désactivé | 2 appels | 3 appels |
| Sans retouche, contrôle final activé | 2 appels | 4 appels |
| Avec retouche, contrôle final désactivé | 3 appels | 4 appels |
| Avec retouche, contrôle final activé | 4 appels | 5 appels |

Aucune boucle automatique après le contrôle final. S’il est activé et signale encore des problèmes, le parcours automatique s’arrête au scénario, avec les remarques et le statut **À relire**. S’il est désactivé, le parcours continue après la correction/retouche : les anciennes remarques restent dans le journal d’appels mais ne sont pas affichées comme un avis sur la version modifiée. En automatique, la suite reste références, états modifiés et miniature selon les options, puis dépôt dans Préparation. Aucun Plan, prompt ou rendu vidéo n’est lancé par Histoire.

Les versions **A · avant retouche** et **B · après retouche** du même scénario sont conservées dans **Versions du scénario**, sans refaire l’écriture pour comparer ces deux versions. Un clic sur une version la restaure dans le lecteur et invalide l’approbation précédente ; la version quittée reste également sauvegardée. En automatique, l’option de retouche activée utilise B, après le contrôle final seulement si celui-ci est coché. Une retouche invalide laisse A intacte et demande une reprise explicite.

Un ancien cycle déjà commencé avant l’ajout de la case conserve son contrôle planifié à la reprise ; les nouvelles histoires et les prochains cycles utilisent le choix enregistré. Aucun projet runtime n’est réécrit au déploiement.

**Durée par scène** : choix 5 à 15 secondes, proposé à 10. Le découpage est calculé avant l’écriture, contraint dans le schéma et validé avant l’export : 60 s à 10 s donnent six scènes de 10 s, jamais cinq de 12 s. La durée totale est exacte ; si elle n’est pas un multiple, la fin s’ajuste dans les limites de 5–15 s (26 s à 10 s : 10/10/6 ; 61 s : 10/10/10/10/10/6/5). Le plafond existant de 18 scènes est conservé : une combinaison incompatible est refusée avant tout appel, sans raccourcir la durée demandée. Les répliques doivent rester jouables (3,5 mots/s maximum), les informations sont redistribuées sans ajouter des scènes de remplissage.

Les anciens projets sans durée par scène restent en **Ancien découpage · libre** ; ouvrir ou restaurer une histoire ne redécoupe rien. Choisir une durée différente puis enregistrer conserve le texte et indique qu’il faut **Actualiser le découpage**. Cette action explicite relance l’écriture selon la nouvelle cible. La préparation est bloquée tant que le scénario ne respecte pas cette cible. Les durées validées deviennent les durées des scènes et des rendus dans Préparation.

**Suivi compact** : `Appel 3/4 · Retouche des dialogues · Gemma 4 · 00:24`. Le total dépend des deux options et s’ajuste si une correction est nécessaire. Le timer mesure le temps écoulé de l’appel, attente comprise ; il continue entre les rafraîchissements et se fige à la fin ou à l’interruption. Appel courant, étape suivante et résultats acceptés sont persistés ; une pause/reprise ne refait pas les étapes terminées. Après redémarrage, reprise explicite. Les réessais demandés après erreur sont comptés comme de nouveaux appels et peuvent dépasser le nombre du parcours normal.

Présence et parole restent distinctes : un personnage silencieux reste une référence de la scène ; une voix absente doit être explicitement hors champ. Les états sont limités aux séquences concernées. Neuf références maximum par clip. La relecture reconstruit la compréhension à partir des actions visibles et paroles, sans s’appuyer sur le résumé ou les intentions privées comme preuves.


La consigne V2 transmise à l’usine conserve relations, événements, causalité et répliques. La mise en scène peut être enrichie selon les niveaux choisis. Le niveau dialogues 1 autorise les réactions sans ajouter de paroles ; les niveaux supérieurs restent modifiables. La consigne sonore suit le choix musique. Cela évite d’opposer une interdiction générale d’enrichissement aux curseurs créatifs réglés à 3. Les prompts historiques de saga ne sont pas ajoutés à l’auteur V2.

## Persistance et qualification

Journal atomique sous `workspace/stories_v2/`, préférences séparées, versions de mutation et export d’épisode déterministe. Les anciennes images et les versions déjà envoyées ne sont pas supprimées. Une modification de scénario invalide l’approbation ; des références ne sont réutilisées que si leur identité, description, style et réglages visuels correspondent. L’usine reçoit un instantané et conserve sa propre responsabilité de lancement.

Contrôles réalisés sur ce patch : compilation Python, imports des modules, compilation JavaScript sans exécution, analyse CSS, unicité des IDs HTML et correspondance des sélecteurs, revue visuelle du formulaire statique et diff ciblé. Les résultats détaillés et sauvegardes se trouvent dans `D:/Code/panelforge/.agent/diagnostics/story-v2-preparation-20260929/`.

**Tests fonctionnels non exécutés**, conformément à AGENTS.md. Trente cas préparés dans les trois modules initiaux : contrat narratif, modes, reprise, préférences, variantes, vrais contrats multi-images avec clients simulés, absence de lancement usine, et parcours navigateur simulé. Aucun gain de qualité ou de performance audiovisuelle n’est annoncé comme mesuré. Huit cas supplémentaires dans `tests.test_story_thumbnail_references` couvrent le passage de neuf candidates à quatre images, les labels invalides, Qwen, le maintien des contrats ordinaires, les changements concurrents et la récupération d’un prompt interrompu sans rendu automatique. Contrôle statique du correctif : quatre Python compilés sans exécution ; pas de génération de qualification.

À exécuter par l’utilisateur depuis le checkout actif :

```powershell
$env:PYTHONPATH = 'D:\Code\panelforge-krea2-flux\src'
& 'D:\Code\panelforge\.venv\Scripts\python.exe' -m unittest tests.test_story_v2 tests.test_story_v2_preparation tests.test_story_v2_browser tests.test_story_thumbnail_references tests.test_story_v2_editorial
```

Puis les régressions existantes pertinentes : épisodes, KREA assisté, Qwen/MiniMax Edit, usine et navigation, ou `python -m unittest discover -s tests`.

Après le démarrage normal choisi par l’utilisateur et Ctrl+F5, qualifier une histoire courte avec un état modifié et plusieurs personnages : contrôler la lecture, les présences silencieuses, le retour à l’état de base, la miniature, puis vérifier dans Préparation que Plan et Prompt restent à faire. Les critères narratifs restent la clarté des relations, de l’annonce, de l’ellipse, de la naissance et de la conséquence. Le rendu réel MiniMax multi-images et la qualité audiovisuelle restent à évaluer sur ce parcours.

Pour le blocage MiniMax « usage de chaque référence » rencontré sur **La mèche verte**, charger le correctif au prochain redémarrage normal du backend puis relancer uniquement la miniature depuis sa carte. L’ancien échec et les images déjà retenues ne sont pas réécrits par le patch. La reprise de l’histoire reste également ciblée sur les travaux manquants ou échoués.

## Qualification du parcours éditorial du 29 septembre

Implémentation locale, chargée au prochain redémarrage habituel du backend, puis Ctrl+F5. Aucun service redémarré pour ce patch et aucune histoire runtime réécrite.

Quinze nouveaux tests dans `tests.test_story_v2_editorial` : durées exactes et reliquats, limites de scènes, modèles indépendants, parcours 2/4/5 appels, contrôle avant/après, historique A/B, blocage après relecture défavorable, maintien de la production en Préparation, contraintes de retouche, pauses/reprises, résultat accepté récupéré après interruption, compteur par cycle, changement de durée et anciennes histoires. Le scénario navigateur existant couvre aussi l’option, le modèle indépendant et le timer. **Tests non exécutés** suivant AGENTS.md ; aucun appel LLM ni rendu de qualification.

Sauvegardes, diff isolé et contrôles statiques : `D:/Code/panelforge/.agent/diagnostics/story-v2-polish-timing-20260929/`. Huit Python compilés, cinq modules importés, JavaScript compilé sans invocation, IDs et sélecteurs contrôlés. Pour qualifier manuellement : nouvelle histoire 60 s / 10 s, retouche activée, comparer A/B et vérifier la compréhension, puis contrôler que le mode automatique s’arrête dans le bac Préparation.

## Option de contrôle final

Ajout local du 29 septembre, domaine1.3.0 et cache UI control1. Cinq tests supplémentaires préparés dans `test_story_v2_editorial` (vingt au total) : huit combinaisons d’options/correction jusqu’à Préparation, préférences indépendantes, rejet technique malgré contrôle désactivé, pause/reprise sans contrôle et reprise d’un contrôle ancien déjà planifié. Les tests de blocage sur problème existants choisissent explicitement le contrôle activé. Le scénario navigateur couvre emplacement, défaut décoché, sauvegarde, indépendance et mémorisation.

Tests non exécutés selon AGENTS.md. Contrôles de syntaxe, imports et liens HTML uniquement ; aucun appel LLM, génération ou redémarrage. Sauvegardes, diff et contrôles : `D:/Code/panelforge/.agent/diagnostics/story-v2-final-control-20260929/`.


## Enchaînement des références sans validation intermédiaire

Correctif du 29 septembre limité à l’orchestration Histoire V2. Les modèles, prompts, réglages, interface et transfert usine restent inchangés. Neuf tests ciblés ajoutés dans `tests.test_story_v2_preparation` : lot manuel complet, reprise MiniMax et Qwen après accusé perdu, rendu encore actif, reprise sélective des échecs, refus d’un rendu sans lien explicite, retouche demandée, maintien des choix manuels, changement de source et arrêt avant usine. Tests préparés, non exécutés selon AGENTS.md.

La récupération se fonde sur les liens de projet/message existants et sur l’identifiant exact de requête du rendu. Elle ne parcourt pas les anciens projets pour rattacher des essais dont le lien a déjà été remplacé avant ce correctif. Ces anciens essais restent dans l’atelier ; aucune migration de l’histoire en cours n’est exécutée pendant l’implémentation.

Sauvegardes et vérifications statiques : `D:/Code/panelforge/.agent/diagnostics/story-v2-reference-chaining-20260929/`. Charger le code au prochain redémarrage habituel choisi par l’utilisateur, puis reprendre explicitement un lot interrompu. Aucun service redémarré et aucune génération de vérification lancée.


## Destinataires et regards dans Histoire V2

Patch du 30 septembre, contrat Histoire 1.4.0 / consignes éditoriales 1.2.0. L'auteur identifie automatiquement les destinataires de chaque réplique avec `addressee_ids` : il s'agit des personnes auxquelles on parle, pas de celles citées dans la phrase. Un destinataire peut rester hors champ ou être à distance ; cela ne crée ni présence ni référence supplémentaire. Narration, pensée, monologue et public non identifié gardent une liste vide.

`address_cue` reste vide par défaut. Lorsque l'échange risque d'être mal compris (tiers, interlocuteur hors champ, POV déjà prévu), l'auteur peut ajouter une seule indication visible courte et compatible avec l'action. Pas de nouvelle commande de caméra ni de regard imposé à chaque réplique. La retouche Gemma conserve les destinataires et le sens de cette indication ; le relecteur reçoit uniquement le geste visible, sans prendre les identifiants des destinataires comme preuve d'une relation comprise par le public.

L'export ajoute à l'intention de la scène une courte ligne par réplique adressée, sans recopier le dialogue, puis une indication de rythme laissant place à toutes les réponses. Le Plan et le prompteur vidéo conservent leurs consignes, modèles, schémas, paramètres et responsabilité de découpage. Aucun appel LLM ajouté. Le parcours automatique reste références puis bac Préparation.

Aucun affichage ou réglage supplémentaire. L'éditeur conserve les indications cachées pour une réplique inchangée ; une modification du texte, du locuteur ou du mode de parole les retire pour éviter une consigne devenue fausse. Une modification manuelle d'action, d'intention ou de lieu retire le seul geste associé. Une réécriture demandée à Histoire peut établir de nouvelles indications. Les histoires existantes sans ces champs restent valides et leur empreinte reste stable ; aucun enrichissement ni changement d'un prompt déjà envoyé n'est exécuté au chargement.

Qualification : sept régressions ciblées préparées dans `tests.test_story_v2_addressing`, scénario navigateur étendu pour conservation/invalidation des données cachées et absence d'affichage supplémentaire. Tests non exécutés conformément à AGENTS.md. Aucun rendu ou appel réel de qualification. La précision des regards reste à évaluer lors d'une prochaine génération utilisateur : il s'agit d'une meilleure intention transmise, pas d'un contrôle garanti du rendu.
