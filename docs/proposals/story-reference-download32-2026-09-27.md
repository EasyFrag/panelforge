# Référence Download(32) — conséquences pour le preset comique

Date : 2026-09-27. Discussion uniquement, aucun patch moteur.

## Matériel effectivement examiné

- Vidéo fournie : C:/Users/samue/Downloads/Download(32).mp4, 42,666667 s, 576 × 1024, 24 images/s.
- SHA256 : 40fd4bd7bbec5b24e23d004782f0e84a4e10b96224b7908d87fd742e213f26b9.
- Images décodées toutes les deux secondes et planche examinée. Audio transcrit avec Faster Whisper large-v3-turbo installé, CPU int8 / 4 threads / mode hors ligne. Aucune génération ni appel au moteur LLM ; GPU non sollicité par cette transcription.
- Artefacts : D:/Code/panelforge/workspace/experiments/analyse-download32-2026-09-27 (source.json, overview.jpg, images extraites, reference.wav, reference.json, transcription.log).
- La transcription est automatique : argot, noms propres et prononciations caricaturales comportent des erreurs possibles. Les sous-titres visibles euphémisent certains propos ; ne pas les confondre avec une transcription littérale de l’audio.

## Progression observable

| Temps approximatif | Moment | Fonction |
| --- | --- | --- |
| 0–6 s | Le riche méprise le cireur ; celui-ci surenchérit dans la servilité. | Rapport de pouvoir et ton installés dans les premières répliques. |
| 6–9 s | Le portefeuille tombe ; le cireur le découvre, le ramasse et s’en réjouit. | Objet et tentation concrète, sans exposition longue. |
| 9–18 s | Le riche explique à sa compagne le test volontaire, la récompense possible ; Piccolo apparaît derrière elle. | Le public comprend davantage que le cireur ; l’exécutant est présenté avant d’agir. |
| 18–24 s | Le cireur veut investir dans les NFT, devenir milliardaire et, à son tour, être servi. | La frime exprime un désir de prendre la place du dominant. |
| 24–33 s | Colère du riche, appel, entrée spectaculaire de Piccolo par le plafond, ordre joué face à lui. | Cause visible de la correction à venir ; gag physique sur le même fil narratif. |
| 33–43 s | Marche sur le passage piéton, interception et correction ; le cireur annonce avoir tout perdu dans les NFT. | Dernière réplique qui retourne la vantardise précédente. |

Le fil principal reste très simple malgré les mots crus, personnages de pop culture, décors et exagérations. Les voix sont typées par leur position et leur désir. Le comique se situe aussi dans le mépris arbitraire du riche, l’obséquiosité excessive du cireur et son rêve de reproduire cette domination.

Différence avec Download(30)/(31) et notre brief : ici le portefeuille est délibérément laissé tomber, pas donné explicitement. Le choix de le garder devient un geste moralement interprétable par les personnages. La version du don assumait plutôt l’hypocrisie du riche. Ces deux mécanismes peuvent fonctionner ; ne pas les confondre ni réparer automatiquement le don s’il est voulu par l’auteur.

Le double rappel est particulièrement utile : cireur → rêve d’être servi ; investissement triomphal → aveu de perte. L’aveu final est parlé après la correction, il ne faut pas le remplacer par une explication abstraite dans les métadonnées.

## Rythme mesuré, limites comprises

Avec le même comptage lexical (apostrophes françaises conservées dans un mot), la transcription donne environ 164 mots sur 42,7 s, dont environ 34,4 s de fenêtres de parole : ~3,8 mots/s sur tout le clip, ~4,8 mots/s sur les fenêtres parlées. La précision est limitée par l’ASR.

Le scénario PanelForge story-53551c9387a74685886728a88a9db13d comporte environ 81 mots pour 50 s prévues. Le nombre 88 du précédent audit comptait les tokens séparés par espaces, y compris certains signes de ponctuation ; ce n’est pas une modification du scénario.

La référence contient donc environ deux fois plus de paroles en une durée plus courte. La politique fast de PanelForge autorise déjà 4,8 mots/s indicatifs. Le problème restant n’est pas uniquement le plafond : la rédaction produit encore très peu de paroles et des réponses passe-partout. Ne pas imposer un minimum de mots ni déduire une capacité garantie de H3 depuis cette seule référence.

Le tempo alterne des segments narratifs courts et des échanges plus denses. Cela inspire les intentions et plans internes au clip. Le premier patch proposé ne nécessite pas une refonte des durées/montage ni une migration de fabrication.

## Ajustements à la proposition de patch

1. **Ambiance comique complète.** Conception : choisir un ressort dominant adapté à l’idée (vantardise qui se retourne, quiproquo, double jeu…), le préparer et jouer sa conséquence. Garder la trame simple ; ne pas systématiquement inventer un test d’honnêteté ou une punition.
2. **Voix selon le désir.** L’écriture distingue domination, flatterie intéressée, frime et panique. Le lexique cru soutient ces intentions. Autoriser des échanges nourris et des réactions brèves ; éviter de réduire le registre à une interjection répétée.
3. **Rappel ou chute préparée quand cela sert l’histoire.** Un élément annoncé revient transformé. Le gag initial et la fin doivent se répondre dans le contenu réellement joué. Pas de nouveau champ obligatoire, quota de gags ou contrôle bloquant mécanique.
4. **Une scène, une idée lisible.** Entrée spectaculaire ou violence burlesque restent liées au conflit. Les gestes simples accompagnent la parole ; ne pas multiplier les accessoires/actions secondaires pour remplir les secondes.
5. **Relecture orientée spectateur.** Vérifier qui veut quoi, pourquoi le suivant agit et si le moment de chute est compréhensible. Préserver le ton cru demandé. Les exemples du preset ne deviennent pas des répliques imposées ; les diagnostics exacts locaux restent distincts des préférences de style.

Le profil est court et partagé intelligemment : conception reçoit mécanique/ton, rédacteur reçoit aussi petit lexique et quelques micro-échanges variés, lecteur reçoit les objectifs utiles de l’unité. Trois appels conservés. Aucun appel supplémentaire d’analyse vidéo dans les futurs projets : cette référence sert à concevoir le profil, pas à être renvoyée à chaque génération.

Ne pas transformer tous les détails de cette vidéo en règles : les vingt millions dans un portefeuille, les NFT, le passage piéton répétitif ou chaque figurant de pop culture ne sont pas obligatoires. Les apparitions décoratives ne nécessitent pas toutes des fiches personnages. Le principe se transpose aux humains réalistes avec Piccolo animé, comme demandé précédemment.

## Interface et essai

L’orientation déjà acceptée reste valable : idée courte, ambiance, univers visuel, durée, langue ; un panneau Personnaliser pour le reste. Le preset résout les réglages contradictoires et annonce le ton effectif. Aucun sélecteur supplémentaire pour chaque ressort comique.

Après accord et implémentation ultérieurs, l’utilisateur peut lancer une même idée courte deux fois, sans citations exactes ni découpage : juger lisibilité, voix, densité utile de dialogue et chute, puis vérifier l’audio rendu. Un second sujet différent permettra de voir si le moteur réutilise une mécanique au lieu de copier le portefeuille. Aucun essai lancé pendant cette discussion.
