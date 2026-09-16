# Histoires — Brainrot narratif 1.0

Implémenté dans le checkout `.panelpatch` le 15 septembre 2026, sur demande.
Un nouvel espace **Histoires** est accessible dans le bandeau principal.

Correctif éditorial r2 du même jour : mélo frontal, fruits adultes et relations
cohérentes, sans jargon adolescent automatique. La recette initiale intacte passe
à r2 lors de sa première lecture avec le nouveau code ; r1 et les personnalisations
restent conservées. Une révision peut aussi actualiser les cartes de propositions
en même temps que le scénario, sans changer la sélection de l'auteur.
[Diagnostic et détails](diagnostics/stories-editorial-r2-2026-09-15.md).

Révision éditoriale **r3** : propositions fondées sur les actes et les enjeux,
développement illustré par deux micro-scènes complètes au format JSON, continuité
des objets et des connaissances, conséquences visibles et dialogues adaptés aux
clips courts. La discussion/révision suit la même direction. Le nombre d'appels,
le schéma et l'interface ne changent pas. Les installations r1/r2 d'origine passent
à r3 ; une personnalisation ou un retour explicite à une ancienne version est
conservé. [Détails et essai proposé](diagnostics/stories-editorial-r3-2026-09-15.md).

Trois familles éditoriales indépendantes sont disponibles : **Mélodrame fruits**,
**Sensuel light** et **Cru ++** (`story.explicit-hard@1.0.0`). Cru ++ possède ses
propres sources, champs de concepts et archive de révisions. Ses scénarios exigent
des participants adultes et ajoutent `sexual_state` à chaque micro-scène pour
conserver précisément positions et contacts déjà établis. Modifier ou activer une
révision Cru ++ ne change pas les recettes Fruits ou Sensuel light.

## Parcours

Le sélecteur LLM reprend celui des autres ateliers, avec **Local · Unsloth**.
Pour une nouvelle histoire sans préférence enregistrée, Local est coché et
`HauhauCS/Gemma4-31B-QAT-Uncensored-HauhauCS-Balanced-MTP` est préféré. Les choix
manuels Local/Serveur sont mémorisés séparément dans le navigateur. Une histoire
rouverte reprend son modèle enregistré, même si le catalogue arrive plus tard.
Un modèle absent reste indiqué indisponible ; il n'est pas remplacé silencieusement.

1. Choisir **Explorer des propositions**, demander une, deux ou trois histoires,
   donner éventuellement une idée puis lancer la proposition. Sans idée, la
   recette propose des conflits simples, antagonistes excessifs, escalades
   causales et retournements visuels. Une proposition unique est sélectionnée
   automatiquement ; avec deux ou trois propositions, le choix reste humain.
2. Comparer les accroches et ouvrir **Conflit et dénouement**. Choisir une piste
   ou discuter avec le LLM pour ajuster les propositions.
3. **Développer cette histoire** produit le scénario entier : personnages,
   décors, micro-scènes, actions, dialogues attribués et états de continuité.
4. Continuer la conversation pour réviser le scénario ou poser une question
   sans le modifier. Chaque résultat accepté garde une version récupérable.
5. Copier l'intention de chaque micro-scène, avec ou sans durée, ou télécharger
   le scénario en texte. Les répliques sont assemblées mot pour mot avec leur
   locuteur. Aucune caméra ni aucun nombre de plans n'est imposé par l'export.

Le mode **Suivre fidèlement un script complet** saute les propositions et appelle
directement le Rédacteur une seule fois. Le script source prévaut sur le ton par
défaut de la famille : le LLM le structure en fiches et micro-scènes sans changer
ses événements, sa fin ou ses dialogues. Pour les scripts au format scénario,
PanelForge extrait localement les blocs `LOCUTEUR` puis vérifie après l'appel que
toutes les répliques sont présentes mot pour mot, dans le même ordre, sans ajout.
Un écart refuse l'application du scénario et conserve le brouillon diagnostic.
Chaque réplique issue du script reçoit aussi un `dialogue_id` stable. Son texte
parlé reste seul dans `text` ; le canal (`spoken`, `voice_over`, `off_screen`,
`thought` ou `mediated`) et l'indication originale sont conservés séparément.
Les formes usuelles comme `VOIX OFF DE LÉA`, `LÉA (V.O.)`, `TOM [O.S.]` ou
`TOM — DERRIÈRE LA PORTE` sont ainsi comprises sans autoriser une paraphrase.

Le format initial vise six micro-scènes de dix secondes. Le volet **Format de
l'épisode** permet de choisir deux à douze scènes et cinq à quinze secondes par
clip avant création. Ce nombre est une cible d'écriture, pas un quota de plans.
Le modèle peut proposer un découpage différent ; l'interface affiche toutes les
scènes reçues. Le contrat accepte au maximum dix-huit micro-scènes.

Le parcours par propositions utilise un appel d'architecture puis un appel de
développement. Le parcours script utilise un seul appel de rédaction, avec les
échanges de discussion/révision à la demande. Aucun appel automatique de réparation
du JSON, de génération de fiche KREA2 ou de rendu vidéo n'est ajouté.
Le choix et la création des références visuelles, l'envoi automatique à H3/REF2V,
la file de clips, DLSS et l'assemblage de l'épisode restent les étapes suivantes.

## Persistance et consignes

- Projets : `workspace/stories/story-<id>.json`, sauvegarde atomique. Conversation,
  documents versionnés, modèle utilisé et dernier brouillon sont conservés.
- **Versions de l'histoire → Reprendre cette version** crée une nouvelle version
  à partir de l'ancienne ; les versions intermédiaires restent disponibles.
  Choisir une autre proposition archive le scénario précédent avant de repartir
  du nouveau choix. Un document restauré fait foi sur les anciens messages.
- **Consignes LLM** ouvre la recette indépendante `story.brainrot@1.0.0` dans
  l'éditeur existant : propositions, scénario, discussion/révision. Les changements
  enregistrés s'appliquent au prochain échange ; un appel commencé conserve la
  copie de ses consignes. Les recettes vidéo ne sont pas modifiées.
- Sources r3 lisibles : `prompt_sources/story.brainrot/1.0.0/editorial-r3/`
  (`concepts.txt`, `scenario.txt`, `revision.txt`). R1 reste à la racine, r2 dans
  `editorial-r2/`. Les
  personnalisations actives et leurs versions résident dans
  `workspace/prompt_recipes/story.brainrot/1.0.0/`. Une fois la recette initialisée,
  utiliser l'éditeur pour changer la version active, plutôt que modifier les
  sources initiales ou les archives dont les empreintes sont vérifiées.
- Sources Cru ++ : `prompt_sources/story.explicit-hard/1.0.0/`. Elles sont
  installées comme une recette séparée et restent éditables/versionnées depuis
  **Consignes LLM** sans propagation vers les deux autres familles.
- **Échanges LLM** affiche les demandes système/contexte, réponses et raisonnement
  fourni par le modèle. Les traces utilisent l'archive durable existante,
  associée explicitement à l'identifiant `story-*`, hors journal roulant.

## Chargement et erreurs

La liste LLM n'est demandée qu'à l'ouverture de cet espace, indépendamment de la
liste des projets. Une panne du serveur LLM n'empêche pas de relire, sélectionner,
restaurer ou exporter une histoire. Le dernier atelier et la dernière histoire
sont repris au rafraîchissement ; les retours non envoyés sont conservés dans le
navigateur quand son stockage est disponible.

Les appels s'exécutent en arrière-plan et continuent après navigation/refresh.
Une demande simultanée sur le même projet est refusée ; une répétition du même
identifiant de demande n'envoie pas un deuxième appel. Les écritures manuelles
vérifient la version du projet pour éviter d'écraser celle d'un autre onglet.
Après redémarrage du service, un appel inachevé devient « interrompu » à la
réouverture et peut être relancé. L'annulation prend effet quand le moteur rend
la main ; le verrou n'est pas libéré avant la fin effective du worker.

Un JSON invalide, tronqué ou contenant des références de personnages/décors
incohérentes n'écrase pas le scénario courant. Le brouillon est consultable et
la relance explicite. La cohérence narrative et le rythme réel des dialogues
restent à évaluer avec le modèle choisi ; ce patch ne prétend pas les garantir.

Correctif du 15 septembre : les virgules superflues avant `}` ou `]` sont tolérées
à la lecture des réponses Histoires, uniquement hors des chaînes de caractères et
après une valeur. Les dialogues et autres textes restent exacts. Aucun appel de
réparation LLM n'est ajouté ; les autres erreurs restent refusées et les traces
conservent la réponse originale. Les anciens brouillons ne sont pas appliqués
automatiquement. Charger ce correctif Python nécessite un redémarrage du Lab.

## Vérifications

Contrôles statiques Python, syntaxe JavaScript, câblage HTML et diff effectués.
Aucun test applicatif, appel LLM, rendu image/vidéo ou redémarrage exécuté.
Tests préparés pour exécution par l'utilisateur depuis le checkout actif :

```powershell
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_stories tests.test_stories_browser tests.test_lab_web tests.test_navigation_and_resource_preview_browser
```

Le test navigateur emploie uniquement une API simulée. Les régressions couvrent
les deux appels, sélection/persistance, copie exacte des dialogues, retour de
version, consignes actives, erreurs/troncature, concurrence/annulation/reprise,
et accès aux histoires quand la découverte de modèles échoue.

Pour une première installation de l'espace Histoires, redémarrer le Lab puis
actualiser la page pour charger les routes. Les changements enregistrés dans
**Consignes LLM** sont relus au démarrage de chaque échange, sans redémarrage.
