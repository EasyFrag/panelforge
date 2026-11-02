# Premières productions Petits hommes v8 — 29 octobre 2026

Analyse demandée après le premier rendu Éthiopie. **Aucun changement de preset ou de code, aucun test, appel modèle, rendu ou redémarrage lancé.**

Périmètre : quatre Plans et leurs quatre Prompts disponibles au dernier relevé du **29 octobre à 23:15:42, heure de Paris**. Une seule vidéo terminée examinée, via son image initiale et ses cinq images de contrôle : Éthiopie, rochers au-dessus du village. Les commentaires sur les trois autres scènes concernent les textes, pas leurs futurs rendus.

Les instantanés sont enregistrés dans `.agent/diagnostics/petit-homme-v8-productions-20261029/` : `snapshot.json`, `snapshot-final.json` et `ethiopia-render-evidence.json`.

## Éthiopie : la faible intervention est déjà choisie dans le Plan

Fiche `factory-d8d4ff4307bb434aaf727b497a5a2aa9`, session `prompt-2a651a492ed74be78df3309ce4b79173`. Appels Plan `llm-b2789b2b33bc404c9aa9c40a9cd0806f`, Writer `llm-d4bea8d0129c4c84ae0e59ace1ffd573` : recette H3 standard, révision 2.

Le Plan prévoit que la main arrive, presse la paroi, puis repart. Au contact, les fragments sont censés ralentir et s'arrêter à mi-pente. Ensuite, la falaise est annoncée stable après le retrait, sans action qui explique une modification persistante de la paroi. Les habitants se détendent, poursuivent leur travail et remercient.

Les **huit lignes d'actions du Plan sont présentes mot pour mot dans le Prompt, dans le prompt de la tentative et dans son `effective_prompt`**. Il n'y a donc pas de perte de l'intervention au Writer ou lors de la transmission au rendu. Parmi ces huit lignes, une seule décrit le geste utile sur la falaise : la pression de la paume. Les autres portent sur arrivée, effets annoncés, réactions, retrait et merci.

Les cinq images de contrôle, à 0, 2,521, 5,042, 7,562 et 10,083 secondes, montrent arrivée, contact contre la paroi et retrait. La poussière et la pente évoluent, mais aucune fixation, réparation ou transformation durable imputable au geste n'est clairement lisible. La vidéo est donc compatible avec la pauvreté de l'action prévue, sans que ces images permettent de mesurer précisément tous les mouvements ou de juger l'audio.

Le rythme du Plan réserve la première moitié à la descente et à l'appui, puis prévoit une pause, le retrait et le merci. Cette allocation favorise la présence de la main davantage qu'une intervention transformatrice.

## Pourquoi aucun accessoire n'est choisi

L'assortiment contient bien douze propositions, dont fermeture éclair, ventouse, pince à dessin, charnière et élastique. Il a été transmis au Plan. Le champ `variety_choice.objects` est vide avec cette justification :

> A collapsing rock face cannot be stabilized by any small supplied accessory

La petite taille n'est imposée nulle part dans la requête. L'échelle de la main est explicite, celle des accessoires ne l'est pas. Le modèle écarte donc l'assortiment à partir d'une taille qu'il a supposée. La liberté de choisir la main seule, répétée dans l'intention et les règles de variété, lui fournit ensuite une sortie facile.

Cela ne prouve pas que toute proposition du catalogue conviendrait à cette scène. Le défaut est de rejeter l'ensemble sur une hypothèse de dimensions absente des consignes.

## Les préparations suivantes

| Scène | Intervention prévue et conservée dans le Prompt | Évaluation du texte |
| --- | --- | --- |
| Grèce, fiche `cb5d…` | Paume verticale devant la vague ; impact contre la main puis déviation de la crête vers la mer. | Effet plus tangible qu'un simple appui : impact et déplacement de l'eau. La main reste cependant surtout un écran qui se place puis se retire, sans accessoire. |
| Grèce, fiche `a430…` | Éventail géant, balayage de l'écume et dégagement du passage. | Accessoire original et action visible. Mais la grande vague reste explicitement menaçante à la fin : le Plan traite une conséquence secondaire sans établir que le passage restera sûr. |
| Japon, fiche `0be…` | Prendre un tuyau existant, relever sa buse, orienter le jet vers la brèche du feu ; flammes transformées en braises, vapeur et sol mouillé. | Manipulation plus complète et résultat concret. Le Plan s'impose pourtant « acts a single time », lâche ensuite le tuyau et fait reprendre le jardinage alors que le feu subsiste plus haut. La continuité de la protection mérite d'être observée. |

Le dernier relevé inclut le Prompt japonais : il conserve la prise du tuyau, l'orientation du jet, l'extinction locale, le lâcher et le merci. Aucun effacement de l'action principale par le Writer n'est identifié sur les quatre fiches.

Trois Plans déclarent `objects=[]`, mais le Japon utilise un tuyau déjà présent. Le constat exact est **un seul accessoire nouveau choisi dans l'assortiment sur quatre Plans**, et non trois scènes sans aucun objet utilisé. L'échantillon est trop petit pour estimer une fréquence générale.

## Consignes à améliorer, sans modifier le H3 partagé

1. **Rendre explicite l'échelle des accessoires.** Ils peuvent être à l'échelle de la main, donc gigantesques pour les habitants. Ne pas les rejeter parce qu'ils seraient nécessairement petits. Ne pas fournir d'association objet-problème à recopier.
2. **Demander une intervention complète et décisive.** Un plan continu ne signifie pas un seul geste. Les gestes nécessaires peuvent se suivre pour une même solution ; arrivée, présence et retrait ne constituent pas à eux seuls l'intervention.
3. **Exiger un changement persistant lisible.** Montrer ce qui a changé et pourquoi le bénéfice subsiste une fois la main partie. Une phrase annonçant la sécurité ne remplace pas cette preuve. La causalité peut rester inventive et fantaisiste, mais elle doit être compréhensible visuellement.
4. **Prioriser le besoin principal.** Ne pas considérer l'aide accomplie si le danger restant annule immédiatement le résultat. Une aide logistique peut être utile, à condition que le bénéficiaire atteigne réellement une situation améliorée.
5. **Donner le temps à l'intervention.** Entrée et retrait brefs, majorité de l'action consacrée à l'opération et à son effet ; merci bref accompagnant l'activité finale. Conserver dix secondes, sans quota de gestes.
6. **Maintenir les moyens libres.** Dans l'expérimental, examiner les accessoires à une échelle adaptée avant de préférer la main seule. Celle-ci reste valable lorsqu'elle accomplit une transformation aussi lisible et pertinente ; aucun objet obligatoire ni quota ajouté.

Le H3 standard autorise explicitement plusieurs actions liées dans un même plan. Sa permission d'audace comporte aussi une invitation à ne pas multiplier les actions, et un exemple calme utilise un rythme lent. Cela peut favoriser la sobriété, mais ne démontre pas une cause unique et ne justifie pas de modifier le H3 utilisé par les autres ateliers. L'intention peut préciser que plusieurs gestes nécessaires appartiennent à une seule intervention, sans ajouter d'événement indépendant.
