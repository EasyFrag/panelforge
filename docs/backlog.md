# Backlog produit

## Priorités actives — 14 septembre 2026

- **Prochaine itération proposée : UX vidéo + consignes LLM accessibles.**
  Maquette de simplification du rendu **validée par l'utilisateur le 14 septembre** :
  [presets de rendu](proposals/render-presets-v2.html). Un seul preset pour le
  prochain rendu, contrôles avancés repliés, quatre LoRA et fiches accessibles,
  MP initiaux/après upscale et Seed Réutiliser visibles. Pas de zone de comparaison
  ni de lancements en série BUNNY. Ajouter un accès discret aux fichiers système
  éditables et au message réellement assemblé pour le Plan/Writer ; isoler les
  sources actives des anciennes recettes avec conservation des identités/versionnements.
  [Constat et proposition](proposals/editable-llm-prompts.md). **Discussion et
  alignement uniquement pour ce tour**, application non modifiée. État préalable
  sauvegardé sur GitHub : `snapshot-before-render-ux-prompts-2026-09-14`, commit `934cd2f`.
- **P1 — Évolution du prompting I2V / Mise en scène 1.1.** Mise en attente explicite
  par l'utilisateur, à conserver. Première étape : réduire la redescription de la
  frame initiale exacte tout en conservant les ancrages du Plan interne. Les bases
  utiles pourront être adoptées explicitement en REF2V selon les rôles d'images.
  Version expérimentale distincte, ancienne version conservée pour des essais
  longs, deux appels et indépendance des familles maintenus. Voir le
  [cadrage](proposals/bunny-sampling-presets.md).
- **P2 — Améliorer l'analyse vidéo → intention française → H3/REF2V.** Inspiration
  demandée : [video-to-h3-prompt](https://github.com/LoveRain1997/video-to-h3-prompt).
  Enrichir l'outil déjà livré : chronologie causale, distinction action/caméra/montage,
  réexamen limité des passages ambigus. Réutiliser le modèle vision sélectionné,
  l'extraction et la transcription CPU actuels ; pas de nouveau service ni de
  pipeline concurrent de rédaction H3. Discussion uniquement, aucun patch moteur.
  [Analyse et proposition bornée](proposals/media-analysis-adaptive-p2.md).

Les points datés ci-dessous conservent l'historique. Ces priorités du 14 septembre
remplacent les anciennes priorités des travaux encore à faire ; la V1 d'analyse
média et sa transcription sont déjà implémentées. La comparaison DLSS image
existante n'est pas concernée par l'abandon de la comparaison BUNNY.

**Point du 11 septembre — Analyse média** : transcription locale facultative implémentée, CPU par défaut sur demande utilisateur, GPU sélectionnable ; [guide 1.1](media-analysis-speech-1.1.md). Tests préparés à exécuter par l’utilisateur. Nouvelle discussion : distinguer une intention décrivant toute la scène (T2V) et une intention privilégiant action/changements/caméra/rythme quand des images sont déjà fournies (I2V/REF2V), sans supprimer les descriptions encore nécessaires selon le rôle des références. Attendre le retour d’essai avant modification des consignes sur ce point.

Priorités fixées par l’utilisateur le 9 septembre 2026 : **combat P0**, **analyse vidéo/images vers prompt P1**. Recherche de seeds laissée de côté.

**Point du 10 septembre** : **analyse vidéo/images + texte facultatif → intention française → H3/REF2V** implémentée sur autorisation, V1 à tester par l’utilisateur ; guide [Analyse média 1.0](media-analysis-1.0.md). **Sensualité / jeu d’acteur non explicite** reste différé. La recette **Classique Mise en scène 1.0 en deux appels** est implémentée sur autorisation, après snapshot GitHub. Tests et comparaison qualitative à effectuer par l’utilisateur ; aucun changement de défaut.

## Livré — Classique Mise en scène 1.0, expérimental

Implémentation et guide : [Classique Mise en scène 1.0](h3-classic-cinematic-1.0.md). Disponible dans H3/REF2V via le sélecteur Version Classique ; Auto/1–6 plans, Plan puis Writer. Anciennes recettes et paramètres de rendu conservés. Tests préparés, non exécutés. La proposition validée ci-dessous décrit le périmètre réalisé.

L’utilisateur trouve le parcours Combat en deux étapes convaincant et souhaite discuter de sa généralisation au Classique. Le Classique possède déjà des parcours en deux appels : H3 mono `direct.planned@1.2.0`, REF2V mono `direct.planned@1.1.0`, H3 multi `direct.multishot.planned@1.1.0`. Le travail proposé porte donc surtout sur le contrat du Plan et sa transmission au rédacteur, inspirés de Combat 1.3 ; le gain constaté ne peut pas être attribué au seul nombre d’appels, puisque schéma, exemples et compilateur ont également changé.

Proposition : entrée distincte **Classique · Mise en scène · 2 étapes · expérimental**, pour H3/REF2V, avec ses propres consignes et exemples (interaction, manipulation/transformation, mouvement et continuité du décor). Premier appel : identités, cadrage d’ouverture, progression d’actions ou d’états, phases caméra lorsque justifiées, rythme, état de sortie/raccord ; deuxième appel : rédaction H3 fidèle au Plan. Éviter d’imposer richesse d’action, vitesse, affrontement ou deux phases à toutes les scènes. Une scène calme doit pouvoir garder un plan simple. Les corrections supplémentaires restent explicites, sans troisième appel caché. Conserver les anciennes recettes et leurs parcours 1/2/3 ; ne pas changer le défaut Classique avant comparaison utilisateur.

Nombre de plans proposé : petit sélecteur **Auto / 1 à 6**, Auto par défaut. Auto respecte une demande explicite dans l’intention ; sinon le Plan propose un montage adapté à la durée et à la scène. Une valeur manuelle fait autorité pour le montage, règle affichée près du contrôle. Le Plan rend le nombre et les coupes vérifiables avant rédaction. Un plan contient plusieurs actions possibles ; le nombre de plans ne mesure pas la quantité d’action. La séparation actuelle mono/multi pourrait être réunie dans cette seule nouvelle recette, en conservant les anciens parcours.

Architecture à préserver : mécanisme neutre et contrats communs à versions exactes, politiques/exemples Classique indépendants ; aucun import automatique de « Combat latest » ou de consignes Combat. Toute extraction/modification du socle commun doit vérifier explicitement la conservation de Combat dans le même patch. Version et réglages conservés dans révisions, reprise, fork et conversion ; aucun changement implicite des modèles, LoRA, MP, seeds ou recettes de rendu. Comparer quelques intentions calmes et actives, mono et multi, avec références/rendu constants avant une promotion éventuelle. Implémenté sur autorisation le 10 septembre, sans promotion comme défaut.

## P0 — Prompts de combat H3 / BUNNY

[Audit des exemples et des sources du 9 septembre](h3-combat-prompt-audit-2026-09-09.md) : neuf fichiers reçus, sept prompts distincts ; fiches Combat Base V2 / Weapon Combat V1 et guides officiels H3 consultés. Préparer des échanges causaux avec identités et armes stables, contacts/réactions, déplacements lisibles et continuité entre actions. Ajuster la densité à la durée sans imposer une quantité rigide de gestes.

**Implémenté le 10 septembre 2026, essais utilisateur en attente.** Sélecteur Classique / Combat, neuf parcours H3 mono/multi et REF2V mono en 1/2/3 appels, prompts et politiques créatives propres, conservation de la famille jusque dans l'ajustement après rendu et l'adaptation REF2V. Voir [le guide Combat 1.0.0](h3-combat-preparation.md). Les anciens REF2V multi-plan restent Classique ; l'adaptation H3 Combat multi-plan vers REF2V conserve la famille.

Contrainte confirmée : deux familles indépendantes, blocs communs à versions exactes ; toute amélioration générale est examinée pour les deux familles dans le même patch, sans héritage automatique de Classique. Les neuf cookbooks et trois profils Classique actuels conservent leurs textes assemblés. Tests préparés, non exécutés ; aucun essai LLM/vidéo lancé par l'agent.

Choix distinct de la recette technique BUNNY et du LoRA de rendu : `BUNNY` est le déclencheur de Weapon Combat, pas un mot universel de prompting. L’auteur déconseille d’empiler Weapon Combat avec Combat Base V2 ou un autre LoRA de mouvement fort. Forces des deux passes, netteté et qualité selon le mode restent à expérimenter par l’utilisateur. **Aucun test ou rendu automatique ; expérimentation réservée à l’utilisateur.**

## Livré — Analyse vidéo / images vers intention française puis H3/REF2V — ancienne P1

**Implémentation autorisée et réalisée le 10 septembre**, après l’alignement ci-dessous : [guide V1 et tests utilisateur](media-analysis-1.0.md). Dans Video Lab, extrait sélectionnable, captures ajustables, images réordonnables et temps facultatifs ; un appel d’analyse, intention française éditable, transfert explicite vers H3/REF2V. Tests préparés et non exécutés. Extrait jusqu’à 60 s ; durée cible 5–15 s pour les rendus actuels. Les paragraphes suivants conservent le cadrage préalable, désormais mis en œuvre ; les mentions de discussion sans autorisation décrivent cet état antérieur.

**Clarification utilisateur du 10 septembre, discussion reprise** : importer une ou plusieurs images OU une vidéo, ajouter facultativement un texte d’intention en français, analyser l’ensemble puis transmettre l’intention à H3 ou REF2V pour préparer une vidéo. Proposition actuelle : une **intention française éditable** comme résultat de l’analyse, puis utilisation des parcours existants pour produire le prompt technique et rendre. La proposition antérieure de compilation directe vers le prompt final en deux appels d’analyse n’est pas retenue comme un engagement ; le nombre d’appels propre à l’analyse reste à cadrer. Aucun nouveau parcours concurrent de préparation H3/REF2V.

Interface proposée dans **Video Lab**, espace Analyse vidéo/images chargé à son ouverture : import, sélection début/fin d’un extrait vidéo, lecteur et captures horodatées ajustables ; images multiples réordonnables. Champ facultatif pour dire ce qu’il faut conserver/changer. Bouton Analyser, résultat français modifiable, puis Préparer dans H3 / Préparer dans REF2V avec l’intention préremplie. Sans texte complémentaire : fidélité aux observations proposée par défaut ; avec texte : adaptations demandées explicites, distinctes des faits observés. Exemples : reprendre une mise en scène avec d’autres personnages ou un autre décor.

**Dernier alignement utilisateur, 10 septembre** : sélection d’une portion de vidéo avec un sélecteur, et repères temporels facultatifs par image importée (exemple : 0 s, 1 s, 3 s), en plus du réordonnancement. Présentation proposée pour la vidéo : plage début/fin à deux poignées, valeurs saisissables et lecture de l’extrait ; seules les captures de la plage sont analysées. Afficher les temps d’origine dans le lecteur, mais utiliser une chronologie relative à zéro pour l’intention (extrait 12–20 s → séquence 0–8 s).

Images : champ Temps (s) facultatif sur chaque vignette ; sans temps, conserver seulement l’ordre, sans inventer un minutage observé. Les temps renseignés servent de repères de rythme dans l’intention. Règle proposée pour le déplacement : conserver le temps avec l’image, signaler une incohérence entre ordre et repères, permettre correction/suppression manuelle ; aucun effacement ou tri automatique silencieux. Durée cible distincte et modifiable ; le dernier repère ne détermine pas implicitement toute la durée. Ce tour confirme le périmètre en discussion, sans autorisation d’implémenter.

Séparer les médias **analysés** des références **utilisées pour générer** : choix de première/dernière image dans H3 ou de références/rôles dans REF2V, remplacement par ses propres images possible. Pas d’envoi automatique de toutes les captures au rendu. L’ouverture préremplit un atelier existant ; choix habituel de famille/recette/parcours, génération lancée par l’utilisateur. Conserver provenance/version de l’analyse sans modifier implicitement les recettes Classique/Combat ou les réglages MP/seed/LoRA.

L’intention proposée doit rendre lisibles les sujets, les actions successives, les changements d’état, le cadrage/mouvement caméra et les coupes observables. Durée de l’extrait reprise comme point de départ et modifiable ; ne pas conserver une durée textuelle périmée lorsque la cible change. Une image seule ne prouve pas un mouvement ; plusieurs images ne permettent pas d’affirmer les gestes entre elles. Les transitions inventées pour une adaptation sont distinguées des observations. Pas de prétention à retrouver exactement le prompt original.

Périmètre V1 encore proposé : visuel seulement, extrait court choisi dans une vidéo ; audio/transcription et analyse intégrale de longues vidéos différés. Modèle multimodal sélectionnable, vidéo analysée via images horodatées sans supposer de capacité vidéo native du modèle local. Échantillonnage ajustable important pour actions rapides et coupes ; qualité à évaluer sur des exemples après autorisation.

Réutilisable : entrées multimodales et keyframes horodatées du feedback H3, extraction Canvas/seek du Social Lab à isoler de ses consignes Instagram, extraction locale `DlssMedia.frames` à isoler de DLSS, ateliers et contrats de préparation REF2V/H3. Le moteur d’analyse temporelle reste à concevoir et à évaluer. Cette mise à jour documente l’alignement proposé, sans code fonctionnel.

## Fluidité et lisibilité des ateliers

Voir [l’audit du 9 septembre](assisted-performance-audit-2026-09-09.md). Après observation des correctifs : mesurer le parcours global de file, envisager l’affichage à la demande des essais anciens et le regroupement des actions secondaires. Ne pas retirer de fonctions sur la seule hypothèse qu’elles ralentissent les rendus.

## Recherche de seeds H3 / REF2V — mise de côté

Sujet discuté puis mis de côté par l’utilisateur, décision réaffirmée le 9 septembre : **on oublie pour le moment, aucune priorité active**. [Audit Seed Hunter du 7 septembre](h3-seed-search-audit-2026-09-07.md) conservé pour mémoire : comparer plusieurs aperçus partageant prompt/images/réglages, choisir un candidat et ne finaliser que celui-ci. Conservation/reprise du latent à traiter pour éviter de reconstruire un résultat différent au changement de résolution. Ni l’import de BUNNY ni la preview pendant le calcul ne constituent cette fonctionnalité. Aucun patch Seed Hunter lancé.

## Vision à plus long terme

- **Sensualité / jeu d’acteur non explicite — différé par l’utilisateur le 10 septembre** : éventuelle famille de préparation indépendante et versionnée, microexpressions, regards, gestes subtils, progression émotionnelle et caméra discrète ; rendu et réglages techniques communs. Discussion seulement, aucun patch autorisé ou en cours. L’analyse vidéo/images est également conservée en backlog.

Automatisation créative par agents locaux, d’abord sur des clips courts et thèmes choisis, puis continuité sur des vidéos plus longues avec sujets, décors et voix cohérents. Cette direction n’est pas un périmètre d’implémentation validé pour la prochaine passe.
