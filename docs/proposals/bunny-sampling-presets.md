# Proposition : presets de rendu BUNNY et évolution du prompting

Discussion du 13 septembre 2026, périmètre corrigé après retour utilisateur.
Aucune modification du moteur ou des réglages des ateliers. La
[maquette interactive du 14 septembre](render-presets-v2.html) présente le
sélecteur unique, les détails repliables et les fiches LoRA. Son
[aperçu](render-presets-v2.png) montre l'état initial. L'ancienne maquette
`render-presets-ui.html` est dépassée ; sa zone de comparaison est abandonnée.
Les candidats EROS sont illustratifs et bloqués au lancement tant que leur
adaptation aux deux passes n'est pas définie. La maquette ne fait aucun appel
réseau, aucune génération et ne conserve aucune donnée de projet.

Priorités utilisateur du 14 septembre : simplification UI en cours de maquettage,
évolution I2V en **P1** différée, amélioration de l'analyse média en **P2** ;
voir [backlog](../backlog.md). Les contrôles du rendu classique ne sont pas détaillés
dans cette maquette centrée sur BUNNY ; leurs réglages actuels restent à préserver.

## Prompting : une variable nouvelle à la fois

- Mise en scène 1.1 expérimentale reste à implémenter : limiter les redites du
  premier cadrage déjà établi par une frame exacte, conserver les ancrages dans
  le Plan interne et les informations utiles aux autres cadrages et références.
  Commencer par I2V ; les bases utiles à REF2V seront adoptées explicitement,
  selon le rôle des références, sans modifier automatiquement les autres recettes.
- Étape suivante possible : jeu d'acteur observable, perception et réactions
  causées par les événements. Pas de geste, dialogue ou agitation obligatoire.
- Ensuite : événement concret issu d'une intention vague, selon l'audace
  choisie, sans remplacer le sujet ou systématiser surprise et retournement.
- Enfin : mieux répartir action, respiration, réaction et révélation sur la
  durée ; affiner les motivations des changements de cadrage.

Ces étapes sont des directions à évaluer après les essais, pas un engagement à
les cumuler immédiatement. Conserver deux appels, recettes exactes, paramètres
utilisateur et indépendance Classique/Combat/Sensuel. Comparer les nouvelles
recettes avec les mêmes LLM avant d'évaluer séparément un changement de modèle.

## Constat EROS et BUNNY

La [fiche EROS](https://huggingface.co/TenStrip/10Eros-Max?not-for-all-audiences=true)
liste `er_sde/beta` 4, `er_sde/beta57` 4–6, `res_multistep/simple` 6–8,
`lcm/simple` 6–8, `lcm/beta` 4–6, `euler/simple` 4–8 steps. L'auteur privilégie
res_multistep pour le mouvement et lcm/simple pour l'audio Turbo ; ces jugements
ne constituent pas une validation de notre BUNNY. Les fichiers TURBO intègrent
déjà une fusion Turbo. Les presets destinés à ces variantes devraient donc
définir explicitement l'absence de Turbo BUNNY supplémentaire.

Audit en lecture seule de `/object_info/<classe>` sur Bucket : le nœud
`MiniMaxH3DualClockSamplerT8` expose les quatre samplers et `beta57`, dont
l'infobulle précise alpha=0,5 et beta=0,7. BasicScheduler expose beta mais pas
beta57. Le plan T8 expose base/coarse/refine, refine restant borné à 3–5 ; le
DetailMixer reçoit ses refine_sigmas sans sélecteur sampler/scheduler équivalent.
Disponibilité des entrées confirmée, compatibilité GPU et qualité non testées.

Dans notre graphe BUNNY 0.1.3, le premier sampler utilise le sampler du DualClock
mais les sigmas du ParityPlan. Le deuxième utilise le sampler et les sigmas du
DetailMixer, alimenté par le même ParityPlan. Le calendrier du DualClock n'est
donc pas celui branché directement sur la première diffusion. Le triplet
9/4/5 signifie 4+5 pas effectivement exécutés. Changer seulement le champ
scheduler du DualClock ne raccorde pas automatiquement simple/beta/beta57 aux
diffusions. Les budgets de la fiche ne précisent pas notre décomposition en
deux passes ; ne pas les copier dans base_steps ou les présenter comme des
presets BUNNY fidèles sans vérifier leur traduction.

L'adaptation demanderait une recette de rendu versionnée, avec contrôle des
calendriers effectifs, raccordements du modèle et des deux passes. Garder BUNNY
0.1.3 comme témoin intact. L'utilisateur réserve EROS à BUNNY ; les futurs
presets MiniMax classiques alimenteront un catalogue distinct et compatible.

## Interface proposée

Zone quotidienne : **Recette de rendu / Modèle / Préréglage**, puis Ratio, Durée,
MP initiaux, MP sortie, Seed avec Réutiliser, Musique et bouton Lancer.
Un résumé indique les pas effectifs des deux passes et le Turbo appliqué.

Un seul sélecteur **Préréglage de rendu** remplace les boutons Steps rapides /
Steps classiques. Il conserve ces deux choix avec leurs triplets 9/4/5 et
30/25/5, puis pourra accueillir les adaptations EROS compatibles et
**Personnalisé**. Les presets réunissent steps, sampler et scheduler réellement
appliqués ; ils n'ajoutent pas un second sélecteur de sampling au premier niveau.
Le résumé reste visible quand les détails sont repliés. Les deux anciens raccourcis
ne modifient actuellement pas le Turbo : conserver ce comportement dans leurs
équivalents, et rendre explicite toute politique Turbo propre à un nouveau preset.

Sections repliées :

- **LoRA · N actifs** : garder les quatre emplacements, ordre, forces par passe
  et fiches. Retirer le sélecteur redondant « Profil de rendu : LoRA » et déduire
  l'activation des lignes sélectionnées lors d'une future refonte.
- **Réglages avancés** : samplers, calendriers, pas par passe, Turbo, preview.
  Le calendrier de base BUNNY reçoit une explication ; ne pas le confondre avec
  le total. Afficher 0,70 au lieu de 0,7000000000000002.
- **Prompt utilisé** : texte existant et adaptation REF2V ; dégager l'action
  de conversion du centre des paramètres de rendu.

Les presets sont filtrés par moteur et checkpoint exact, sans réinitialisation
silencieuse au changement de modèle. Un preset de sampling possède ses
samplers/calendriers/steps et sa politique Turbo ; il ne remplace pas prompt,
images, seed, durée, dimensions, LoRA ou réglage musique. Une modification de
ses paramètres donne « Personnalisé », enregistrable sous un nouveau nom.

## Parcours retenu : un preset, un rendu habituel

L'utilisateur choisit un preset, lit son résumé et lance avec le bouton existant.
Le résultat rejoint l'historique habituel, avec le preset, sa version et les
paramètres effectifs conservés pour reprendre les réglages ultérieurement.
Les essais se font un par un dans cet atelier.

Pas de zone de comparaison, de bouton Comparer, de sélection multiple ou de
lancement en série dans ce chantier BUNNY. La comparaison DLSS image déjà
implémentée est un autre outil et n'est pas concernée par ce retrait.

Chaque preset exécutable devra définir des valeurs exactes pour les deux passes,
pas une plage « 6–8 ». Vérifier le raccordement réel des samplers et calendriers
avant de proposer les adaptations EROS comme utilisables. Les réglages actuels
restent disponibles ; ne pas inventer des triplets à partir de la fiche auteur.

Priorité : simplifier les contrôles existants et réunir steps/sampling dans un
sélecteur, puis ajouter les presets compatibles. Le chantier de prompting reste
séparé, afin de permettre les essais longs demandés sans cumuler les changements.
