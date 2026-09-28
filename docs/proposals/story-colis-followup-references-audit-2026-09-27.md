# Audit — suite du Colis et références — 27 septembre 2026

## Périmètre et verdict

Audit du scénario, de la préparation de suite, des appels enregistrés, du code d’héritage et des fichiers d’images. Aucun rendu vidéo/audio examiné. Aucun code applicatif, prompt archivé ou état runtime modifié ; aucun test, appel LLM, génération ou redémarrage lancé.

- Source : story-0c1422ce9a55463c8529e254a4bc273d ; fabrication episode-1bbc0a1095a748a69297bfd742388435.
- Suite : story-a6477c1b50144d963f3fd9cd73f72669 ; titre Le carton vide, scénario Le retour du carton ; fabrication episode-e4af7379809b4de1a4f91604bb921ea4.
- Préparation : followup-13f603bf528ce89237a415e47cb5bd6c.
- Expérimentale v2 confirmée dans le chat et les trois appels d’écriture : experimental-2026-09-27, politique 2, recette révision 9, empreinte 5e5d92d7359b57e2434a39a99c5b10c22e7f5139a28d5673f37c2f90ec0a0ca1. Aucune ancienne édition utilisée par erreur.
- Parent correctement renseigné ; les deux fabrications utilisent visual_state_policy=2. Nino seul a une provenance inherited_image.

## Reprise des références

Episodes._inherit_character_images appelle EpisodeStateImages._inherit_sparse_image. Après rapprochement de l’identité, la reprise exige appearance_key(actual) == appearance_key(wanted). La clé normalise NFC, casse et espaces, mais pas les apostrophes ni les reformulations. Les images sources étaient disponibles avant la création de la suite.

| Référence | Comparaison observée | Conclusion |
| --- | --- | --- |
| Nino | Apparence et vêtements exactement conservés | Image héritée correctement. |
| Sacha | Unique différence : boucles d'oreilles devient boucles d’oreilles. Même tenue. | Faux changement dû à une apostrophe. |
| Colis de luxe | Référence source : carton fermé, ruban intact. Suite : même carton ouvert, ruban écarté, partiellement vidé. | Vrai changement visuel ; conserver l’identité, dériver une image ouverte du carton validé si nécessaire. Aucune image ouverte dédiée n’était sélectionnée dans l’épisode 1. |
| Montre dorée | Ancienne base : apparence structurée null/null. Variante : montre sur la paume, bracelet visible. Suite : même montre, cadran clair, tenue dans la main. | Le texte mélange identité et mise en scène. Aucune paire ne passe l’égalité stricte, sans transformation réelle de l’objet. |

Sources : src/panelforge/application/episodes.py:62 ; src/panelforge/application/episode_state_images.py:129 ; src/panelforge/domain/story_reference_plan.py:19 ; src/panelforge/domain/episode_continuity.py:159.

La protection conservatrice reste nécessaire pour éviter un retour au corps initial après grossesse ou musculature. Un héritage fondé uniquement sur le nom serait une régression.

## État actuel des fichiers

Les références de Sacha, du colis et de la montre sont désormais renseignées par import. Vérification SHA-256 des octets des content.bin : elles sont strictement identiques à leurs images de base dans l’épisode 1. Les nouveaux IDs ne signifient donc pas de nouvelles générations. Nino partage directement son asset source.

| Élément | Asset source | Asset actuel |
| --- | --- | --- |
| Sacha | asset-003ded3e179843c681ae72aad1c95e68 | asset-3c5f0d486c6e48c6bf39b6e4b31a7cb8 |
| Colis | asset-e74647a28dcf475cb8fb4c0b3ada3ffc | asset-560e6e97619c435f99c2252d2adc3307 |
| Montre | asset-a931551b204449e5bea9afb83a411724 | asset-ade19bda33d34ea396c61be290e44c7b |

Cela confirme les fichiers repris, pas l’exécution finale des gestes. Le carton réimporté est celui préparé initialement comme fermé, alors que la suite le demande ouvert. Ne pas écraser ces sélections.

## Défaut distinct de fusion des états

Avertissement enregistré : « La mémoire visuelle précédente n'a pas pu être reprise entièrement : Deux états de Sacha désignent la même étape. »

Le rédacteur conserve l’ID inherited-9dc0436464755f52 et le place à la première apparition de Sacha, scène 4 (indice 3). La mémoire précédente porte ce même ID à l’ouverture (indice 0).

story_continuity.inherit cherche uniquement un état au début de la scène 1. En son absence, il insère l’état antérieur, sans reconnaître l’ID déjà présent à la scène 4. Le normaliseur refuse les deux occurrences du même ID. Le message « même étape » masque ici une collision d’ID sur deux indices différents.

story_contracts abandonne alors la fusion, conserve le registre valide du rédacteur et ajoute un avertissement. L’apostrophe différente demeure et échoue ensuite à la reprise d’image. La collision et la comparaison textuelle sont deux défauts distincts : corriger un seul ne suffit pas.

Sources : src/panelforge/domain/story_continuity.py:238, insertion ligne 267, unicité ligne 95 ; src/panelforge/domain/story_contracts.py:359.

## Qualité du récit

Cinq clips de 10 s. Progression lisible : retour du carton, propriétaire constatant le manque, justification de Nino, revendication de Sacha, menace d’appel à la police. Les dialogues finaux sont français. Mme Delcourt et le palier constituent des références nouvelles nécessaires.

Réussites : conséquence extérieure, trois rôles clairs, même enjeu matériel, entrée de Sacha visible avec la montre.

Limites :
- L’aveu reste faible : Nino dit déjà que le colis était devant chez eux, puis « C’était chez nous. Sacha et moi on a trouvé ça ». Il ne reconnaît pas clairement l’ouverture ou le vol. Le résumé affirme une bascule plus nette que les paroles.
- Nouvelle fin suspendue, mais elle était explicitement fixée par la proposition automatique de suite avant conception. Le rédacteur respecte son brief ; améliorer cette dynamique implique aussi la proposition de suite.
- Le ton est oral/familier, moins cru et peu comique malgré le même profil. Favoriser l’invention des tactiques plutôt qu’un quota de vulgarité.
- Dix secondes sans dialogue pour marcher et frapper représentent un cinquième du format. Choix de tension possible, coûteux pour une comédie rapide ; à évaluer sur le rendu.
- Petit raccord : l’épisode 1 dit « Mme Delcourt, pas notre rue », la suite place sa porte sur le même palier. La source avait déjà des indications d’adresse ambiguës.

La relecture s’attarde sur le carton tenu par Mme Delcourt plutôt que par Nino, détail provenant du plan, tout en le laissant indicatif. Elle repère moins bien la faiblesse de l’aveu. Les remarques sur Sacha mentionnée hors champ ne justifient pas de l’ajouter au casting.

## Appels et coût

| Étape | Durée | Entrée | Sortie, raisonnement inclus |
| --- | --- | --- | --- |
| Conception | 216,766 s | 10 533 tokens | 22 076 tokens |
| Rédaction | 435,999 s | 14 104 tokens | 24 630 tokens |
| Relecture | 155,088 s | 8 740 tokens | 7 288 tokens |

Écriture : environ 13 min 28, trois appels acceptés, aucune correction/reprise/troncature. Proposition de suite préalable : environ 26 s supplémentaires. Chat : unsloth/Qwen3.8-27B-GGUF ; écriture/relecture : HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF.

Débits moyens sortie/durée, préremplissage inclus : environ 102, 56,5 et 47 tokens/s. Ces mesures ne prouvent pas un offload RAM ou une anomalie GPU. La rédaction comporte environ 12 241 mots de raisonnement enregistré ; les traces montrent des vérifications répétées de structure, IDs, scènes et états, pas une boucle applicative.

Contexte de rédaction : environ 42 749 caractères. Les deux champs historiques occupent environ 23 514 caractères sérialisés : previous_story_read_only demeure une chaîne JSON ; previous_episode_read_only contient le scénario entier et son registre. Le registre hérité arrive aussi séparément. Du contexte reste à simplifier pour les suites. Le modèle hésite également sur episode-1 présent dans l’ancien et le nouveau projet malgré la portée explicitée. Aucun gain de vitesse de v2 n’est établi par cet essai, non comparable à intention constante à l’épisode 1.

## Correctif à discuter

1. Fusion idempotente : reconnaître un état déjà transmis même si le personnage arrive plus tard. Tolérance typographique pour l’héritage ; attention, appearance_key produit aussi des IDs persistants, ne pas renuméroter les anciennes références en changeant globalement cette clé.
2. Séparer identité/référence validée de position, détenteur et gestes. Même montre dans la main ou la poche = même identité ; vrai changement de corps/tenue = variante explicite. Pas de rapprochement sémantique hasardeux entre objets.
3. Dériver les vrais nouveaux états depuis l’image précédente. Ici, si nécessaire, carton ouvert à partir du carton fermé, avec provenance et choix explicites.
4. Afficher la raison : Héritée de l’épisode 1 / Variante nécessaire : colis ouvert / Nouveau personnage. Aucune génération à l’ouverture de la fabrication.
5. Séparer le correctif technique des évolutions éditoriales : progrès local de la suite, aveu réellement joué, contexte historique moins redondant. Tout changement de prompts doit créer une nouvelle édition en préservant v1/v2 archivées.

Aucun correctif implémenté pendant cet audit.
