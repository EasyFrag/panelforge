# Audit — langues des Petits hommes expérimentaux (27 septembre 2026)

Demande : connaître les langues acceptées par MiniMax et expliquer les remerciements
encore anglais. Audit en lecture seule du runtime, sans correction ni relance.

## Documentation officielle

MiniMax H3 annonce un support stable de 11 langues de dialogue : arabe, chinois,
anglais, français, allemand, italien, japonais, coréen, portugais, russe et espagnol.
Les autres langues sont prises en charge à des degrés variables. Cela concerne
H3 vidéo/audio, pas les modèles Speech/TTS.

- [README officiel, System Overview](https://github.com/MiniMax-AI/MiniMax-H3#system-overview)
- [Guide officiel Base, section 4.4](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/base-en.txt)

Le guide demande la langue et les mots exacts dans la balise vocale, sans traduire
les paroles. Hindi, proposé dans notre menu, et malais, pertinent pour une source
observée, ne font pas partie des 11 langues stables. Ne pas les qualifier
d'impossibles : leur fiabilité est moins documentée.

## Résultats observés

Sept fiches expérimentales, toutes en auto, dans le journal partagé. Leurs essais
H3 sont réussis et leurs attempt.prompt concordent avec le Plan et le Prompt usine.
Les cinq dernières préparations demandent déjà l'anglais avant le rendu.

| Nom | Fiche | Langue du Plan / prompt de rendu | Réplique |
| --- | --- | --- | --- |
| lieu de culte brisé | factory-967922a157964aa5ba6d3c889fe0bd1b | English | Thank you! |
| Pont brisé | factory-1551308557164c249472b75ecc6d32d2 | English | Thank you! |
| lieu de culte brisé | factory-89679e8369a4436cbdca562c5bcf987a | English | Thank you! |
| lieu de culte brisé | factory-182770065c1f419bb3672aa0af3de81a | English | Thank you! |
| Pont brisé | factory-28e974e15819489b9cd0df43a00e3278 | English | Thank you! |
| Pierre sur la route | factory-c1f9bd1f593743f7883ce9b0dc91e8f7 | French | Merci ! |
| Pierre sur la route | factory-e320add1eb794bf1907db395b4fc2c29 | French | Merci ! |

Les cinq Plans anglais justifient le repli par un lieu incertain et l'absence de
drapeau ou d'inscription. Le contexte transmis se limite à Pont brisé ou lieu de
culte brisé. Les deux Plans français déduisent à tort France de la langue du titre.

## Omission de transmission confirmée

imageButton transmet assetId, sourceId et name. La réception image conserve la
référence et son libellé ; le prompt KREA2 n'est pas repris. Le preset copie le nom,
les libellés et source_config.intention, vide ici. Les indices connus sont perdus.

Vérification par correspondance exacte entre output_asset_id de l'essai KREA2 et
config.references[0].asset_id :
- factory-c1f9bd1f593743f7883ce9b0dc91e8f7 : vêtements et paysage japonais explicites ;
  remerciement français décidé d'après le titre français seulement.
- factory-182770065c1f419bb3672aa0af3de81a : inspiration architecturale algérienne ;
  repli anglais, pays absent du contexte usine.
- factory-89679e8369a4436cbdca562c5bcf987a : motifs architecturaux malaisiens ;
  repli anglais. Le pays reste multilingue ; transmettre l'indice ne suffit pas
  à fixer une règle adaptée, et le malais n'est pas dans les 11 langues stables.

## Limite et suite

Aucune vidéo ni audio analysé. Les deux prompts français ne prouvent pas que H3
a effectivement prononcé Merci. Si ces vidéos parlent anglais, examiner leur
audio séparément.

Correction à envisager : capturer le contexte du bon essai image, distinguer pays
nommé, inspiration culturelle/architecturale et langue de rédaction du titre,
et clarifier les replis pour pays multilingues/langues hors support stable.
Le choix manuel Langue parlée est déjà disponible pour un nouvel essai ; changer
la langue nécessite un nouveau Plan/Prompt puis un rendu.

Aucun code, réglage de fiche, média ou service modifié ; aucun test, LLM, rendu ou
redémarrage lancé. Documentation et continuités uniquement.

## Discussion suivante — variété des langues et métadonnées PNG

Demande utilisateur : discussion uniquement. Pays évident : langue correspondante.
Sinon, pseudo-aléatoire parmi les 11 langues stables, orienté par l'ambiance :
Europe/française -> langues européennes ; Asie -> chinois/coréen ;
désert -> arabe ; Europe de l'Est -> russe/portugais selon son regroupement
créatif. Le portugais n'est géographiquement pas une langue d'Europe de l'Est.
Cela remplace la préférence précédente de repli systématique sur l'anglais.

Proposition à discuter : choix manuel prioritaire ; pays explicite dans le
contexte source avant l'ambiance ; groupe visuel lorsque le pays est indéterminé ;
tirage sur les 11 si aucun indice. Choisir une seule fois par fiche et conserver
la langue et la réplique aux étapes suivantes/reprises. Afficher la langue
résolue. Aligner ultérieurement le menu sur les 11 langues stables.

Vérification réelle de deux PNG immuables, digest SHA256 conforme :
- asset-06185fce98574cc287f6dc68f5cc9d3e : chunk texte prompt contenant le
  graphe ComfyUI ; PrimitiveStringMultiline contient le prompt japonais ;
  SaveImageKJ.caption contient un JSON avec prompt, canonical_prompt,
  art_direction et assisted_creation.intention, dont « Pays : Japon ».
- asset-7870780f18b743d88dc895456bd20ecb : même format, architecture
  algérienne/désert dans le prompt et « Pays : Algérie » dans l'intention.

Il s'agit de texte de provenance/création, pas d'une géolocalisation GPS.
L'extracteur recover_krea2_metadata voit le chunk mais renvoie prompt=None :
il reconnaît les textes littéraux de CLIPTextEncode ; ce workflow fournit des
liens vers des primitives et une caption structurée non exploitée par ce lecteur.
Les textes sont réellement présents dans les PNG. L'usine ne branche pas
cette récupération non plus.

Transmission proposée : retrouver l'essai KREA correspondant exactement à
l'asset ; utiliser prompt/intention de création et style, en privilégiant le
contexte figé lors du rendu plutôt qu'une intention de projet modifiée ensuite.
Pour un PNG importé sans projet, lire les métadonnées connues.
Transmettre le contexte pertinent avec sa provenance à la préparation vidéo,
sans injecter tout le graphe technique. Si les métadonnées ont disparu d'un
export, exploiter l'image ou le contexte saisi. Aucun nouvel appel LLM nécessaire
pour lire les métadonnées.

Aucun code ni runtime modifié ; aucun test, génération ou redémarrage.

## Logique des langues validée ensuite par l'utilisateur

L'utilisateur confirme : « ça me va comme logique, on est carré pour les langues ».
Cette validation remplace le regroupement exploratoire précédent :
- Langue manuelle prioritaire, puis pays explicite/évident.
- Asie de l'Est indéterminée : chinois, coréen ET japonais.
- Europe occidentale indéterminée : français, anglais, allemand.
- Europe du Sud indéterminée : italien, espagnol, portugais.
- Europe générique : ces six langues ; russe lorsque l'inspiration évoque l'Est.
- Russie/style russe : russe ; contexte arabophone ou désert sans autre indice : arabe.
- Le portugais relève du Portugal/Brésil ou d'une ambiance ibérique, pas de l'Est.
- Les 11 langues ont chacune des contextes de sélection, sans dépendre du seul
  tirage général. Pour les cas ambigus, favoriser les langues récemment moins
  utilisées dans le groupe, puis conserver le choix par fiche.
- Aucun indice : tirage sur les 11. Aucun quota global ne doit contredire un pays
  explicitement indiqué.

La logique est approuvée ; son implémentation n'a pas été faite pendant l'audit
des gestes qui suit.

