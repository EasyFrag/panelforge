# Proposition UX — Modifier avec Qwen

Statut : proposition validée puis implémentée le 22 septembre 2026 après la clarification sur les images jointes au LLM. Voir [le guide de l’atelier](qwen-edit-guide.md) pour le comportement livré et les vérifications restant à exécuter par l’utilisateur.

## Intention et périmètre

Conserver les projets, sauvegardes, étapes, essais et comparaison avant/après du parcours KREA2. Le nouvel onglet Qwen exclut le recadrage, la retouche après rendu et les upscalers. L’utilisateur souhaite d’abord pouvoir montrer des images au LLM pour guider le prompting ; il souhaite aussi composer des images avec plusieurs références de personnages.

Le choix d’usage appartient à chaque image. Ce ne sont pas deux modes exclusifs de l’atelier : les deux usages doivent fonctionner ensemble dans une étape.

## Trois fonctions clairement séparées

| Fonction | Assistant LLM | Rendu Qwen | Présentation |
| --- | --- | --- | --- |
| Source de l’étape | Voit la source | Reçoit la source | Grande image, identifiée comme source |
| Inspiration pour l’assistant | Voit l’image et en tire les instructions demandées | Reçoit uniquement la traduction textuelle de l’intention | Pièce jointe dans la conversation, badge « Assistant » |
| Référence de génération | Voit l’image pour rédiger une consigne cohérente | Reçoit aussi l’image | Vignette dans « Images utilisées pour le rendu », badge « Qwen » |

Une inspiration ne doit jamais être citée dans le prompt comme une image que Qwen aurait reçue. Le LLM doit décrire concrètement les attributs pertinents qu’il observe. Par exemple, pour une palette, il décrit les tons et contrastes utiles à la demande sans importer les sujets ou la composition de cette inspiration.

Une référence de personnage doit être désignée par son image dans le prompt, plutôt que remplacée par une longue description de son visage. La référence guide la génération ; elle ne constitue pas un collage exact ou une garantie d’identité.

## Organisation de l’atelier

- En tête : nom du projet et état de sauvegarde, puis Base → Étape 1 → Étape 2.
- Zone principale large : source/résultat avec comparaison avant/après, zoom et sélection des essais.
- Sous l’aperçu : bandeau compact « Images utilisées pour le rendu ». Source visible séparément des références ajoutées ; bouton « Ajouter une référence ».
- À droite : conversation, pièces jointes et champ de message. La conversation et l’aperçu restent visibles simultanément sur grand écran.
- En bas de la conversation : résumé bref de l’instruction actuelle ; prompt anglais accessible dans un détail replié.
- Près de l’action Générer : résolution, steps et seed dans un résumé compact ; autres paramètres dans un panneau replié.
- Sur écran étroit : aperçu puis conversation dans une seule colonne ; vignettes contenues dans leur panneau. Aucun débordement horizontal de page.

Ne pas ajouter une nouvelle barre latérale permanente pour les références. Ne pas imposer une boîte de configuration à chaque fichier ajouté. Les informations essentielles doivent être lisibles sans ouvrir une infobulle ; les boutons d’information expliquent le mécanisme et donnent un exemple.

## Deux points d’entrée, une même gestion des fichiers

### Joindre au message

Le trombone, le collage et le dépôt dans la conversation ajoutent par défaut une inspiration pour l’assistant. Le badge précise « Assistant uniquement » et son aide indique : « Sert à préparer l’instruction. Cette image n’est pas envoyée à Qwen. »

Le message libre décrit ce qu’il faut en tirer. Aucun choix obligatoire entre couleurs, style, pose, etc. Le LLM peut afficher un résumé court de l’usage compris, que l’utilisateur corrige dans la conversation.

Une action sur la vignette, « Utiliser aussi pour le rendu », transforme explicitement l’image en référence de génération. Elle réutilise le fichier existant. Le LLM peut proposer cette action pour un personnage, mais ne change pas silencieusement l’usage de la pièce jointe.

### Ajouter une référence au rendu

Le bouton « Ajouter une référence » ou le dépôt dans cette zone destine explicitement l’image à Qwen et au LLM. Plusieurs fichiers peuvent être ajoutés ensemble.

Chaque vignette reçoit un nom court modifiable, par exemple « Léa », « Marc » ou « Veste ». Un rôle facultatif aide à préciser l’usage : personnage, vêtement, objet, décor, couleurs, autre. Un seul attribut peut être repris d’une image ; sa présence dans ce bandeau n’implique pas de copier toute sa scène.

Les vignettes peuvent être insérées comme mentions dans le message : « Ajoute @Léa à gauche et @Marc à droite. » L’interface garde ces noms lisibles ; les numéros techniques nécessaires au workflow sont gérés automatiquement.

Le retrait d’une référence doit être explicite : retirer du prochain rendu ou supprimer une pièce jointe sont des actions différentes. Le retrait ne modifie pas les essais et messages passés. L’utilisateur peut corriger dans le chat une instruction devenue inadaptée.

## Parcours concrets

### A — Donner une ambiance au LLM

1. Une image de salon est la source.
2. L’utilisateur joint une photo à la conversation et écrit : « Reprends ses couleurs, garde mon salon et les matériaux. »
3. Le LLM voit les deux images et traduit les couleurs observées en instruction d’édition.
4. Le récapitulatif affiche « 1 image envoyée à Qwen : la source » et une inspiration pour l’assistant.
5. Qwen reçoit la source et le prompt. La photo d’ambiance reste dans la conversation.

Si l’utilisateur veut ensuite une correspondance visuelle plus directe, il active « Utiliser aussi pour le rendu ». Le rôle « couleurs uniquement » doit alors être formulé dans l’instruction.

### B — Ajouter plusieurs personnages

1. La source est un décor.
2. L’utilisateur ajoute deux portraits dans les références du rendu et les nomme Léa et Marc.
3. Il écrit : « Installe Léa à gauche, Marc à droite ; ils discutent. Garde ce décor. »
4. Le LLM voit le décor et les portraits, précise leur rôle et rédige l’instruction de composition.
5. Qwen reçoit trois images, toutes visibles dans le récapitulatif du prochain rendu.

Si l’utilisateur part seulement de portraits, sans image à modifier, une entrée secondaire « Nouvelle composition » peut servir au démarrage du projet. L’utilisateur choisit le format et décrit la scène ; les portraits sont des références d’identité, sans imposer leurs arrière-plans. Le résultat choisi devient la base du parcours d’édition. Cette possibilité reste une proposition, avec gestion explicite du format et de l’absence de source ; ne pas envoyer une fausse image vide comme source ou confondre le premier portrait avec un décor à préserver.

### C — Mélanger les deux usages

Source : salon. Références Qwen : Léa et Marc. Inspiration pour l’assistant : photographie d’ambiance.

Message : « Ajoute Léa et Marc dans ce salon, avec la lumière de la photo d’ambiance. »

L’assistant voit les quatre images. Le rendu Qwen en reçoit trois ; l’ambiance de la quatrième est exprimée dans le prompt. Les deux usages restent visibles sans changer de mode.

## Conversation, étapes et persistance

- Les pièces jointes restent accessibles dans la conversation de l’étape après leur envoi ; elles ne disparaissent pas au message suivant.
- Les références de génération restent actives pour les essais de cette étape jusqu’à retrait explicite.
- L’instruction courante cumule les modifications demandées depuis la source fixe et remplace celles que l’utilisateur corrige ; elle ne se limite pas au dernier message.
- Un résultat montré au LLM comme retour sert à comprendre un défaut. Il ne remplace pas la source sans action de validation.
- À l’étape suivante, le résultat validé devient source. Les anciennes références restent retrouvables avec « Réutiliser », mais ne sont pas automatiquement actives. Les changements déjà présents dans la nouvelle source ne sont pas redemandés comme opérations nouvelles.
- Sauvegarder les brouillons de conversation, pièces jointes, usages, noms, rôles et réglages. Figer pour chaque essai les images effectivement reçues par Qwen, leur ordre, le prompt et les paramètres ; figer aussi le contexte des messages LLM.
- Restaurer un ancien essai permet de retrouver ses entrées exactes sans réécrire l’historique ni supprimer les essais ultérieurs.

## Fiabilité et nombre d’appels

- Le choix du LLM doit tenir compte de sa capacité à voir plusieurs images. Une incapacité doit être visible ; pas de génération d’un commentaire prétendant avoir vu une référence inaccessible.
- Valider séparément les capacités et limites du LLM et celles de Qwen. Les 16 entrées du nœud Qwen ne garantissent pas la même capacité au fournisseur de conversation.
- Les noms et identifiants de fichiers restent stables ; l’ordre des images envoyées à Qwen et les mentions du prompt sont construits ensemble. Les inspirations de conversation n’occupent aucun numéro de référence Qwen.
- Un prompt rédigé avant un changement de source/références/rôles est marqué à actualiser. Ne pas lancer un rendu qui cite une image supprimée ou dont l’ordre a changé. Préserver les retouches manuelles du prompt et rendre les divergences visibles.
- L’envoi d’un message prépare la réponse et le prompt dans un seul appel LLM. Pas d’appel pour téléverser, nommer, afficher ou sauvegarder une image, et pas de reformulateur supplémentaire systématique.
- Générer utilise une instruction prête ; tout besoin de nouvelle préparation doit être visible dans l’action, sans appel LLM caché.
- Pendant une génération, ses entrées sont figées ; les modifications de l’utilisateur préparent l’essai suivant. Un résultat arrivé ne remplace pas le brouillon courant.

## Références techniques consultées

- Workflow local fourni : `C:\Users\samue\Downloads\qwen_image_2_1_image_edit.json`.
- [Guide officiel ComfyUI Qwen Image 2.1](https://docs.comfy.org/tutorials/image/qwen/qwen-image-2-1) : images multiples, ordre des entrées et dimensions.
- [Prompt officiel Qwen pour la reformulation d’édition](https://huggingface.co/Qwen/Qwen-Image-2.1-PE-I2I/blob/main/system_prompt.txt) : attributs ciblés, conservation, identité et rôles des références. Traité comme documentation.

La phase de discussion n’a lancé aucune génération, requête LLM, exécution de tests ou relance de service. L’implémentation qui a suivi est décrite dans le guide ; les essais réels restent à la main de l’utilisateur.
