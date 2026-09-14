# Analyse média → H3 : durées et échec de Plan, 14 septembre 2026

Diagnostic demandé, sans correctif ni relance. Lecture des données locales et
du code uniquement ; aucun contenu de scène ni média reproduit dans ce document.

## Deux essais bloqués avant le Plan

La dernière analyse `analysis-31ddfde6821745f6b6a66db8354fbba5` a réussi
(`llm-bda605532ed84833b25972835411396c`, 07:29 UTC). Extrait et durée cible :
12,95 s. Le service ajoute l'en-tête `Durée cible : 12.95 secondes.` et le
texte contient deux repères d'action : 6,66 s et 9,16 s.

`application/direct_fl2va_prompt.py` reconnaît `durée`, `durée totale` et des
formulations de durée de plan/clip, mais pas le qualificatif `cible`. La regex
prioritaire ne trouve donc aucune durée totale. Le repli considère alors toutes
les mentions numériques de secondes comme des durées possibles et en trouve
trois. `requested_h3_base_duration_ms` lève alors
`H3 Base intention contains conflicting explicit durations`.

Les compositions enregistrées confirment les étapes suivantes :

| Préparation | Création UTC | Mentions de secondes | État enregistré |
| --- | --- | --- | --- |
| `prompt-b1b230ee255e4751938f72733cea024f` | 07:30:42 | 12,95 ; 6,66 ; 9,16 | Aucun Plan, aucun Writer |
| `prompt-412eed3c7f3d4f3b9d1c3bc6bce56f1f` | 07:31:27 | 10 ; 6,66 ; 9,16 | Aucun Plan, aucun Writer |
| `prompt-0e3d19d7ace147c68c818a2370d4f763` | 07:31:58 | 10 uniquement | Plan puis Writer acceptés |

Le changement de durée totale seul ne résout pas le problème tant que les
repères demeurent. La troisième préparation ne les contient plus : Plan
`llm-a616bb69c34b47a89835a991aa5fc592` accepté, puis Writer
`llm-6e185badef5045b5931d0946bf453b91` accepté. La dernière préparation observée
n'a donc pas de rejet LLM du Plan ; le blocage précédent était dans la
préparation locale du contexte, avant envoi au modèle.

La dernière vidéo liée à cette préparation contient un essai réussi et un autre
marqué en cours au moment de la lecture. Aucun processus ou historique modifié.

## Correctif ciblé proposé

Reconnaître le libellé produit par notre propre analyse comme une durée cible
explicite. Les repères d'action ne doivent pas entrer en concurrence avec cette
durée ; deux véritables demandes de durées totales contradictoires restent une
erreur utile. Ne pas supprimer tous les timestamps, ni demander au modèle de
remplacer les repères précis par une description vague.

Cas hors ligne à couvrir au futur patch, avec scènes neutres : libellé cible
avec point/virgule et repères multiples, durées explicites compatibles ou
contradictoires, conservation des formulations historiques. Une transmission
structurée de la durée depuis Video Lab serait plus robuste à terme, mais
demande un périmètre plus large que la reconnaissance du libellé existant.

## Autre rejet du Plan encore présent dans le journal

Un rejet distinct date du **13 septembre à 19:25 UTC**, recette Classique
Mise en scène 1.0 : `llm-b156f188092a4068a43ac997ff8ced35`.
Le champ caméra de la seconde phase utilise `alongside the landing tiger`.
Le validateur accepte notamment `beside ...` et `along ...`, mais pas
`alongside ...`. Les consignes et le schéma exposés au modèle donnent quelques
exemples, sans communiquer la liste fermée effective. Le raisonnement conserve
justement une hésitation sur ce préfixe ; il ne s'agit pas d'une sortie tronquée.
L'erreur de liste de plans vide est une conséquence du rejet de cette phase.

La relance `llm-bd62bdb831504f9f9d626d797eeb48cf` (19:26 UTC) a produit
`along the sandy ground beside the landing tiger` et a été acceptée. Pour ce
cas, aligner explicitement la consigne/schéma Classique sur les préfixes
réellement acceptés serait une correction distincte. Ne pas assouplir tous les
validateurs ni changer les autres familles au cours d'un simple rangement.

Ce diagnostic distingue les deux essais de ce matin de cet ancien rejet.
Aucun nouveau rejet du Plan après la préparation de 07:31:58 n'était présent
dans le journal consulté. Aucun test applicatif exécuté et aucun appel LLM lancé.
