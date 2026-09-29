# Petits hommes expérimental : besoin ciblé, direction v4 — 28 septembre 2026

Implémentation autorisée après l’analyse des tsunamis, sécheresses et incendies.
Le preset existant little_men_experimental est conservé : aucun nouveau mode
ou sélecteur ajouté.

## Comportement livré

- Base commune approuvée de 87 mots, centrée sur un objet du quotidien
  monumental, une aide ingénieuse et un bénéfice durable.
- Une seule phrase ajoutée selon le besoin identifié : sécheresse → eau ;
  tsunami/vague → intercepter ou détourner ; inondation → évacuer hors de la
  zone protégée ; incendie → flammes et fumée animées puis extinction.
- Intention avec objectif : 99, 101, 101 ou 102 mots. Ces chiffres n’incluent
  pas la durée, les métadonnées image ou les règles vocales.
- Tornades et réparations : pas de phrase supplémentaire imposée. L’objet
  reste libre dans tous les cas, sans quota de gestes.
- Le Plan reçoit une consigne de 40 mots contre 92 auparavant : relier besoin,
  mécanisme et résultat durable dans continuity_invariants, garder le choix
  d’objet libre et ne pas figer les phénomènes à cause du matériau visuel.

Le besoin est repéré sans appel LLM supplémentaire. Priorité à l’intention
vidéo et au contexte saisi, puis à l’intention KREA de l’image exacte, puis à
sa description complète. Les labels, noms de fichiers et textes de style sont
ignorés pour ce repérage : un fichier nommé incendie peut montrer un tsunami.
Une vague prime sur la seule inondation qu’elle produit.

Le repérage textuel est volontairement borné à des termes français/anglais
positifs. Il traite les négations simples et les besoins mixtes comme incertains
plutôt que d’empiler des objectifs. Si le contexte ne suffit pas, le Plan reste
chargé d’interpréter l’image. Pour une sécheresse visuellement ambiguë, préciser
« sécheresse, manque d’eau » dans le champ de contexte existant suffit à fixer
l’objectif. Le texte n’est jamais déduit de l’apparence des personnages.

La phrase choisie arrive au Plan et au Writer ; le Writer conserve le Plan
approuvé. Les onze langues, l’équilibrage, les formules minimales et leur
validation stricte restent inchangés. La langue ne se choisit toujours qu’une fois.

## Conservation et activation

La version interne est little_men.localized_thanks.v4. Les helpers et la règle
Plan v3 sont conservés pour les sessions anciennes. Une nouvelle préparation ou
une copie remplace seulement les anciens défauts v2/v3 exacts ; les intentions
personnalisées sont conservées. Réappliquer le preset permet d’adopter la nouvelle
direction tout en conservant la langue si ses entrées restent les mêmes.

Rendu, durée de 10 s, modèles, DLSS, preset classique et Lèvres conservés.
Instagram reste désactivé par défaut. Aucune source KREA n’est réécrite et aucune
image n’est régénérée par ce correctif de preset. Une image représentant le feu
comme une sculpture rigide peut encore limiter le résultat ; les futures images
pourront décrire des flammes souples/irrégulières et une fumée légère.

Charger le correctif au prochain redémarrage habituel du Lab, puis réappliquer
Petits hommes — expérimental sur une nouvelle fiche/copie à préparer.
Les rendus et sessions déjà engagés ne sont pas modifiés en direct.

## Vérification

Dix nouveaux tests hors ligne préparés dans tests/test_video_factory_needs.py :
besoins FR/EN, noms trompeurs, priorité auteur/KREA, négations/cas mixtes,
contexte long, compatibilité et duplication v3, réapplication du preset,
requêtes Plan/Writer avec besoin unique et langue figée, onze formules strictes.
Les tests existants de version courante sont adaptés ; les régressions vocales
historiques et la requête v3 restent disponibles.

Contrôles effectués : AST des fichiers Python modifiés/ajoutés, imports de sept
modules sans instancier les services, comparaison statique du texte approuvé,
des anciens helpers et intentions, des langues/pools/tirages et diff --check.

Tests non exécutés conformément à AGENTS.md. Aucun LLM, rendu, service
redémarré, modification de fiche de production, commit ou push.

    python -m unittest tests.test_video_factory_needs tests.test_video_factory_solutions tests.test_video_factory_languages tests.test_video_factory_experimental tests.test_classic_cinematic tests.test_video_preparation_recipes

Les prochains essais servent à mesurer le résultat visuel, notamment sur une
sécheresse ayant reçu un pansement, un tsunami et un feu en laine. Garder une
tornade et une réparation témoins. Aucune génération de comparaison lancée ici.

Sauvegardes, diff isolé et mesures :
D:/Code/panelforge/.agent/diagnostics/little-men-needs-v4-20260928/.
