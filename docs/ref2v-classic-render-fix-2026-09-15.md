# REF2V Classique : raccordement au rendu

Le profil `minimax.h3.ref2v.classic.cinematic` était omis de la reconnaissance
REF2V au moment de créer le projet de rendu. Avec une première frame et une
référence sujet, le prompt était préparé pour REF2V, mais le projet devenait
I2VA et perdait l'image du sujet.

## Sauvegarde avant modification

État du Lab publié et vérifié avant le correctif : commit
[`608e312`](https://github.com/EasyFrag/panelforge/commit/608e312f91760ce5f70188ee005b94ac42a678b4),
branche `snapshots/avant-alignement-ref2v-2026-09-15`, tag
[`snapshot-avant-alignement-ref2v-2026-09-15`](https://github.com/EasyFrag/panelforge/tree/snapshot-avant-alignement-ref2v-2026-09-15).
Le snapshot inclut les travaux précédents KREA2 Assisted, DLSS et durée H3.
Le remote local et la branche principale GitHub n'ont pas été modifiés.

## Correctif

Version de livraison :
[`snapshot-ref2v-2026-09-15`](https://github.com/EasyFrag/panelforge/tree/snapshot-ref2v-2026-09-15),
branche `snapshots/ref2v-2026-09-15`.

- Le nouveau profil Classique est reconnu comme REF2VA. Toutes les références
  liées à la composition sont conservées dans l'ordre des `<Picture N>` utilisé
  par les deux appels LLM, y compris si les bindings réordonnent les images ou
  n'utilisent qu'un sous-ensemble des images de la session.
- Une première/dernière frame fournie dans REF2V reste une image de la liste de
  références, avec son rôle dans le prompt. Les champs de frames H3 ne sont pas
  utilisés pour ce projet.
- À la réouverture de la session d'origine, un projet Classique REF2V mal classé
  sans aucun essai est réparé en place. Son identifiant, son prompt courant,
  ses ajustements, ses modèles LLM et son historique de conversation sont conservés.
  La réparation ne relance pas les LLM et ne crée pas de nouvel essai.
- Un projet mal classé contenant déjà des essais n'est pas réécrit : un message
  demande une reprise dans un nouvel atelier REF2V, afin de conserver l'historique.
  Les lectures directes de l'historique restent disponibles.

La réparation est déclenchée par l'ouverture de l'atelier depuis sa session
(`/api/h3-render/projects/from-session/...`), pas par un balayage au démarrage.
Les données du workspace n'ont pas été modifiées par l'agent pendant le patch.

**H3 reste inchangé.** Le seul fichier fonctionnel modifié est
`application/h3_render.py`, dans `get_or_create_from_session`, avec des branches
spécifiques au nouveau profil REF2V. Les consignes, schémas, compilateurs, modèles,
workflows et interfaces H3/REF2V sont conservés. La différence de grammaire au
deuxième appel et à la compilation existe déjà ; aucun troisième appel ajouté.
Les parcours REF2V historiques, Combat et Sensuel conservent leur routage.

## Vérification

Contrôles statiques : syntaxe Python des trois fichiers modifiés/ajoutés, diff,
et absence de changement des sources de prompting, workflows et UI par rapport
au snapshot. Les tests applicatifs ne sont pas exécutés par l'agent, conformément
à `AGENTS.md`. Aucun LLM réel, ComfyUI, rendu ou redémarrage lancé.

Tests préparés pour l'utilisateur :

```powershell
cd D:\Code\localQ\.panelpatch
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_ref2v_classic_render_boundary tests.test_classic_cinematic tests.test_h3_render
```

Ils couvrent les deux appels avec réponses fixes et rédacteur distinct, la
grammaire mono/multi-plan, tous les rôles de références et jusqu'à neuf images,
l'ordre des bindings, la compilation de la recette actuelle REF2V 0.2.4, la
réparation et sa répétition sans nouvelle écriture, la conservation des anciens
essais et les quatre modes d'entrée H3. Le test d'intégration Classique existant
vérifie désormais explicitement le mode de rendu et ses références.

Pour reprendre le projet signalé : redémarrer le Lab, puis rouvrir sa session
depuis **REF2V**. Le prompt existant est réutilisable sans refaire le Plan ni la
Rédaction. Le panneau doit indiquer REF2VA et afficher toutes les références.
