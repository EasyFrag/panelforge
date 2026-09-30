# Usine mobile : historique thermique — 28 septembre 2026

## Résultat

L’accueil mobile regroupe PanelForge, l’état de connexion, l’actualisation, le titre Usine et l’état du lot dans un en-tête compact. Le résumé de progression, le temps restant et l’heure de fin restent présents.

Les deux cartes de température instantanée sont remplacées par deux courbes : Serveur en haut, PC local en dessous. Elles affichent les six dernières heures de l’historique existant, y compris avant l’ouverture de la page. L’échelle reste 40–90 °C, avec pic, minimum, seuil et signalement explicite des températures hors plage. Les valeurs hors plage sont dessinées à la limite de la zone ; le texte et la lecture au toucher conservent leur température exacte.

Tous les maxima enregistrés par tranches de 15 secondes sont conservés. Aucun lissage ni moyenne ne masque les pics. Les coupures supérieures à trois tranches (45 secondes avec les réglages actuels) interrompent les traits. Un toucher ou les flèches du clavier permettent de lire une mesure horodatée.

L’historique se recharge au plus toutes les 30 secondes, indépendamment de l’actualisation de la production toutes les 5 secondes. Une actualisation manuelle recharge les deux. En cas d’échec, les dernières courbes restent visibles avec une indication d’ancienneté / d’indisponibilité.

## Notifications

L’utilisateur a précisé qu’il devait probablement activer les notifications sur le téléphone et souhaite les retester ensuite. Le mécanisme d’abonnement/envoi existant est conservé ; aucune notification réelle envoyée ni diagnostic de livraison conclu.

Le formulaire propose désormais 84 °C pour le serveur (PC : 80 °C). Les seuils déjà enregistrés d’un abonnement restent prioritaires et peuvent être modifiés depuis Alertes. Les lignes de seuil et les alertes visibles utilisent ces mêmes préférences. Les protections thermiques et les paramètres d’ordonnancement ne sont pas modifiés.

La notification de lot terminé existe déjà et est conservée. L’activation reste explicite dans Alertes, avec autorisation du navigateur Android.

## Architecture et fichiers

- domain/factory_mobile.py : projection bornée à six heures, température/timestamps validés, doublons fusionnés par maximum, serveur avant local. Aucun événement de production, chemin ni erreur brute exposé.
- application/factory_mobile.py : fournisseur d’historique injecté, sans appeler le snapshot de production pour lire les courbes ; message sûr en cas d’indisponibilité.
- scripts/run_lab.py : réutilise machine_work.thermal_history du coordinateur existant.
- features/lab/factory_mobile_web.py : GET /api/thermal-history en lecture seule, route du composant thermique. La surface privée mobile existante demeure.
- static/factory-mobile/thermal.js : SVG natif responsive et lecture des points. Aucun ajout de dépendance.
- index.html, app.css, app.js et sw.js : accueil compact, chargement séparé de l’historique, cache de coque mobile2. Ni API ni médias ajoutés au cache du service worker.

## Vérifications

- Lecture seule de l’API PC : historique disponible sur 24 heures, résolution 15 secondes, données des deux machines présentes. Le mobile en extrait six heures.
- AST/compilation de six fichiers Python ; compilation syntaxique V8 de trois scripts et de deux blocs de scénario navigateur.
- Identifiants HTML uniques, références de cache cohérentes, structure CSS et git diff --check validés.
- Aperçu visuel statique avec données fictives, sans app.js ni appel API : émulation téléphone de 390 px, contenu de 390 px, courbe de 332 px. Capture consultée : mobile-static-preview-390.png dans le dossier de diagnostic.
- Quatre régressions backend préparées : fenêtre, pics, doublons, trous, invalides, non-mutation, projection sans données internes, endpoint en lecture seule et fournisseur indisponible.
- Scénario navigateur existant étendu : ordre des courbes, seuil 84, débordements thermiques, lecture d’un point, conservation après erreur et récupération ; commandes de production et navigation conservées.

Tests fonctionnels et navigateur non exécutés conformément à AGENTS.md actif. L’aperçu n’est pas une validation de la liaison avec l’application en cours ni une recette Android.

Depuis le checkout actif, tests à lancer par l’utilisateur :

```powershell
$env:PYTHONPATH = "D:/Code/panelforge-krea2-flux/src"
D:/Code/panelforge/.venv/Scripts/python.exe -m unittest tests.test_factory_mobile tests.test_factory_mobile_browser
```

## Activation

La nouvelle route d’historique et son raccordement nécessitent le prochain démarrage normal de PanelForge depuis D:/Code/panelforge-krea2-flux. Aucun service en cours n’a été redémarré. Une fois ce démarrage effectué, recharger / rouvrir la page mobile ; la coque du service worker change de version.

Avant ce démarrage, le serveur en mémoire ne connaît pas les nouvelles routes : l’interface peut annoncer l’historique momentanément indisponible. Aucun rechargement à chaud du processus ni changement de production n’a été tenté.

Sauvegardes, diffs, aperçu et contrôles : D:/Code/panelforge/.agent/diagnostics/factory-mobile-history-20260928/. Aucun commit ni push.
