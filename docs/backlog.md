# Backlog produit

Priorités fixées par l’utilisateur le 9 septembre 2026 : **combat P0**, **analyse vidéo/images vers prompt P1**. Recherche de seeds laissée de côté.

**Point du 10 septembre** : les deux chantiers futurs **analyse vidéo/images → prompt** et **Sensualité / jeu d’acteur non explicite** sont gardés en backlog, à la demande de l’utilisateur. Discussion active sur une recette **Classique expérimentale en deux appels**, sans autorisation d’implémenter pour le moment.

## Discussion — Classique expérimental, plan de mise en scène puis rédaction

L’utilisateur trouve le parcours Combat en deux étapes convaincant et souhaite discuter de sa généralisation au Classique. Le Classique possède déjà des parcours en deux appels : H3 mono `direct.planned@1.2.0`, REF2V mono `direct.planned@1.1.0`, H3 multi `direct.multishot.planned@1.1.0`. Le travail proposé porte donc surtout sur le contrat du Plan et sa transmission au rédacteur, inspirés de Combat 1.3 ; le gain constaté ne peut pas être attribué au seul nombre d’appels, puisque schéma, exemples et compilateur ont également changé.

Proposition : entrée distincte **Classique · Mise en scène · 2 étapes · expérimental**, pour H3/REF2V, avec ses propres consignes et exemples (interaction, manipulation/transformation, mouvement et continuité du décor). Premier appel : identités, cadrage d’ouverture, progression d’actions ou d’états, phases caméra lorsque justifiées, rythme, état de sortie/raccord ; deuxième appel : rédaction H3 fidèle au Plan. Éviter d’imposer richesse d’action, vitesse, affrontement ou deux phases à toutes les scènes. Une scène calme doit pouvoir garder un plan simple. Les corrections supplémentaires restent explicites, sans troisième appel caché. Conserver les anciennes recettes et leurs parcours 1/2/3 ; ne pas changer le défaut Classique avant comparaison utilisateur.

Nombre de plans proposé : petit sélecteur **Auto / 1 à 6**, Auto par défaut. Auto respecte une demande explicite dans l’intention ; sinon le Plan propose un montage adapté à la durée et à la scène. Une valeur manuelle fait autorité pour le montage, règle affichée près du contrôle. Le Plan rend le nombre et les coupes vérifiables avant rédaction. Un plan contient plusieurs actions possibles ; le nombre de plans ne mesure pas la quantité d’action. La séparation actuelle mono/multi pourrait être réunie dans cette seule nouvelle recette, en conservant les anciens parcours.

Architecture à préserver : mécanisme neutre et contrats communs à versions exactes, politiques/exemples Classique indépendants ; aucun import automatique de « Combat latest » ou de consignes Combat. Toute extraction/modification du socle commun doit vérifier explicitement la conservation de Combat dans le même patch. Version et réglages conservés dans révisions, reprise, fork et conversion ; aucun changement implicite des modèles, LoRA, MP, seeds ou recettes de rendu. Comparer quelques intentions calmes et actives, mono et multi, avec références/rendu constants avant une promotion éventuelle. Discussion/documentation seulement.

## P0 — Prompts de combat H3 / BUNNY

[Audit des exemples et des sources du 9 septembre](h3-combat-prompt-audit-2026-09-09.md) : neuf fichiers reçus, sept prompts distincts ; fiches Combat Base V2 / Weapon Combat V1 et guides officiels H3 consultés. Préparer des échanges causaux avec identités et armes stables, contacts/réactions, déplacements lisibles et continuité entre actions. Ajuster la densité à la durée sans imposer une quantité rigide de gestes.

**Implémenté le 10 septembre 2026, essais utilisateur en attente.** Sélecteur Classique / Combat, neuf parcours H3 mono/multi et REF2V mono en 1/2/3 appels, prompts et politiques créatives propres, conservation de la famille jusque dans l'ajustement après rendu et l'adaptation REF2V. Voir [le guide Combat 1.0.0](h3-combat-preparation.md). Les anciens REF2V multi-plan restent Classique ; l'adaptation H3 Combat multi-plan vers REF2V conserve la famille.

Contrainte confirmée : deux familles indépendantes, blocs communs à versions exactes ; toute amélioration générale est examinée pour les deux familles dans le même patch, sans héritage automatique de Classique. Les neuf cookbooks et trois profils Classique actuels conservent leurs textes assemblés. Tests préparés, non exécutés ; aucun essai LLM/vidéo lancé par l'agent.

Choix distinct de la recette technique BUNNY et du LoRA de rendu : `BUNNY` est le déclencheur de Weapon Combat, pas un mot universel de prompting. L’auteur déconseille d’empiler Weapon Combat avec Combat Base V2 ou un autre LoRA de mouvement fort. Forces des deux passes, netteté et qualité selon le mode restent à expérimenter par l’utilisateur. **Aucun test ou rendu automatique ; expérimentation réservée à l’utilisateur.**

## P1 — Analyse vidéo / série d’images vers prompt H3 — discussion

Demande du 9 septembre 2026 : fournir une vidéo ou plusieurs images ordonnées et obtenir un prompt H3 REF2V ou FL2VA. **Discussion uniquement, implémentation non autorisée à ce stade.**

**Discussion reprise puis remise en backlog le 10 septembre** : l’utilisateur souhaite placer l’outil dans Video Lab, avec import vidéo OU plusieurs images. Proposition à aligner : troisième sous-onglet **Vidéo / images → prompt**, chargé seulement à son ouverture ; conserver les deux fonctions existantes. Le Social Lab possède déjà une extraction Canvas/seek côté navigateur (`social-lab.js`, `extractKeyframes`), mais quatre captures fixes ne suffisent pas à décrire finement les actions rapides. Réutiliser une petite brique d’extraction, sans réutiliser les consignes éditoriales Instagram.

V1 proposée : choisir un extrait court d’une vidéo (début/fin), voir le lecteur et une frise de captures horodatées, ajouter une capture au curseur ou supprimer une capture inutile. Pour plusieurs images : frise réordonnable, durée cible demandée ; les intervalles inconnus restent une hypothèse explicite. Sélection du modèle multimodal et de la cible H3 first/last ou REF2V, champ facultatif de consigne ; fidélité à la séquence par défaut. Un bouton déclenche deux appels proposés : observation visuelle chronologique, puis rédaction/compilation au format cible. Afficher une synthèse corrigible et le prompt final éditable, avec conversation visible pour ajuster. Les deux appels ne sont pas encore un choix utilisateur validé.

Séparer les images **analysées** des images **envoyées au rendu** : première/dernière choisies pour H3, références et rôles choisis pour REF2V, remplacement possible par ses propres images. Boutons Copier et Ouvrir dans H3/REF2V ; ouvrir un atelier dérivé sans imposer de refaire Brief/Plan, sans génération automatique. Réutiliser les rendus existants et conserver provenance/version de l’analyse, sans modifier implicitement les recettes Classique/Combat ou les réglages MP/seed/LoRA. Commencer par le visuel ; audio/transcription hors V1 proposée. Une série d’images ne permet pas d’affirmer les gestes intermédiaires ni de retrouver exactement un prompt original. Échantillonnage ajustable important pour combats/coupes rapides. Aucune capacité d’analyse vidéo native du modèle local supposée : V1 via images horodatées, à évaluer sur de vrais exemples après autorisation.

Proposition : un espace d’analyse distinct, import/extrait et frise d’images clés, courte explication corrigible de la scène, puis ouverture dans les ateliers H3/REF2V existants avec prompt et images choisies. Deux traitements proposés derrière une action simple : observation chronologique visuelle, puis rédaction selon les contrats du mode de génération. Pas de parcours Brief/Plan supplémentaire imposé.

Points à préciser avec l’utilisateur : reproduction fidèle ou adaptation de l’action à ses propres sujets/décors ; extraits courts, passage choisi dans une vidéo longue ou découpage complet. Séparer images d’analyse et images qui conditionnent le rendu. Des images seules n’établissent ni les mouvements exacts entre deux états ni le son. Commencer par le visuel ; transcription/audio à cadrer séparément si nécessaire.

Réutilisable : entrées multimodales et keyframes horodatées du feedback H3, extraction locale `DlssMedia.frames` à isoler de la fonction DLSS, contrats/prompts REF2V et H3. Le moteur d’analyse temporelle reste à concevoir et à évaluer ; aucune qualité d’analyse vidéo native démontrée par cet audit.

## Fluidité et lisibilité des ateliers

Voir [l’audit du 9 septembre](assisted-performance-audit-2026-09-09.md). Après observation des correctifs : mesurer le parcours global de file, envisager l’affichage à la demande des essais anciens et le regroupement des actions secondaires. Ne pas retirer de fonctions sur la seule hypothèse qu’elles ralentissent les rendus.

## Recherche de seeds H3 / REF2V — mise de côté

Sujet discuté puis mis de côté par l’utilisateur, décision réaffirmée le 9 septembre : **on oublie pour le moment, aucune priorité active**. [Audit Seed Hunter du 7 septembre](h3-seed-search-audit-2026-09-07.md) conservé pour mémoire : comparer plusieurs aperçus partageant prompt/images/réglages, choisir un candidat et ne finaliser que celui-ci. Conservation/reprise du latent à traiter pour éviter de reconstruire un résultat différent au changement de résolution. Ni l’import de BUNNY ni la preview pendant le calcul ne constituent cette fonctionnalité. Aucun patch Seed Hunter lancé.

## Vision à plus long terme

- **Sensualité / jeu d’acteur non explicite — différé par l’utilisateur le 10 septembre** : éventuelle famille de préparation indépendante et versionnée, microexpressions, regards, gestes subtils, progression émotionnelle et caméra discrète ; rendu et réglages techniques communs. Discussion seulement, aucun patch autorisé ou en cours. L’analyse vidéo/images est également conservée en backlog.

Automatisation créative par agents locaux, d’abord sur des clips courts et thèmes choisis, puis continuité sur des vidéos plus longues avec sujets, décors et voix cohérents. Cette direction n’est pas un périmètre d’implémentation validé pour la prochaine passe.
