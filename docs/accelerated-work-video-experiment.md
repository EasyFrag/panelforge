# Essai proposé : travaux accélérés dans un tronc

Protocole de travail à discuter et à exécuter par l'utilisateur. Aucun asset ni rendu généré, aucune nouvelle recette vidéo implémentée.

## Références fournies

- Début : `C:/Users/samue/Pictures/Screenshots/Capture d'écran 2026-09-05 161811.png` — tronc massif couché au bord d'un torrent, canyon rocheux.
- Fin : `C:/Users/samue/Pictures/Screenshots/Capture d'écran 2026-09-05 161833.png` — ouverture rectangulaire creusée dans le tronc, intérieur sombre et copeaux sur les galets.

Le premier objectif observable est la réalisation de cette ouverture. Une maison entièrement aménagée ajouterait d'autres transformations non montrées par les deux images. Préparer des références propres, sans lecteur, bouton Play, texte ni bandeau du navigateur, au même ratio et avec un cadrage aligné. Garder les repères du tronc, de la montagne et de la berge ; la seconde capture est cadrée différemment.

## États et gestes

Ces jalons sont des propositions de mise en scène, pas une garantie d'exécution par H3.

| État | Changement du matériau | Action visible qui le produit |
| --- | --- | --- |
| A — intact | Écorce continue, pas d'ouverture | L'ouvrier se place devant la zone |
| B — tracé | Contour rectangulaire peint | Le trait apparaît derrière la buse du spray |
| C — entamé | Entailles localisées, premiers éclats au sol | Les impacts de hache détachent le bois au point de contact |
| D — ouvert brut | Cavité ouverte, arêtes irrégulières, tas de copeaux accru | L'ouvrier retire les morceaux détachés |
| E — fini | Pourtour lissé, cavité conservée | La ponceuse suit les arêtes, puis l'ouvrier s'écarte |

Décrire quelques gestes caractéristiques et leur conséquence visible. Éviter une liste exhaustive de coups ou des timestamps à la fraction de seconde. Chaque changement reste acquis à la phase suivante. Le spray marque, la hache détache, la ponceuse lisse : le matériau doit évoluer en fonction de l'outil actif.

Un seul ouvrier, mêmes vêtements, outils posés au même endroit. Les changements d'outil restent compréhensibles. Caméra fixe, perspective et lumière stables ; le torrent peut continuer à couler. Travail accéléré et compression du temps de chantier explicitement demandés. Le chantier doit rester lisible entre les gestes rapides.

## Premier essai conseillé

Isoler d'abord **B → C**, sur 8 secondes : contour déjà peint et écorce intacte au début, entaille partielle et quelques éclats à la fin. Garder l'ouvrier visible dans les deux images préparées. Cela réduit la préparation à deux états proches et permet de juger la causalité outil/bois avant la transformation entière.

Intention à coller dans H3 Base, recette à deux étapes, caméra 0, mouvements supplémentaires 0, vie de scène faible et audace 0 :

> Un seul plan fixe de 8 secondes, filmé comme un chantier en avance rapide. Le même ouvrier travaille sur le contour rectangulaire déjà peint sur le tronc. Il donne plusieurs coups rapides et lisibles dans une petite portion de ce contour. À chaque impact, des éclats se détachent du point touché, tombent et s'accumulent sur les galets. L'entaille s'approfondit progressivement jusqu'à l'état de l'image finale ; le reste du tronc garde sa forme et son écorce. Le torrent continue de couler, les rochers, la lumière et le cadrage restent cohérents. Les derniers gestes sont encore visibles à la fin du clip. Aucun autre outil ni aménagement n'est introduit.

Les étapes détaillées du Plan sont transmises sous forme de texte au rendu. Elles ne constituent pas de nouvelles images de conditionnement.

## Essai complet ensuite

Pour éprouver le suivi de plusieurs états dans un seul clip, proposer A → B → C → D → E en Ref2V à deux étapes : A en première frame, B/C/D en keyframes, E en dernière frame. Préparer les états intermédiaires en éditant une même base visuelle ; des générations T2I indépendantes ne garantissent pas le même décor.

Durée de départ proposée : 15 secondes. Répartition indicative : installation et spray 0–3 s, entailles 3–6 s, retrait de matière et ouverture 6–11 s, ponçage et dégagement de l'ouvrier 11–15 s. L'ouvrier reste unique, les outils changent explicitement et les dégâts/copeaux s'accumulent. Ces actions condensent volontairement un travail long.

Ref2V accepte plusieurs images dans le parcours local (jusqu'à 9). Les rôles temporels sont explicités par le prompt ; le workflow les transmet comme références, sans verrouillage indépendant de chaque timestamp. Un résultat conforme aux états mais obtenu par déformation globale du tronc ne suffit donc pas à valider la causalité recherchée.

Pour privilégier les extrémités de chaque transformation, l'autre approche est une suite H3 Base First/Last Frame : A → B, B → C, C → D, D → E. Le bouton existant de reprise depuis la dernière frame aide à poursuivre le résultat réel ; il ne garantit pas à lui seul l'identité du travailleur ni la continuité de vitesse. Comparer les quelques repères visuels fixes entre clips pour surveiller la dérive.

## Ce qui décidera de la suite

- Le bois change-t-il à l'endroit travaillé, avec contact outil/matière lisible ?
- Les entailles, cavités et débris persistent-ils au lieu de se réinitialiser ?
- Le décor et l'ouvrier restent-ils cohérents ?
- L'accéléré conserve-t-il une succession compréhensible des travaux ?

Conserver modèle, réglages et seed pour une première comparaison de formulation ; plusieurs seeds seront ensuite nécessaires avant d'attribuer un succès ou un échec au parcours. Si la succession complète échoue mais les transitions courtes fonctionnent, assembler les clips puis régler leur vitesse au montage constitue une piste. Aucun gain ni niveau de qualité n'est démontré à ce stade.

Sources consultées : [présentation officielle H3](https://www.minimax.io/news/minimax-h3-open-source) pour les variantes FL2VA/Ref2VA et leurs entrées ; [guide officiel Ref2V](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md) pour les rôles de première frame, keyframe et dernière frame. Les choix de découpage, durées et critères ci-dessus sont des propositions pour ce projet.
