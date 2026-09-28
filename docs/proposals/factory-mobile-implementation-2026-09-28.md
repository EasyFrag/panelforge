# Usine mobile — 28 septembre 2026

L’interface Android est implémentée dans `D:/Code/panelforge-krea2-flux`. Elle utilise les mêmes services et estimations que l’Usine sur PC. Elle ne démarre aucun second ordonnanceur de génération.

## Version avant modification

Checkpoint **c4389c62aa8d7317ca0f5f7180c75b6a74984f92**, branche `snapshots/pre-factory-mobile-2026-09-28`, tag `snapshot-pre-factory-mobile-2026-09-28`. Les 191 fichiers applicatifs modifiés ou ajoutés depuis HEAD sont inclus, notamment Écriture Expérimentale v3 et les derniers correctifs Usine. Branche de travail et index conservés ; aucun push.

## Interface

- **Suivi** : livrées / total, temps restant et fin prévue, températures PC / serveur, cartes des étapes actives, vidéos en attente et fiches à reprendre.
- **Vidéos** : galerie paginée de 24 résultats, jusqu’aux 200 plus récents, y compris les résultats archivés. Lecteur intégré avec recherche dans la vidéo par requêtes HTTP Range. DLSS préféré lorsqu’il est prêt ; sinon vidéo brute disponible. Miniatures JPEG réduites, sans modifier les originaux.
- **Alertes** : températures au-dessus des seuils choisis, erreurs et activation des notifications du téléphone. La fin d’un lot est également notifiée.
- **Pause** laisse finir les étapes déjà actives et suspend les admissions suivantes. **Reprendre la file** reprend la file existante.
- **Arrêter** demande confirmation, met la file en pause et annule seulement les étapes actives affichées. Le serveur compare les identités des étapes dans la même section verrouillée que l’action ; une simple mise à jour de progression ne rend pas la confirmation obsolète, mais un changement d’étape la refuse. Aucun résultat produit n’est supprimé. Une étape interrompue peut ensuite être relancée explicitement depuis « À reprendre » ; les étapes réussies sont conservées.
- En cas de perte de connexion, les dernières estimations restent visibles et les commandes sont désactivées. Reconnexion = nouvelle lecture, jamais rejeu d’une commande.
- Page installable sur l’écran d’accueil. Le service worker ne met en cache que l’interface ; aucun état de production, média ou ordre différé n’est mis en cache.

## Notifications

Web Push avec abonnement explicite dans le navigateur. Le PC surveille les conditions toutes les cinq secondes, indépendamment de la page ouverte. Seuils de notification propres à chaque téléphone ; hystérésis de 3 °C et mémorisation des épisodes d’alerte pour éviter les répétitions. Une température absente / ancienne ne réarme pas une alerte.

Abonnements, préférences et alertes déjà envoyées sont enregistrés dans `workspace/video_factory/mobile-subscriptions.json`. La clé privée VAPID est créée au premier démarrage dans `workspace/video_factory/mobile-vapid.pem`. Ces fichiers restent hors Git. Un abonnement expiré est supprimé ; un échec transitoire est réessayé après une minute. Les anciennes erreurs et anciens lots terminés ne déclenchent pas une rafale à l’inscription.

Les notifications nécessitent HTTPS, l’autorisation Android / navigateur, le PC et le Lab allumés, et un accès Internet au service Push du navigateur. Le tableau de bord et les commandes passent par Tailscale. Les réglages de protection thermique existants restent l’autorité et ne sont pas changés depuis le téléphone.

Dépendance optionnelle déclarée : `pywebpush>=2,<3`. **pywebpush 2.5.0 et ses dépendances sont déjà installés** dans la venv partagée ; `pip check` ne signale aucun conflit. Pour une nouvelle installation : `python -m pip install -e ".[mobile]"`.

Références : [Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API), [pywebpush](https://github.com/web-push-libs/pywebpush), [Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve).

## Accès et activation

Le Lab démarre un accès HTTP séparé, lié uniquement à **127.0.0.1:8766**, avec la même application et les mêmes services. Port réglable via `--mobile-port` ; `--mobile-port 0` le désactive. Aucun accès aux autres API du Lab, aucun chemin de fichier arbitraire et aucun endpoint de génération ne sont exposés sur ce port. Les commandes HTTP nécessitent la même origine et un en-tête explicite. Les appareils autorisés par le réseau Tailscale ont accès au tableau de bord et à ses commandes.

**Activation confirmée le 28 septembre :** l’utilisateur a configuré Tailscale Serve et confirmé l’accès depuis Android. Page mobile locale et HTTPS vérifiées en HTTP 200. PanelForge PC répond sur **http://127.0.0.1:7861/** avec le lanceur actuel. Aucun redémarrage ni changement réseau effectué par l’agent.

Pour une première installation, après les tests et le démarrage du Lab depuis le checkout actif :

1. Ouvrir `http://127.0.0.1:8766/` sur le PC pour voir la page.
2. Dans PowerShell sur ce PC, publier cet accès uniquement dans le tailnet :

   ```powershell
   tailscale serve --bg --https=443 http://127.0.0.1:8766
   tailscale serve status
   ```

   Tailscale peut demander d’autoriser HTTPS dans le tailnet. Ne pas utiliser Funnel.
3. Sur Android avec Tailscale connecté, ouvrir **https://desktop-7bunq5p.tail68839a.ts.net/** dans Chrome.
4. Dans Alertes, choisir les seuils puis « Activer les notifications » et accorder l’autorisation du navigateur. Utiliser le menu du navigateur ou le bouton proposé pour ajouter le raccourci à l’accueil.

**Au quotidien :** lancer PanelForge avec le lanceur habituel ; l’accès mobile démarre avec lui. La commande `tailscale serve --bg ...` est une configuration initiale, conservée jusqu’à désactivation ; Serve reprend automatiquement après redémarrage lorsque Tailscale est connecté ([documentation Tailscale](https://tailscale.com/docs/reference/tailscale-cli/serve#effects-of-rebooting-and-restarting)). `tailscale serve status` sert seulement à vérifier l’état. Le PC doit rester allumé, PanelForge ouvert et Tailscale connecté sur le PC et le téléphone. La fenêtre PowerShell utilisée uniquement pour configurer Serve peut être fermée.

**Adresse au démarrage :** le serveur mobile réutilise désormais les réglages de logs du Lab sans les modifier et n’affiche plus son URL locale. Au prochain lancement, la ligne Uvicorn indique à nouveau le lien de PanelForge PC, avec le port choisi par le lanceur. Correction de syntaxe vérifiée ; aucun redémarrage ni test fonctionnel provoqué.

## Validation

Contrôles statiques effectués : syntaxe / compilation Python de neuf fichiers ; compilation V8 des deux scripts mobiles et des deux blocs du scénario navigateur sans exécution applicative ; TOML / manifeste et icônes ; dépendances ; diff. Aperçu HTML statique rendu dans un viewport de 412 px : largeur de contenu 412 px, pas de débordement horizontal. Les valeurs de cet aperçu sont fictives.

**Tests fonctionnels et navigateur non exécutés**, conformément à AGENTS.md du checkout actif. 21 scénarios préparés : projection sans prompts / chemins, sélection des médias, données anciennes, pagination, déduplication et hystérésis des notifications, mesure manquante, redémarrage, nouvel échec, réessai Push, abonnement expiré, stockage corrompu, origine HTTP, limitation de la surface exposée, lecture Range, arrêt ciblé et confirmation devenue ancienne, comportement hors connexion.

Depuis le checkout actif :

```powershell
$env:PYTHONPATH = "D:/Code/panelforge-krea2-flux/src"
D:/Code/panelforge/.venv/Scripts/python.exe -m unittest tests.test_factory_mobile tests.test_factory_mobile_browser tests.test_factory_monitoring tests.test_video_factory tests.test_video_factory_web
```

Recette sur Android à faire après activation : rafraîchissement, coupure / reprise de Tailscale, lecture vidéo / déplacement dans le lecteur, pause / reprise, annulation d’une confirmation d’arrêt, validation d’un arrêt, reprise explicite d’une fiche, inscription / désinscription aux notifications et réception page fermée. Aucune notification réelle n’a été envoyée pour vérification.

## Fichiers et preuves

Nouveaux modules `domain/factory_mobile.py`, `application/factory_mobile.py`, `infrastructure/factory_mobile.py`, `features/lab/factory_mobile_web.py`. Interface autonome dans `features/lab/static/factory-mobile/`. Raccords limités à `scripts/run_lab.py`, au cycle de vie du Lab et à la commande d’arrêt de l’Usine.

Sauvegardes, diff et contrôles : `D:/Code/panelforge/.agent/diagnostics/factory-mobile-20260928/`. Reçu Git : `D:/Code/panelforge/.agent/diagnostics/git-pre-factory-mobile-20260928/checkpoint.json`.
