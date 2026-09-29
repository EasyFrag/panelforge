# Monitoring Usine sur PC — patch du 27 septembre 2026

**Mise à jour du 28 septembre 2026 — temps restants conservés :** les étapes marquées comme reprises gardent leur durée indicative. Un dépassement conserve une marge résiduelle plutôt que d’effacer la prévision du lot. Les dernières valeurs connues sont figées pendant une attente indéterminée, avec heure de fin suspendue ; le calcul courant reprend ensuite. Une perte de polling n’efface plus l’indication. Le correctif de calcul nécessite le prochain redémarrage choisi du Lab ; aucun traitement n’a été interrompu.

**Mise à jour du 28 septembre 2026 — UX compacte :** les cartes de température, alertes thermiques et grands bandeaux sont retirés de la page Usine. Le suivi du lot (reste, fin, livrées / total) apparaît dans l’en-tête fixe à côté du titre, sur les quatre onglets. La prévision de sélection y apparaît uniquement lorsqu’une sélection prête est faite. Le popup global conserve le suivi des températures. Cet ajustement est entièrement statique ; recharger la page suffit. Les descriptions plus détaillées ci-dessous documentent le patch initial.

Statut : implémenté dans `D:/Code/panelforge-krea2-flux`, validation fonctionnelle à exécuter par l’utilisateur. Phase téléphone différée.

## Comportement

- **Préparation** : sélectionner des fiches prêtes affiche une estimation avant lancement, tenant compte de la file actuelle. Réglages non enregistrés ou fiches incomplètes : prévision masquée. En pause, la prévision est explicitement conditionnelle à une reprise immédiate ; consulter ou lancer ne reprend pas la file.
- **Production** : temps restant, heure de fin et fourchette indicative, livrées / total, actives, attente, export. Décompte local chaque seconde ; rafraîchissement de l’état et recalcul via le polling existant toutes les cinq secondes.
- **Chaque vidéo** : heure de livraison complète, début prévu du rendu, reste estimé sous l’étape active. Les durées réellement écoulées restent affichées.
- **Inspecteur** : attente avant la prochaine étape, durées des étapes restantes, disponibilité de la vidéo brute et livraison avec options / export.
- **Machines** : températures Local / Serveur, activité, refroidissement et alertes visuelles persistantes selon les seuils configurés. Accès au moniteur et à son historique existants.
- **Pause** : les étapes en cours peuvent finir ; la fin globale est suspendue. Les temps inconnus, dépassements et données anciennes ne se transforment pas en faux « 0 s ».

## Lots et livraison

Le lot est un registre persistant `production_cycle` dans l’état de l’Usine. Une première admission ouvre un lot ; les ajouts pendant sa production le rejoignent. Pause et reprise conservent son identité. Une nouvelle admission après clôture ouvre le lot suivant ; une reprise explicite d’erreur conserve le lot courant.

Les filtres et sélections n’affectent pas le dénominateur. Archivage et suppression conservent la trace du membre dans le lot. Erreurs, annulations, retraits et arrêts en cours restent distincts des livraisons. Au premier démarrage de cette version, seules les productions encore en cours / à exporter sont rattachées au lot initial ; les anciens lots ne peuvent pas être reconstruits exactement.

« Livré » exige la réussite des étapes activées et un export correspondant à la dernière version des fichiers et du texte IG. Un export vidéo provisoire pendant la génération IG ne termine pas la fiche.

## Calcul et historique

- Historique dédié : `workspace/video_factory/timings.json`, écriture atomique, indépendant des fiches supprimables.
- Import initial idempotent des étapes terminées et datées, depuis les identifiants explicitement conservés dans l’état. Références de recette réellement exécutée lues depuis les projets de rendu ; aucune recherche de médias par convention de nommage.
- Mesures versionnées, identifiant de tentative de mesure, références enfant, date et provenance. Conservation de 4 000 observations récentes et des identifiants déjà importés.
- Comparaisons par étape, machine logique, modèle, profil / cookbook, recette effective et empreinte du workflow, mode / références, durée, résolution, paramètres BUNNY / LoRA / DLSS. La graine et le contenu des prompts ne créent pas de groupes séparés.
- Médiane des 40 dernières observations comparables ; intervalle descriptif élargi. Repli pour les étapes LLM avec le même modèle et profil, en relâchant uniquement des paramètres de contenu ; confiance indiquée plus faible.
- Reprises connues, résultats réutilisés et anciennes observations GPU manifestement trop courtes / ambiguës exclus de l’apprentissage. Le marqueur de mesure partielle ne supprime plus la prévision issue des autres mesures comparables. Un dépassement sans observation restante conserve une marge indicative de 20 % de la médiane (minimum 5 s), avec confiance faible et intervalle élargi ; cette marge ne garantit pas une fin dans ce délai.
- Simulation séparée du véritable ordonnanceur : ordre des fiches, dépendances, une étape active par fiche, Local et Serveur en parallèle, refroidissements connus, autres travaux déjà dans les files machine, publication finale sérialisée.
- Données machines reprises du polling existant, sans appel supplémentaire aux GPU depuis les requêtes de prévision. Aucun changement des priorités ni des décisions de lancement.
- Le premier export dispose d’une **provision explicite de 15 s, plage 0–60 s**, jusqu’aux premières mesures. Elle est indiquée dans l’inspecteur et abaisse la confiance.
- La prévision ne garantit pas les refroidissements futurs ni la charge d’autres ateliers ajoutée après son calcul. Les pauses / attentes sans durée restent indéterminées : si une prévision existait, son temps restant est conservé comme référence figée, mais son heure de fin est suspendue. Cette référence est conservée en mémoire du service, séparément du journal durable des durées. Elle est invalidée en cas de changement de lot, de file / configuration ou de tentative ; un aperçu de sélection ne remplace jamais la prévision de production. Les groupes de mesures sont locaux au workspace et aux deux machines logiques ; un changement de matériel nécessite une nouvelle calibration.

Les intervalles ne sont pas des garanties statistiques. La précision de la file complète n’est pas encore mesurée sur des productions réelles avec cette version.

## Fichiers principaux

- `domain/factory_timing.py` : signatures et statistiques.
- `domain/factory_forecast.py` : simulation.
- `domain/factory_cycle.py` : lots et livraison.
- `application/factory_monitoring.py` et `infrastructure/storage/factory_timings.py` : observations et persistance.
- Raccords limités dans le service Usine, son adaptateur, le routeur HTTP et `scripts/run_lab.py`.
- `features/lab/static/video-factory-monitor.js` / `.css` : présentation et décompte ; raccords à la table / inspecteur existants.
- API de lecture `POST /api/video-factory/estimate` avec IDs et révisions, sans lancement.
- `tests/test_factory_monitoring.py` : statistiques, calendrier, refroidissements, pauses, concurrence, exports, lots, stockage, absence de mutations et garde HTTP de révision.
- `scripts/analyze_factory_timings.py` : audit chronologique hors ligne des étapes. Chaque observation est prédite avec uniquement l’historique antérieur.

## Validation et activation

Contrôles effectués : syntaxe / compilation Python, compilation JavaScript par V8 sans exécution des scripts applicatifs, revue des raccords et des différences. Aucune génération, appel LLM, manipulation des traitements actifs ou redémarrage.

Conformément à [AGENTS.md](../../AGENTS.md) : « Tests are run by the user unless explicitly requested otherwise. » Les tests fonctionnels et la revue visuelle dans le Lab restent à exécuter par l’utilisateur.

Depuis le checkout actif :

```powershell
$env:PYTHONPATH = "D:/Code/panelforge-krea2-flux/src"
D:/Code/panelforge/.venv/Scripts/python.exe -m unittest tests.test_factory_monitoring tests.test_video_factory tests.test_video_factory_web tests.test_video_factory_archives
```

Puis, si les tests ciblés passent :

```powershell
D:/Code/panelforge/.venv/Scripts/python.exe -m unittest discover -s tests
```

Le patch serveur prendra effet au prochain redémarrage choisi du Lab, après la production en cours. Les ressources du navigateur sont versionnées pour éviter l’ancien cache. Aucun redémarrage n’a été effectué pendant l’implémentation.

Après import des mesures par le nouveau Lab, audit facultatif sans GPU ni réseau :

```powershell
D:/Code/panelforge/.venv/Scripts/python.exe scripts/analyze_factory_timings.py --workspace D:/Code/panelforge/workspace
```

Recette manuelle : sélection prête / édition / suppression de sélection ; lancement ; deux machines occupées ; refroidissement connu puis attente thermique ; pause / reprise ; erreur / annulation ; export IG tardif ; archivage / suppression sans variation du total ; perte de polling supérieure à 20 secondes ; redémarrage avec reprise. Vérifier aussi les lots passant minuit.

## Sauvegarde

Le checkpoint antérieur `29cdf3e` reste disponible : branche `snapshots/pre-factory-monitoring-2026-09-27`, tag `snapshot-pre-factory-monitoring-2026-09-27`.

Les fichiers préexistants touchés par ce patch sont sauvegardés dans `D:/Code/panelforge/.agent/diagnostics/factory-monitoring-implementation/before`. Aucun commit supplémentaire, push ni modification réseau.
