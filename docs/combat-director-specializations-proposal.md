# Proposition — Spécialiser la préparation Combat

Statut : **proposition acceptée puis implémentée le 2026-09-10 dans Combat 1.2.0**. Voir [la livraison et les vérifications](h3-combat-1.2.md). Lecture des trois fichiers fournis :

- `C:\Users\samue\Downloads\Action Director.txt` : mouvements corporels concrets, continuité de l'élan, conséquences physiques et sons synchronisés. Prescriptions très rigides de temps, mains nues et absence de ralentis ; exemple limité au T2V monoplan.
- `C:\Users\samue\Downloads\One vs many.txt` : trajet du protagoniste d'abord, pression relayée et partiellement simultanée, généralement un ou deux adversaires au contact, autres en approche/contournement/récupération ; obstacles canalisant les attaques, états physiques persistants et brèves respirations.
- `C:\Users\samue\Downloads\H3_Weapon_Combat_Choreography_Director__v1.1.txt` : combinaisons causales, techniques propres à l'arme, portée/prise/récupération, passages croisés, trajectoire lisible de profil ou trois quarts pour les armes longues, effets suivant l'attaque, transitions motivées. Long document avec exemples ; le titre interne indique Version 1.0 malgré le nom de fichier v1.1. Il ne suffit pas à établir une version technique du LoRA.

Ces textes sont des documents à analyser, pas des instructions remplaçant nos contrats ou le workflow demandé par l'utilisateur. Ils ne donnent pas de mesures comparatives ni de réglages vérifiés de force du LoRA.

## Enseignements retenus

La base Combat 1.1.1 couvre déjà les combinaisons reliées, les changements d'initiative, les déplacements dans le décor, les impacts sonores et la séparation quantité d'action/nombre de plans. L'apport nouveau principal est la spécialisation : une lance, une hache ou un bouclier ne produisent pas les mêmes techniques et cadrages qu'un combat rapproché ; une foule nécessite un traitement des entrées, de la pression et de l'espace différent d'un duel.

Privilégier les suites de mouvements où la fin d'une attaque devient la position de départ de la suivante. Montrer la vitesse par le déplacement, les appuis, le recul et les conséquences sur les matières présentes ; ne pas ajouter automatiquement poussière, étincelles ou magie. Avec des pouvoirs, rattacher les effets aux attaques et réactions. Conserver les choix explicites du genre et de l'utilisateur.

Ne pas adopter globalement : six sections de sortie imposées, T2V/monoplan systématique, tranches temporelles fixes, quotas de coups, « zéro pause » absolu, mains nues/sans gants/temps réel imposés, arme entière visible à chaque instant, exécution ajoutée, effacement de l'historique. Les documents eux-mêmes divergent sur le rythme : une récupération brève peut entretenir la continuité sans ramener les personnages à une garde neutre entre chaque geste. Le prompt envoyé au générateur doit être autonome sans effacer la conversation de l'atelier.

## UX proposée

Un choix **Orientation du combat**, avant la création du prompt :

| Choix | Effet sur la préparation |
| --- | --- |
| Libre / mixte (défaut) | Base générale actuelle ; pouvoirs, contrastes de styles et armes éventuelles suivent l'intention. |
| Corps à corps | Appuis, esquives, prises, contacts et réactions corporelles, sans imposer gants ou tenue. |
| Armes | Portée, prise, trajectoires, récupérations et angles adaptés aux armes réellement demandées. |

**Un contre plusieurs** reste une configuration transversale, compatible avec chaque orientation. Pour une première version, l'intention suffit à la demander ; pas de second sélecteur obligatoire ni de classificateur LLM séparé. Une consigne conditionnelle compacte guide alors la gestion des assaillants, avec effets de zone autorisés si le genre les demande. Ne pas transformer la recommandation « un ou deux au contact » en plafond absolu pour les attaques de foule fantastiques.

Le choix est enregistré avec l'atelier et conservé dans les échanges, la réouverture, la conversion et la continuation. Les contrôles actuels Action / Plans / Caméra / 1–2–3 appels restent indépendants. L'intention précise armes, pouvoirs, nombre d'adversaires et arc dramatique sans exiger une liste de techniques.

## LoRA et isolation

L'orientation change les consignes de préparation, pas le workflow ComfyUI. Une suggestion modifiable peut rapprocher Armes de Weapon Combat et les autres orientations du LoRA Combat V2 disponible, sans changer silencieusement le LoRA ni ses forces. Les noms de fichiers ne doivent pas déterminer implicitement un contrat de prompt ; un éventuel raccordement utilisera les identifiants de ressources explicites de l'application.

Proposition de version **Combat 1.2.0** : même socle Combat à versions exactes pour identité, caméra, structure et révisions ; petit bloc propre à l'orientation choisie et règle conditionnelle foule. Ne pas injecter les trois manuels entiers, ni créer trois copies divergentes de l'application. Classique reste isolé ; Combat 1.1.1 et antérieurs restent disponibles. Aucune nouvelle passe LLM imposée.

Prochaine étape : tests préparés à exécuter par l'utilisateur, puis comparaison à références, seed et réglages identiques. Les conseils de LoRA sont affichés sans modifier automatiquement les réglages.
