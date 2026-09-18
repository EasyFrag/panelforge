# Ordonnanceur global des traitements

PanelForge possède deux files FIFO indépendantes, administrées par le serveur avant tout appel aux moteurs :

- `local_gpu` : appels LLM locaux et traitements DLSS ;
- `remote_gpu` : rendus KREA2, H3, REF2V et Video Lab.

Une seule tâche peut occuper une machine à la fois. La machine locale et le serveur distant peuvent travailler simultanément. Un DLSS attend donc la fin des appels LLM déjà admis, puis bloque le démarrage des appels LLM suivants jusqu'à son terme. Il ne concurrence jamais un LLM sur le GPU local.

## Suivi

Le moniteur du bandeau ouvre la fenêtre **Traitements**. Elle affiche, pour chaque machine :

- la tâche active, son étape et son pourcentage lorsqu'il est mesurable ;
- la file FIFO et la position des tâches à venir ;
- les attentes thermiques et le compte à rebours ;
- la pause après la tâche en cours ;
- un historique court des traitements terminés.

Le suivi flottant remplace l'ancien indicateur DLSS. Les erreurs d'admission DLSS qui surviennent avant la création d'une tâche y sont également signalées.

## Paramètres globaux

La fenêtre persiste ses paramètres dans `workspace/system/work-scheduler.json` :

- seuil d'arrêt thermique ;
- seuil de reprise ;
- durée de stabilisation après retour sous le seuil ;
- surveillance locale et distante ;
- comportement lorsque la télémétrie est indisponible ;
- repos obligatoire entre deux rendus vidéo distants, 30 secondes par défaut ;
- pause automatique après une erreur non interceptée ;
- taille de l'historique visible.

Les anciens réglages thermiques propres au lot d'images et le repos propre à la chaîne vidéo Histoires ne pilotent plus le coordinateur. Les documents historiques restent lisibles, mais l'admission utilise toujours les paramètres globaux courants.

Le repos vidéo est évalué seulement lorsqu'une nouvelle vidéo atteint la tête de la file distante. Il ne prolonge donc pas artificiellement la fin de la dernière vidéo, mais aucune image ou autre vidéo ne peut la dépasser une fois son admission commencée.

## API

- `GET /api/work-scheduler/status`
- `GET /api/work-scheduler/settings`
- `PUT /api/work-scheduler/settings`
- `POST /api/work-scheduler/{local_gpu|remote_gpu}/pause`
- `POST /api/work-scheduler/{local_gpu|remote_gpu}/resume`

`GET /api/runtime/status` expose aussi `work_scheduler`; `production_resources` reste fourni comme vue de compatibilité.

## Limites actuelles

La progression H3 et KREA2 est une progression de phases, pas le nombre exact d'étapes ComfyUI. DLSS agrège ses phases en un pourcentage global. Une tâche déjà envoyée n'est pas interrompue par **Pause** : la pause s'applique au prochain départ, conformément au libellé de l'interface.
