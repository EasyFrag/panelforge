# Deux relances à 2 MP — lecture des résultats du 29 septembre 2026

Demande : comparer les deux essais réellement lancés par l’utilisateur, donner un avis sur la dégradation. Inspection des images et journaux uniquement ; aucun réglage applicatif, appel LLM, rendu, test ou redémarrage effectué.

## Résultats examinés

Parcours : `journey-323a50895e5f5c72bf755375b6070023`.

| Édition | Résultat initial à 1 MP | Relance à 2 MP |
| --- | --- | --- |
| Porte | asset-d4ee438c91b349e4a76c0bdeb091ecf7 | asset-9b4d4fcd383d4496b715b1f60cc28836 |
| Deck | asset-6f66726c62cf46b0bad5148d31e33ae7 | asset-49b446f6fd75431ea1f05fb5ce1d0c8d |

Les deux relances sont terminées avec succès. Leurs workflows exécutés ont été comparés aux témoins : mêmes prompts, mêmes assets d’entrée, mêmes seeds, mêmes modèles nommés, 18 steps, finition raw et sorties 2016 × 3584. Les seuls écarts de graphe sont le nom du fichier téléversé, le préfixe de sortie propre à l’essai et la cible du redimensionnement de référence, passée de 1 à 2 MP. Cela vérifie le traitement demandé dans le graphe ; la taille effective après tout traitement interne au nœud distant n’a pas été mesurée.

## Avis visuel

Comparaison de six vues complètes (source/1 MP/2 MP pour chaque édition), puis des mêmes régions d’écorce et de racines/mousse. Les images sont ramenées à une échelle commune pour cette inspection ; aucun filtre d’accentuation ou de correction de couleur n’est appliqué aux planches.

- **Porte : préférence pour le 2 MP.** Certaines fissures et irrégularités du tronc restent plus fines ; les grandes plaques et contours semblent moins simplifiés que dans la version 1 MP. Le rendu s’écarte pourtant encore du départ : les microtextures deviennent plus régulières, les creux se renforcent et certaines nuances se perdent. La forme de l’encadrement de porte change aussi, malgré le même prompt et la même seed.
- **Deck : amélioration partielle à 2 MP.** L’écorce centrale reste plus proche de sa source que dans le témoin à 1 MP, où les grands contrastes et les reliefs artificiels sont plus marqués. La mousse et les racines présentent encore une accentuation et un durcissement des ombres. Le 2 MP ne conserve pas intacte la matière de départ.
- Les deux observations vont dans le sens d’un bénéfice de la référence plus détaillée. Ce jugement visuel sur deux éditions, avec une seed par édition, ne suffit pas à mesurer la contribution relative du plafond ni à garantir une séquence longue sans dérive. Ne pas annoncer que le 1 MP est démontré comme cause unique ou principale.

## Limite déterminante : deux éditions indépendantes

La relance de la porte part de l’original `asset-bf2cf354ecc0464bb427772beeeddd7e`.

La relance du deck part encore de **l’ancienne porte à 1 MP**, `asset-d4ee438c91b349e4a76c0bdeb091ecf7`. Elle ne part pas de la nouvelle porte `asset-9b4d4fcd383d4496b715b1f60cc28836`. C’est le comportement du contrôle de comparaison livré, qui gèle la source de chaque édition pour isoler l’effet immédiat du réglage.

Ces essais mesurent donc original → porte à 1 ou 2 MP, puis ancienne porte → deck à 1 ou 2 MP. Ils ne mesurent pas encore original → porte 2 MP → deck 2 MP. Le défaut déjà présent dans la source de la deuxième relance reste un facteur hérité.

## Suite proposée, non lancée

L’essai suivant le plus informatif serait de réutiliser la nouvelle porte à 2 MP comme source du deck, en conservant le prompt, la seed et les autres paramètres de son édition, avec une référence à 2 MP. Cela complèterait une courte branche entièrement à 2 MP, comparable à l’ancienne chaîne 1 MP. Ne pas ajouter simultanément une seconde référence ou changer l’interpolation ; ne pas transformer cette proposition en garde-fou qualité.

Planches et provenance : `D:/Code/panelforge/.agent/diagnostics/image-journey-2mp-review-20260929/` : `overview.jpg`, `bark-step-1.png`, `bark-step-2.png`, `roots.png`, `evidence.json`. Les planches servent à inspecter les images, sans modifier les assets source.
