# Usine : tri des résultats et stabilité des prévisions — 28 septembre 2026

## Comportement

Dans le bandeau de sélection de Résultats, un sélecteur compact propose « Ordre habituel » (défaut) et « Plus récents d’abord ». Le second utilise les dates de fin des étapes/export, avec repli sur lancement/création si aucune date de fin valide n’existe. Les scènes d’une histoire restent regroupées dans leur ordre interne ; le groupe est daté par sa fin la plus récente. Les égalités gardent l’ordre initial.

Le choix reste actif pendant les actualisations et la navigation entre onglets, puis revient au défaut au rechargement complet. La sélection reste cochée. Le tri agit sur une copie destinée à l’affichage ; aucune commande de priorité ni modification de l’ordre serveur.

## Cause du clignotement et correction

L’ancienne clé de prévision mélangeait la sélection, les révisions des fiches, la révision globale de la file et un intervalle de cinq secondes. Chaque sondage ou progression d’un autre traitement vidait donc le résultat déjà calculé, retirait les durées des lignes et affichait « Estimation… », avant le retour de la requête.

Deux identités sont désormais séparées :

- Sélection/révisions des fiches : invalide réellement la prévision si le preset, les réglages, la sélection ou l’état de préparation changent.
- Révision globale/intervalle : déclenche un recalcul en conservant l’affichage connu.

Une requête lente pour la sélection courante peut terminer malgré les sondages suivants. Les réponses d’anciennes sélections sont ignorées. Une erreur transitoire conserve la dernière valeur, la signale comme ancienne et masque l’heure de fin ; l’erreur reste consultable en infobulle. Sans première valeur calculée, l’interface garde son état explicite d’attente/indisponibilité.

Le tableau refuse aussi un ancien état global reçu après une modification plus récente : un GET parti avant un changement de preset ne peut plus rétablir son ancienne révision.

## Fichiers et validation

- `static/video-factory.js` : tri d’affichage, sélecteur, protection contre les états anciens.
- `static/video-factory-monitor.js` : prévision conservée pendant l’actualisation et gestion des réponses concurrentes.
- `static/index.html` : sélecteur et nouvelles versions des deux scripts pour le cache. Modifications réseau concurrentes conservées.
- `tests/test_factory_preview_browser.py` : deux scénarios navigateur hors ligne, préparés pour l’utilisateur. Couvrent le tri, les groupes, la sélection, les dates manquantes/égales, l’actualisation, les réponses anciennes, les recalculs lents, les erreurs, le changement de preset et la désélection.

Contrôles effectués sans exécution applicative : syntaxe Python ; compilation V8 des deux scripts applicatifs et des trois blocs de scénario/initialisation ; sélecteur HTML unique, options et références de cache. Les tests fonctionnels/navigateur ne sont PAS exécutés conformément à AGENTS.md actif.

Commande de validation utilisateur depuis le checkout actif :

```powershell
$env:PYTHONPATH = "D:/Code/panelforge-krea2-flux/src"
D:/Code/panelforge/.venv/Scripts/python.exe -m unittest tests.test_factory_preview_browser tests.test_video_factory_web
```

Un rechargement de la page charge ces modifications d’interface : l’index est servi depuis le fichier avec Cache-Control no-store et les scripts changent de version. Aucun redémarrage backend, génération, commande de file, écriture runtime, commit ou push effectué.

Sauvegardes, diffs et contrôles : `D:/Code/panelforge/.agent/diagnostics/factory-results-preview-20260928/`.
