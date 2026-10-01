# Usine à vidéo

Implémentation du 25 septembre 2026 dans le checkout `D:\Code\panelforge-krea2-flux`, branche `feature/video-factory-2026-09-25`.


## Preset Petits hommes — expérimental (30 septembre 2026)

Le preset garde une image de départ et un plan continu de 10 secondes. Une main
géante détourne un objet du quotidien à échelle humaine, monumental pour les
petits hommes, afin de résoudre le problème visible avec une idée surprenante
et compréhensible. Les gestes utiles font progresser la même solution, sans
quota de deux ou trois. Le résultat reste visible après le retrait de la main,
puis les petits hommes remercient ensemble une seule fois.

L’intention courante (v4 interne, même preset) comporte 87 mots. Une courte
consigne liée au besoin s’ajoute lorsqu’il est identifiable : irrigation et
végétation luxuriante pour la sécheresse, interception/déviation pour une vague,
ventouse de débouchage au premier geste d’aide pour une inondation,
flammes vivantes puis extinction
pour un incendie. La ventouse doit évacuer l’eau et abaisser durablement son
niveau ; les gestes suivants restent libres, si nécessaires. Cette contrainte
d’objet ne concerne pas les tsunamis. Tornades et réparations n’ajoutent
aucune consigne ciblée ; le choix de l’objet et des gestes reste libre.

Pour la sécheresse, la consigne demande systématiquement une pousse magique,
immédiate et luxuriante partout où l’eau touche la terre. La végétation suit
la progression de l’arrosage et reste visible après le retrait de la main.
Elle se développe pendant l’irrigation dans les dix secondes du plan.

Le repérage utilise l’intention vidéo et le contexte saisi, puis l’intention
KREA et la description de l’image exacte. Les labels, noms de fichiers et styles
ne servent pas à déterminer le problème. Une vague prime sur l’inondation
qu’elle provoque. Les cas absents ou ambigus sont laissés au Plan visuel,
sans ajouter plusieurs objectifs. Le contexte complet est lu avant réduction.

Le Plan relie besoin, mécanisme et bénéfice durable dans une phrase de
continuity_invariants. Sa consigne courte respecte les outils imposés et laisse
sinon le choix libre ; la matière du décor ne doit pas immobiliser l’eau ou le feu.

### Langues et contexte image

**Langue parlée** propose Auto et les 11 langues stables de H3 : français, anglais,
allemand, italien, espagnol, portugais, russe, chinois, coréen, japonais et arabe.
Un choix manuel prime. Sinon, un pays connu est prioritaire ; les cas ambigus
utilisent les groupes convenus :

| Ambiance | Langues |
| --- | --- |
| Asie de l’Est | Chinois, coréen, japonais |
| Europe occidentale | Français, anglais, allemand |
| Europe du Sud | Italien, espagnol, portugais |
| Péninsule ibérique | Espagnol, portugais |
| Europe générique | Les six langues européennes ci-dessus |
| Europe de l’Est | Russe |
| Ambiance arabe / désert sans pays précis | Arabe |
| Aucun indice | Les 11 langues |

Le portugais correspond notamment au Portugal/Brésil et n’appartient pas au
groupe Europe de l’Est. Un pays explicite prime sur le paysage : un désert
situé aux États-Unis conserve l’anglais.

L’envoi depuis KREA récupère le prompt de **l’essai correspondant exactement
à l’image envoyée**, avec son style. L’intention d’origine, notamment « Pays :
Japon », est récupérée dans le PNG lorsqu’elle est disponible et correspond
au même essai. L’intention actuelle d’un projet modifié ultérieurement ne remplace
pas cette provenance. Pour un PNG importé, la caption ComfyUI ou les métadonnées
de prompt connues fournissent ce contexte sans recherche de projet par fichiers.

La fiche affiche **Contexte récupéré de l’image**. **Lieu / contexte de la scène**
reste éditable pour apporter une précision. Les titres ne sont plus recopiés
automatiquement dans ce champ ; la langue du titre ou du prompt ne prouve aucun
pays. Les anciennes paroles citées dans les métadonnées ne deviennent pas des
répliques imposées.

### Formule de remerciement

Les politiques expérimentales v2, v3 et v4 imposent uniquement la formule minimale de la langue
choisie : Thank you, Merci, 감사합니다, Gracias, ありがとう, Danke, Grazie,
Obrigado, Спасибо, 谢谢 ou شكرا. Le Plan reçoit les mots exacts ; les contrôles
du Plan et du Prompt refusent tout complément (« kind hand », « beaucoup »),
répétition ou autre phrase. Casse et ponctuation peuvent varier ; les marques
vocaliques arabes facultatives sont acceptées.

La v4 conserve cette validation stricte et la transmission vocale courte de la v3. Une langue déjà choisie est transmise
avec sa seule formule minimale. Pour une scène ambiguë, seul le Plan reçoit
les groupes et l’ordre de préférence ; le rédacteur reçoit la langue approuvée
et préserve les paroles, sans refaire le choix.

### Choix conservé et variété

Avant le Plan, l’usine prépare un ordre reproductible propre à la fiche, favorisant
les langues moins présentes parmi les 50 choix expérimentaux récents (y compris
ceux déjà réservés par d’autres préparations). Les égalités sont départagées
par l’identifiant de la fiche. Une langue est fixée immédiatement lorsque le pays
ou le groupe se déduit du contexte textuel.

Si le contexte textuel ne suffit pas, le Plan visuel existant reçoit l’image,
les groupes et cet ordre de préférence. Il doit prendre la première langue
compatible avec le pays ou l’ambiance, ou la première des 11 sans indice.
La compréhension de cette ambiance et le respect de la préférence dans ce cas
restent confiés au modèle du Plan ; le programme contrôle les 11 langues admises
et impose strictement les langues déjà résolues à partir du contexte.

Le Plan enregistre la langue et les mots natifs. Le rédacteur et le rendu
reprennent ce choix. Les reprises et changements de modèle conservent la langue
résolue tant que l’image, le contexte et le choix manuel ne changent pas.
Une nouvelle fiche, y compris une duplication, dispose de son propre tirage.
Modifier la langue ou le contexte en préparation invalide le Plan et le Prompt.
Le texte Instagram reste indépendant.

La politique typée little_men.localized_thanks.v4 distingue les nouvelles
préparations. Les sessions v1/v2/v3 commencées gardent leurs entrées et règles.
Depuis le 30 septembre, les nouvelles sélections fixent aussi la ventouse au
premier geste d’inondation, puis le résultat végétal luxuriant pour la sécheresse.
Les marqueurs correspondants sont conservés entre Plan et Prompt. Les anciennes
sélections v4 sans ces marqueurs conservent leur texte verrouillé ; dupliquer
une ancienne fiche permet d’adopter la
nouvelle consigne dans une nouvelle préparation.
Une nouvelle préparation ou copie remplace uniquement les intentions standard
v2/v3 exactes par la nouvelle intention ; une intention personnalisée reste intacte.
Réappliquer explicitement le preset permet aussi de passer à la v4. Les choix
de langue résolus restent conservés si leurs entrées ne changent pas.

Les métadonnées complètes restent enregistrées et consultables. Le contexte
transmis garde les notes manuelles et l’intention image, dédoublonnées, puis le
prompt image (extrait de 1 200 caractères au-delà de cette taille). Le long style
séparé n’est plus répété si une description existe ; il sert de repli sinon.
Le repérage du pays utilise toujours les données complètes avant cette réduction.
Le Plan reçoit toujours l’image. Hindi reste lisible dans les anciennes sessions v1.

DLSS reste activé. Depuis le 28 septembre, Texte IG est désactivé par défaut
sur Lèvres et Petits hommes, y compris expérimental. Il reste activable dans la
fiche, avec anglais, Gemma 4 et trois variantes préconfigurés.
Les sorties restent dans Petits hommes/date, y compris après personnalisation.
Le preset Petits hommes classique reste à huit secondes avec son remerciement
anglais. Aucun appel LLM supplémentaire, aucune migration des anciennes fiches.

### Vérification et utilisation

Contrôles statiques effectués : AST Python, imports, compilation V8 du JavaScript
et revue des contrats de langue, des entrées historiques et des autres presets.
Les régressions couvrent les requêtes Plan/Prompt, les duplications et un ou quatre gestes. Tests fonctionnels préparés mais non
exécutés conformément à AGENTS.md ; aucun LLM, rendu ou redémarrage lancé.

Au prochain redémarrage habituel du Lab, **Ctrl+F5**, puis appliquer le preset
expérimental en Préparation. Pour un ancien essai, utiliser **Dupliquer** puis
préparer la nouvelle fiche. La langue et le remerciement sont visibles après
le Plan. Cache usine : 20260928.solutions1.

[Direction ciblée v4 et vérifications](proposals/little-men-needs-v4-2026-09-28.md).
[Correctif v3 et comparaison manuelle sur six images](proposals/little-men-solutions-v3-2026-09-28.md).

    python -m unittest tests.test_video_factory_needs tests.test_video_factory_solutions tests.test_video_factory_languages tests.test_video_factory_experimental tests.test_video_factory tests.test_video_factory_patch3 tests.test_video_factory_results tests.test_video_factory_web tests.test_classic_cinematic tests.test_video_preparation_recipes tests.test_vocal_policy tests.test_prompt_composition_storage tests.test_krea2_edit

## Patch du 26 septembre 2026

- **Préparation** : Supprimer la sélection (N) retire les lignes cochées, en conservant les sources et médias. Le bouton est désactivé sans sélection. Les brouillons des lignes supprimées ne sont pas enregistrés.
- **Fin de vidéo** : le résultat est validé dès son import. Le cooldown serveur reste imposé avant la vidéo suivante et visible sans propriétaire actif ; il ne retient plus la fin de ligne ni le travail admissible sur le GPU local.
- **Preview** : désactivée pour les nouveaux rendus usine et Histoires en batch, y compris le batch direct. H3/REF2V manuels conservent leurs réglages. Le lecteur de résultat et les keyframes restent disponibles. La politique batch est persistée dans l’essai.
- **Petits hommes** : appliquer le preset active DLSS et Texte IG (anglais, Gemma 4 local, trois variantes). L’intention demande une solution avec un accessoire extérieur choisi librement, guidée par quelques mécanismes illustrés dès le Plan. L’intention et les options restent éditables. Les lignes existantes gardent leurs réglages jusqu’à une application explicite du preset.
- **Résultats** : Voir le DLSS / Voir la vidéo, Ouvrir le dossier, Texte IG · copier. Dans le détail : Copier le chemin, copie par variante et téléchargement TXT. Les emojis, hashtags et sauts de ligne sont conservés ; les emojis séparés déjà présents dans le texte ne sont pas répétés.
- **Rangement** : `<dlss-output-root>/dlss/Petits hommes|Histoire|Levres|Autres/YYYY-MM-DD/`. La famille d’origine survit au passage en Personnalisé ; une scène conserve sa famille Histoire et son numéro dans le nom. Date locale de disponibilité du résultat final ; l’arrivée plus tardive du texte conserve le même dossier. Les fichiers vidéo et `_Instagram.txt` ont un radical commun avec identifiants courts.
- **Publication** : les sources restent à leur emplacement. Un lien physique évite de dupliquer les octets sur le même volume ; une copie atomique sert de repli. Écriture dans un worker distinct, état persistant et bouton Reprendre l’export si nécessaire, sans nouveau rendu ni appel LLM. Le texte reste copiable et téléchargeable si la publication sur disque échoue.
- **Accès au dossier** : l’ouverture native fonctionne depuis le Lab sur son PC Windows ; depuis un autre poste, utiliser Copier le chemin ou les téléchargements. La copie serveur DLSS existante reste distincte du classement local de l’usine.

Code livré localement, sans redémarrer les services. Au prochain redémarrage habituel du Lab, recharger avec Ctrl+F5. Le nouveau classement peut également publier les résultats usine déjà terminés ; aucun média d’origine n’est déplacé et aucune génération n’est relancée.

Vérifications effectuées : AST Python, JSON et liaisons de manifestes, imports dans le venv, syntaxe JavaScript, `git diff --check`. Les tests suivants sont **préparés, non exécutés** :

```powershell
python -m unittest tests.test_video_factory tests.test_video_factory_results tests.test_video_factory_web tests.test_machine_work tests.test_h3_bunny tests.test_h3_render tests.test_episodes tests.test_episode_reference_refresh
```


## Utilisation

Les boutons violets **Envoyer à l’usine** sont disponibles sur les images KREA 2 (en remplacement de Replacer dans…), à côté de Créer le parcours dans H3 et REF2V, et à côté de Lancer prompts + vidéos dans Histoires. L’envoi copie les données dans Préparation, sans création de parcours ni appel LLM ou génération vidéo. Le retour Ajouté à l’usine permet d’ouvrir la file ; l’atelier reste affiché. Un double envoi identique retrouve la même ligne. Dupliquer permet une nouvelle production volontaire.

- **Préparation** : chaque ligne affiche Prêt ou À compléter. Sélectionner une vidéo ouvre les réglages à droite, ou sous la liste sur un écran plus étroit. Une image seule arrive sans intention présumée, avec un rôle à choisir. Lancer la sélection ajoute explicitement les lignes complètes à la production.
- **Production** : vidéos actives et en attente. L’ordre est modifiable avec les flèches de priorité. Modifier une ligne en attente la remet en préparation.
- **Résultats** : vidéos terminées à contrôler, erreurs et annulations. Cliquer sur Plan, Prompt, Vidéo, DLSS ou Texte IG ouvre le détail et les sorties déjà disponibles. Reprendre la chaîne conserve les étapes réussies. Archiver retire les réussites contrôlées de cet onglet.
- **Archives** : quatrième onglet pour les fiches archivées manuellement, avec médias, textes et durées conservés. Restaurer dans Résultats les remet dans la liste sans relance ; Dupliquer ouvre une nouvelle Préparation.

Une scène correspond à une ligne : cinq scènes d’histoire donnent cinq vidéos, regroupées et sélectionnables ensemble. Les productions sont rattachées aux scènes si les entrées et leur préparation sont restées inchangées. Une scène modifiée entre-temps conserve sa nouvelle préparation ; la vidéo reste accessible dans l’usine avec une indication dans son détail. Les références manquantes d’histoire se corrigent dans la source, puis via Recharger depuis l’histoire.

## Réglages

Cinq presets : Réglages source, Lèvres, Petits hommes, Petits hommes — expérimental, Personnalisé. Une modification devient Personnalisé en conservant l’origine. Réglages source restaure la copie capturée à l’envoi.

- Lèvres : H3, une image de fin, un plan de 10 s. Deux passages complets du rouge
  à lèvres, d’abord en bas puis en haut : dépôt immédiat uniquement derrière le
  contact, haut nu pendant le premier passage, arrêt du dépôt quand le stick se
  soulève. Retrait de la main puis sourire franc tenu sur la fin. La règle et les
  états intermédiaires sont demandés explicitement au Plan et au Prompt.
  Matières/couleurs adaptées à la référence. DLSS actif, Texte IG désactivé par
  défaut ; axes 1/1/1, dialogue 0 et audace 1. Réappliquer le preset pour mettre
  à jour une ancienne ligne. Choisir une image finale avec le sourire souhaité.
- Petits hommes : H3, image de départ, un plan, huit secondes ; une main géante apporte un accessoire librement choisi pour aider les petits personnages. L’intention illustrée reste éditable ; DLSS est activé et Texte IG désactivé à l’application de ce preset.
- Les trois presets spécialisés utilisent Bunny et Motion Repair, avec les réglages actuels de fabrication. Ils exigent une seule image et refusent un lot incompatible sans modification partielle.
- Le nombre de plans accepte Auto ou 1 à 6. H3 accepte première / dernière frame ; REF2V conserve les références et leurs rôles.
- Les réglages de rendu et les paramètres avancés sont accessibles depuis l’inspecteur. Modifier seulement la durée de rendu ne réécrit pas un prompt déjà préparé.
- Hors application des presets Lèvres et Petits hommes, le DLSS hérite de la source ; il est actif pour les scènes envoyées depuis Histoires et désactivé par défaut pour une nouvelle image ou un nouveau parcours sans réglage source.
- Texte IG est désactivé par défaut, y compris sur les presets Lèvres et Petits hommes (classique et expérimental). Son activation propose anglais, Gemma 4 local et trois variantes. Le français et le nombre de variantes sont réglables. L’entrée est automatiquement la vidéo H3 produite ; un échec DLSS n’empêche pas Instagram. Le résultat peut être ouvert dans l’atelier Texte IG.

La sélection multiple permet un preset commun, une durée, le nombre de plans, DLSS et Texte IG. Les champs non renseignés restent inchangés. Le retour Annuler restaure les réglages précédents et les résultats dont les entrées correspondent. Les anciennes sorties restent consultables dans l’inspecteur. Une révision par ligne empêche d’écraser une modification concurrente. Le rafraîchissement conserve les brouillons et le focus dans les réglages.

## Ordonnancement et reprise

Le coordinateur existant reste responsable des machines, des files de réservation et des règles thermiques. Pour chaque machine disponible, l’usine cherche la première étape exécutable dans l’ordre des lignes. Une ligne bloquée ne retient pas l’autre machine ; elle retrouve sa priorité dès qu’elle peut avancer. Une seule étape par ligne est active à la fois.

**Pause après les étapes actives** laisse finir les étapes déjà commencées, puis empêche toute étape suivante. La pause persiste jusqu’à Reprendre la file, y compris si l’utilisateur lance de nouvelles lignes. Les éléments en préparation ne partent jamais automatiquement. Il n’y a pas de commande Finir la file puis suspendre.

Annuler arrête l’admission des étapes restantes et demande l’arrêt des travaux H3/DLSS déjà actifs. Une réponse LLM en cours est interrompue au prochain événement du flux. Les sorties reçues avant ou pendant la demande restent accessibles.

La file, les réglages copiés, les révisions et les identifiants des travaux enfants sont enregistrés atomiquement dans `workspace/video_factory/state.json`. Un verrou de processus empêche deux moteurs d’utiliser ce même journal. Les rendus et DLSS déjà identifiés sont réconciliés au redémarrage, même si la file est en pause. Une étape LLM interrompue, ou une étape sans travail enfant enregistré, demande une reprise explicite ; elle n’est pas relancée silencieusement. Les documents de préparation déjà enregistrés sont réutilisés à la reprise.

Le type persistant `kind: video` laisse une place à de futurs blocs. La génération d’histoires ou de nouveaux épisodes comme blocs de file n’est pas incluse dans cette version.

## Validation et mise en service

Contrôles effectués : syntaxe Python, imports des nouveaux modules, analyse syntaxique JavaScript et `git diff --check`. Aucun test fonctionnel ni génération n’a été exécuté, conformément à `AGENTS.md`. Aucun service n’a été redémarré.

Tests ciblés à lancer avec l’environnement Python habituel depuis ce checkout :

```powershell
python -m unittest tests.test_video_factory tests.test_video_factory_web
```

Les tests utilisent des services factices et un répertoire temporaire. La fixture navigateur utilise le Chromium local si disponible, sans serveur ni backend de génération.

La suite projet reste `python -m unittest discover -s tests`. Après le prochain redémarrage habituel du Lab, recharger la page avec Ctrl+F5. Vérifications manuelles utiles : envoyer une image, appliquer Lèvres et vérifier DLSS/IG actifs, anglais / trois variantes ; envoyer une histoire de cinq scènes ; vérifier les cinq étapes visibles ; lancer une petite sélection, mettre en pause et reprendre ; annuler puis reprendre une chaîne avec une vidéo déjà produite.

Sauvegarde avant implémentation : [snapshot-pre-video-factory-2026-09-25](https://github.com/EasyFrag/panelforge/tree/snapshot-pre-video-factory-2026-09-25), commit `8e91ed424ce51b508746ac0d239d9187d8a45c16`.

## Patch complémentaire du 26 septembre : durées, reprise et versions traduites

- Production et Résultats affichent les secondes sous chaque étape : compteur
  en cours, durée figée à la fin, rien pour Off ou une mesure inconnue.
- **Reprendre la chaîne** est la commande unique, sur une ligne, dans sa fiche
  ou sur une sélection. Elle conserve les étapes réussies ; un export seul en
  erreur se reprend sans génération. L’identifiant DLSS trop long est corrigé.
- Les miniatures des trois onglets et les références des fiches s’agrandissent
  avec la loupe +, indépendamment de la sélection.
- **Supprimer** est disponible dans toutes les fiches et en sélection multiple
  sur les trois onglets. Une étape active est d’abord arrêtée ; la fiche reste
  marquée Suppression en cours jusqu’à confirmation. Les sources et médias
  restent conservés. Une ligne supprimée peut être renvoyée depuis Histoires.
- Un envoi partiel indique les scènes déjà présentes et leur état.
- Histoires en version English utilise le prompt traduit validé, sans refaire
  le plan ou la rédaction. Une traduction incomplète bloque l’envoi. Le message
  JavaScript view is null est corrigé.

Les lignes existantes ne sont pas réécrites automatiquement. Pour corriger une
ancienne ligne anglaise partie du scénario français : Recharger depuis
l’histoire en Préparation, ou Supprimer puis renvoyer l’édition English.
Charger le correctif au prochain redémarrage habituel du Lab puis Ctrl+F5.

[Diagnostic, comportement et tests à lancer](proposals/video-factory-timing-retry-2026-09-26.md).

## Patch du 26 septembre : Lèvres, inondations et lisibilité

- Lèvres utilise les nouveaux réglages décrits ci-dessus. Une nouvelle préparation
  reçoit la durée effective du rendu, avec la référence alignée sur la fin.
- Petits hommes garde huit secondes et reçoit un exemple d’inondation plus ludique :
  la ventouse déclenche un tourbillon qui vide la rue comme une baignoire. Le choix
  de l’objet reste libre ; l’effet visible suit son action.
- Un épisode est encadré et fermé après sa dernière scène visible, avec un espace
  avant les vidéos indépendantes. L’en-tête indique le nombre de scènes de l’onglet.
  Un groupe coupé par les priorités reste délimité sans réordonner les lignes.
- Les copies avec dialogues anglais ont un badge EN dans le titre de la ligne et
  de la fiche. L’intention française reste conservée : le prompt traduit déjà prêt
  est utilisé pour la vidéo. Aucune nouvelle traduction/rédaction n’est lancée.
- DLSS affiche un pourcentage calculé sur ses phases, jamais NaN %. Sans mesure,
  En cours ; pendant réception/import, Finalisation. Les secondes restent visibles.

Code livré localement, cache usine `20260926.patch3`, contrôles de syntaxe/imports
réussis. Tests fonctionnels préparés et laissés à l’utilisateur selon AGENTS.md.
Aucun redémarrage ni rendu de vérification. Au prochain redémarrage habituel puis
Ctrl+F5, réappliquer les presets aux lignes de Préparation à actualiser.

[Diagnostic et commandes de vérification](proposals/video-factory-lips-2026-09-26.md).

## Patch du 26 septembre : Archives et résultats compacts

Les statuts et actions de Résultats/Archives forment une grille de trois colonnes :
Terminé / Voir le DLSS / Ouvrir le dossier, puis Texte IG / Archiver / Supprimer.
Deux colonnes sur petit écran. Les erreurs gardent Reprendre la chaîne ; Archives
propose Restaurer à la place d’Archiver.

Après contrôle d’un lot, choisir le filtre **À archiver**, sélectionner les fiches
et cliquer **Archiver la sélection**. Une réussite doit être entièrement exportée,
y compris son texte Instagram final. Les erreurs restent dans Résultats. La même
action est disponible sur chaque ligne et dans sa fiche. Il n’y a pas d’archivage
automatique. Archives a son propre compteur, indépendant de Résultats.

**Restaurer dans Résultats** fonctionne à l’unité et en lot, sans relancer de
traitement. L’archive conserve les intentions, prompts, sources, durées et sorties.
Elle ne déplace pas de fichier. Pour refaire une production, utiliser **Dupliquer** ;
un renvoi identique depuis la source indique **Déjà archivé** avec accès à l’archive.
Supprimer retire la fiche de l’usine en conservant les médias, comme auparavant.

Publication : les vidéos sans DLSS sont rangées dans `<famille>/<date>/base video/`,
y compris si DLSS est désactivé ou échoue. Les DLSS et TXT restent dans le dossier
de date ; Ouvrir le dossier mène à ce niveau. Une arrivée tardive d’Instagram garde
le dossier attribué. Les quatre anciennes bases ont été migrées lors du cadrage.

Cache usine `20260926.patch4`. Au prochain redémarrage habituel du Lab puis Ctrl+F5,
l’onglet Archives et les commandes seront disponibles. Aucun résultat n’a été
archivé à ta place. Contrôles statiques réussis ; tests fonctionnels préparés et
laissés à l’utilisateur conformément à AGENTS.md.

```powershell
python -m unittest tests.test_video_factory tests.test_video_factory_archives tests.test_video_factory_results tests.test_video_factory_web tests.test_video_factory_timing_retry
```
