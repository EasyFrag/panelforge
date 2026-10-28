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

### Pause thermique globale

Le popup propose un bloc commun **Pause thermique globale**, activé par défaut avec un seuil GPU de **86 °C**, configurable et enregistré avec les autres paramètres. Il surveille les deux GPU indépendamment des réglages de cooldown et de leurs cases de surveillance.

Une température **strictement supérieure au seuil** sur l'un des GPU bloque les nouveaux départs sur les deux files PanelForge. Une tâche déjà admise continue normalement ; aucune annulation, suspension du processus de calcul ou extinction de machine n'est envoyée. Les tâches en attente gardent leur ordre et leurs résultats.

Le contrôle utilise le suivi backend, même popup fermé, et vérifie aussi la température avant l'admission finale. Une tâche qui possède déjà une place mais attend un cooldown ne peut pas contourner le verrou. Le message indique le GPU, la température et le seuil de l'incident ; le suivi flottant conserve l'alerte.

Le refroidissement ne relance rien automatiquement. **Reprendre les traitements** demande une nouvelle mesure des deux GPU, tous deux disponibles et **strictement sous le seuil courant**. Les pauses manuelles par file et les cooldowns existants restent applicables après cette reprise. Les commandes de reprise individuelles, la modification du seuil et la désactivation de la protection ne lèvent pas le verrou global.

L'incident est sauvegardé séparément dans `workspace/system/work-thermal-pause.json` et restauré au redémarrage. Une erreur d'écriture laisse la pause active et affiche une alerte ; la sauvegarde est retentée à la mesure suivante. Une reprise dont l'enregistrement échoue ne libère pas les files. Cette V1 réagit aux dépassements mesurés ; elle ne crée pas de nouvelle politique d'arrêt sur perte de télémétrie ni de surveillance autonome sur le serveur distant.

Le repos vidéo est évalué seulement lorsqu'une nouvelle vidéo atteint la tête de la file distante. Il ne prolonge donc pas artificiellement la fin de la dernière vidéo, mais aucune image ou autre vidéo ne peut la dépasser une fois son admission commencée.

## API

- `GET /api/work-scheduler/status`
- `GET /api/work-scheduler/settings`
- `PUT /api/work-scheduler/settings`
- `POST /api/work-scheduler/thermal-pause/resume` (409 si les deux températures ne permettent pas la reprise)
- `POST /api/work-scheduler/{local_gpu|remote_gpu}/pause`
- `POST /api/work-scheduler/{local_gpu|remote_gpu}/resume`

`GET /api/runtime/status` expose aussi `work_scheduler`; `production_resources` reste fourni comme vue de compatibilité.

## Limites actuelles

La progression H3 et KREA2 est une progression de phases, pas le nombre exact d'étapes ComfyUI. DLSS agrège ses phases en un pourcentage global. Une tâche déjà envoyée n'est pas interrompue par **Pause** : la pause s'applique au prochain départ, conformément au libellé de l'interface.
