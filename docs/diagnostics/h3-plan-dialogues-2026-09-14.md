# Diagnostic H3 : rejets du Plan et dialogues, 14 septembre 2026

Lecture du journal `D:\Code\panelforge\workspace\llm_calls.json`, sans nouvel appel LLM et sans modification des recettes de prompt. Les identifiants ci-dessous permettent de retrouver les échanges exacts. Les scènes et leurs dialogues ne sont pas reproduits ici.

Tous les appels concernés ont reçu une réponse du modèle, terminée normalement. Le rejet survient ensuite dans la validation applicative du Plan de la recette FL2VA Sensuel à deux appels (`minimax.h3.fl2va.sensual.planned@1.0.0`). Le Plan était rédigé par Qwen local.

Heures locales Paris (UTC+2) :

| Appel | Heure | Constat |
|---|---|---|
| `llm-597a7846108941acb2c3b36df7c2c93e` | 10:50:21 | Aucune réplique dans `SPOKEN LEDGER`, deux répliques japonaises dans le Plan. Rejet : les répliques ajoutées doivent être en anglais. |
| `llm-f8cbdb83d40c457d9278bcde27ebc9ac` | 10:51:53 | Champ `reference_picture` contenant `<Picture 1>, <Picture 2>` ; le schéma n’autorise qu’un identifiant exact ou null. Erreur indépendante des dialogues. |
| `llm-269adf8029d74deab8d64309efc18a8e` | 10:55:22 | Nouveau rejet de langue, toujours aucune réplique reconnue comme imposée. |
| `llm-3d02223c99fa43df91a6951d7805356c` | 10:56:30 | Deux blocs de dialogue commencent par le mot `Japanese` sans les crochets attendus. Le normaliseur ne peut pas les rattacher exactement aux phrases du registre vocal. Rejet « Langue manquante ou ambiguë ». |
| `llm-3da0aecbfd4246b3b08a51900d27b0f6` | 11:04:14 | Plan accepté : deux répliques reconnues comme imposées, identiques aux phrases japonaises produites. |
| `llm-9c606f0f469340bca3d8287cc35cf04b` | 11:06:02 | Rédaction finale par Gemma acceptée. |

## Effet de la ponctuation

Dans les intentions des Plans rejetés, aucune paire de guillemets n’entoure les dialogues. Dans le Plan accepté à 11:04, quatre guillemets droits délimitent deux répliques ; il n’y a pas de parenthèses. Le code `extract_explicit_dialogues` reconnaît les guillemets droits, français et typographiques. Les parenthèses ne sont pas un délimiteur de réplique reconnu.

La politique vocale conserve les paroles explicitement imposées dans leur langue et leur ordre. Elle réserve l’anglais aux ajouts spontanés. Ici, les phrases demandées mais non reconnues comme citations ont été traitées comme des ajouts. Les guillemets expliquent donc la différence de traitement observée ; ils ne peuvent pas empêcher une erreur indépendante de référence ou de balise dans une autre réponse du LLM.

Deux rejets antérieurs à 10:45 et 10:47 concernent l’ajustement après rendu, pas la création du Plan : langue des ajouts, puis conservation exacte des paroles.

## Les quatre consignes éditables

| Composant | Moment d’utilisation |
|---|---|
| `plan.system` | Premier appel : construire le Plan JSON depuis l’intention et les références. |
| `writer.system` | Deuxième appel : rédiger le prompt H3 depuis le Plan approuvé. |
| `revision.system` | Demande facultative d’ajustement du prompt avant lancement du rendu. |
| `render.system` | Ajustement dans l’atelier de rendu, à partir du prompt courant et du retour utilisateur ; images de l’essai si elles sont jointes. |

Il s’agit de quatre usages, pas de quatre appels systématiques. Les recettes concernées gardent deux appels pour préparer un nouveau prompt. Intention, références, schéma et réglages sont ajoutés aux consignes lors de la construction de la requête. Les traces « Échanges LLM » montrent le message réellement envoyé.
