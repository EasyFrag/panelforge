# Pré-vérifications LAN / Tailscale et choix du mode — 28 septembre 2026

## Portée et décision proposée

Demande utilisateur : faire les vérifications préalables et aligner le choix du mode au lancement ou dans l'interface, sans coder. Audit en lecture seule du checkout actif `D:/Code/panelforge-krea2-flux`, du runtime partagé et de bucket. Des productions sont en cours : aucune interruption ou requête de génération.

Périmètre retenu par l'utilisateur : deux arguments de lancement, --network-mode lan et --network-mode tailscale, accompagnés d'une petite indication Local ou Tailscale intégrée à côté du logo PanelForge. Aucun sélecteur ni préférence réseau à ajouter dans l'interface à ce stade. Le code reste différé ; la phase actuelle concerne uniquement les vérifications et le paramétrage des machines, avec commandes exécutées par l'utilisateur et résultats retournés.

Le mode détermine comment PanelForge joint bucket. Il ne change ni les modèles, ni les GPU, ni le workspace, ni le choix du LLM PC/serveur. Il ne déconnecte pas Tailscale sur Windows ou Linux. Un téléphone peut joindre l'interface du PC par Tailscale pendant que le PC joint bucket par LAN.

## Vérifications réalisées

| Élément | Observation | Conséquence |
| --- | --- | --- |
| Lanceur courant | `--base-url http://bucket:8188`, `--llm-base-url http://bucket:8083/v1`, port 7861, workspace partagé existant | Profil actuellement Tailscale ; les arguments explicites dominent déjà les valeurs par défaut |
| Identité du serveur | SSH direct LAN, avec `HostKeyAlias=bucket` et vérification stricte de la clé connue : hostname bucket | Même serveur, sans nouvelle confiance SSH ni modification de known_hosts |
| Réseau | PC 192.168.1.83/24, bucket 192.168.1.72/24, Wi-Fi ; adresses Tailscale connues | Les deux chemins existent ; réservation DHCP encore à vérifier dans la box |
| ComfyUI HTTP | `/system_stats`, `/queue`, `/object_info/UNETLoader` répondent HTTP 200 par LAN et Tailscale, environ 47–94 ms | Lecture d'état, file et inventaire accessibles sur les deux chemins |
| ComfyUI WebSocket | Connexion et événements `status`, `crystools.monitor` reçus sur les deux chemins ; même température GPU | Suivi et télémétrie LAN vérifiés sans rendu de test |
| Lecture de fichier existant | HEAD `/view` : HTTP 200, même image PNG et longueur 1 482 988 octets par les deux chemins | Route d'accès aux sorties disponible ; aucun fichier téléchargé intégralement ou modifié |
| Écriture ComfyUI | Route POST `/upload/image` présente ; répertoires input/output accessibles au compte SSH, qui exécute ComfyUI | Prérequis statiques vérifiés ; upload réel non réalisé dans cet audit |
| LLM catalogue/administration | `/v1/models` et `/running` répondent par Tailscale ; timeout à 4 s sur LAN | Le LLM serveur est le prérequis réseau manquant |
| LLM réel | `/usr/local/bin/llama-swap --listen 127.0.0.1:8083 --config /etc/llama-swap/config.yaml` | Service limité à la boucle locale de bucket |
| Exposition LLM | `tailscale serve status --json` : TCP 8083 vers 127.0.0.1:8083 | L'écoute sur l'adresse Tailscale est un proxy ; ne pas remplacer aveuglément l'écoute par 0.0.0.0:8083 |
| Proxy LAN disponible | `systemd-socket-proxyd` et sa documentation déjà installés | Une entrée LAN distincte peut être proposée sans nouvelle dépendance logicielle |
| Pare-feu | UFW actif ; `sudo -n ufw status verbose` exige un mot de passe ; fichiers de règles non lisibles | Détail des autorisations bloqué par les droits Linux, à examiner avant toute ouverture LAN |
| Modèles LLM | 33 chemins de fichiers GGUF/safetensors explicites trouvés dans la configuration, 33 présents | Pas de fichier manquant dans cet inventaire ; ce n'est pas un essai complet de démarrage hors Internet |
| Ressources web | Aucun script/style externe identifié par recherche statique des références ; catalogue Clio présent localement | Interface et catalogue installé disponibles localement ; fonctions de téléchargement restent distinctes |
| Proxy du diagnostic | Aucun HTTP_PROXY, HTTPS_PROXY ou ALL_PROXY dans l'environnement du diagnostic ; sondes HTTP sans proxy | Les vérifications LAN effectuées ciblent directement l'adresse privée |

Les appels d'état n'ont pas chargé de modèle. La file ComfyUI contenait une tâche active pendant le relevé ; la température reçue était de 79 °C. Aucune conclusion nouvelle de panne ou surchauffe n'est tirée de ces observations ponctuelles.

## Prérequis serveur et stockage

### 1. Donner un accès LAN au même LLM

Solution préférée à qualifier : conserver llama-swap sur 127.0.0.1:8083 et le proxy Tailscale existant, ajouter un proxy TCP local lié **uniquement à 192.168.1.72:8083**, vers 127.0.0.1:8083. `systemd-socket-proxyd` installé sait transférer des flux bidirectionnels. Cette séparation conserve les accès existants et évite de faire dépendre l'API Tailscale d'une nouvelle adresse d'écoute du LLM.

Avant déploiement : vérifier les règles UFW avec les droits nécessaires, fixer/réserver les adresses nécessaires, limiter l'accès LAN aux machines autorisées et vérifier le comportement au démarrage avant attribution DHCP. Une adresse d'écoute générique sur le port 8083 risquerait de concurrencer les écoutes existantes ; elle n'est pas la proposition retenue. Les flux LLM longs et le streaming devront être qualifiés après installation. Le proxy proposé n'a pas été créé, démarré ou testé.

Références : [Tailscale Serve TCP](https://tailscale.com/docs/reference/tailscale-cli/serve), manuel installé `/usr/share/man/man8/systemd-socket-proxyd.8.gz` et binaire `/usr/lib/systemd/systemd-socket-proxyd`. Le manuel systemd en ligne a renvoyé HTTP 403 ; la documentation installée a été lue.

### 2. Traiter les chemins de fichiers sans casser les reprises

- Les racines KREA2 actuelles utilisent `\\sshfs.r\malmo@bucket\data\models\ComfyUi\...`, donc le nom Tailscale. Elles ne sont pas accessibles dans la session du diagnostic. Les dossiers correspondants existent et sont lisibles sur bucket ; SSH direct LAN fonctionne. Le mode LAN devra utiliser un accès LAN validé, ou une stratégie explicite basée sur l'inventaire ComfyUI pour les fonctions qui le permettent. Ne pas laisser des sondes SSHFS tenter Tailscale dans un profil annoncé LAN.
- `X:` n'est pas monté dans la session du diagnostic. Le journal réel confirme un problème applicatif existant : sur 413 tâches DLSS enregistrées, 355 copies supplémentaires sont en échec, 6 réussies et 52 sans copie. Les cinq dernières copies examinées échouent avec « Le partage vidéo du serveur n'est pas accessible ».
- Ces copies DLSS vers le serveur sont distinctes de la livraison de l'Usine sur le PC : au relevé, 126 fiches avaient une livraison réussie et une autre était active. Les derniers DLSS échantillonnés ont bien le traitement principal réussi.
- L'exporteur persiste un chemin absolu dans chaque tâche et refuse une reprise si la racine configurée produit un chemin différent. Un simple remplacement de X: par un UNC différent ferait donc échouer les anciennes reprises.
- Proposition minimale : conserver le chemin logique d'export, avec le même dossier physique derrière dans les deux modes ; valider le montage dans la session qui lance PanelForge. Le changement du transport de ce montage doit être explicite et réalisé hors copies en cours. S'il faut changer la destination logique, traiter cela comme une migration séparée, sans modifier les historiques ni relancer les 355 copies automatiquement.
- L'écriture sur le partage depuis PanelForge reste à qualifier : aucun fichier de test créé et aucune copie relancée pendant l'audit.

### 3. Définir précisément « hors Internet »

La cible est la production avec modèles, custom nodes et ressources déjà installés. La configuration LLM ne comporte pas les marqueurs usuels de téléchargement recherchés ; 33 fichiers explicitement référencés sont présents. Cela ne prouve pas que tous les modèles, extensions ComfyUI ou outils auxiliaires n'ont aucune vérification réseau au démarrage.

Civitai et l'installation/mise à jour Clio font des accès externes explicites. Leur indisponibilité doit rester indépendante de la production ; les données utiles déjà présentes restent utilisables. L'analyse statique ne remplace pas une recette réelle avec Internet coupé, incluant le démarrage des services. Aucun arrêt de Tailscale, coupure WAN, changement DNS ou redémarrage n'a été effectué.

## Choix du mode : périmètre retenu

Arguments à créer, inexistants aujourd'hui : `--network-mode lan` et `--network-mode tailscale`.

- Mode choisi au lancement. Aucun sélecteur, préférence sauvegardée ou changement de mode dans l'interface en V1.
- Petite indication **Local** ou **Tailscale** à côté du logo PanelForge, cohérente avec la typographie et la palette de l'en-tête fourni. Le texte décrit le mode actif ; une couleur ne doit pas prétendre certifier la disponibilité du serveur.
- Le profil LAN cible les services et chemins LAN de bucket ; Tailscale conserve l'accès aux mêmes services et données. Unsloth et DLSS du PC restent sur 127.0.0.1. Aucun repli automatique entre profils.
- Conserver workspace, identifiants et chemins logiques ; compatibilité des anciens arguments d'URL à traiter explicitement pour ne pas afficher Local devant une configuration Tailscale.
- Défaut de lancement à arrêter lors de la mise en service ; aucune modification implicite du lanceur en cours.
- Accès futur du téléphone indépendant du transport PC vers bucket.

## Phase actuelle : commandes utilisateur puis paramétrage des machines

L'utilisateur exécutera les commandes et retournera leurs résultats. Première série en lecture seule : sur bucket, `sudo ufw status verbose`, sockets TCP pertinents avec `sudo ss -ltnp`, adresses/MAC et état Tailscale Serve ; sur Windows, session PowerShell habituelle non élevée, interfaces actives et MAC, lecteurs/partages montés, services SSHFS/WinFsp et présence du chemin X: d'export. Confirmer aussi les réservations DHCP LAN de bucket et du PC dans la box.

Attendre ces éléments avant de fournir les commandes adaptées d'ouverture LAN du LLM et de montage. Ne pas demander de configuration LLM brute ou de fichier contenant des clés. Aucun changement de pare-feu, proxy, partage ou adresse appliqué dans ce tour.

### Pourquoi différer la bascule immédiate

Le code crée au démarrage neuf clients ComfyUI distants distincts, la passerelle LLM, le client d'administration llama-swap, la télémétrie et les services qui les conservent. Certains moniteurs capturent une URL WebSocket. Le catalogue KREA2 utilise aussi l'URL et les racines dans la portée de son cache. Modifier deux chaînes d'URL en direct ne mettrait pas à jour cet ensemble de façon cohérente.

Une vraie bascule à chaud exigerait : verrou global d'admission ; contrôle des tâches actives et réservées dans tous les ateliers, appels LLM et exports ; attente de la fin effective ; validation de l'identité du serveur cible ; remplacement atomique de tous les clients/moniteurs ; reconnexion des flux et invalidation des caches ; retour au profil précédent si validation échoue. La pause Usine seule ne couvre pas les autres ateliers. L'arrêt de sa boucle (`join(timeout=3)`) n'est pas une garantie de fin de toutes les opérations. Un timeout d'envoi ne justifierait jamais de resoumettre aveuglément un rendu sur l'autre chemin.

## Limites restantes avant mise en service

1. Lecture administrative des règles UFW et validation des réservations DHCP dans la box : accès nécessaires non disponibles dans cet audit.
2. Mise en place du proxy LAN LLM, puis vérification catalogue/administration/streaming ; rien n'a été configuré.
3. Identification/rétablissement du montage d'export dans la session de PanelForge et choix des racines KREA2 pour chaque transport ; validation des droits d'écriture à cette occasion.
4. Lors de l'implémentation autorisée, tests ciblés de résolution/priorité des profils, compatibilité des anciens arguments, propagation à tous les clients, absence de repli, indicateur fidèle au mode actif, identité et chemins persistants. Aucun test applicatif exécuté ici.
5. Recette finale hors WAN et hors Tailscale, LAN conservé : démarrage, upload, génération représentative autorisée, réception/suivi/thermique, export ; puis retour au profil Tailscale. L'audit actuel n'autorise pas à annoncer cette recette déjà réussie.

## Livrables et état

Seuls ce rapport, le lien depuis l'alignement initial et `.agent/CONTINUITY.md` sont écrits. Aucun code applicatif, configuration, prompt, runtime, service, règle réseau, modèle ou montage modifié. Aucun test applicatif, rendu, appel de génération LLM, redémarrage, commit ou push. Les documents décrivent une proposition à aligner, pas une implémentation.

## Retours utilisateur et préparation système — 28 septembre 2026

- L'utilisateur confirme explicitement les deux réservations DHCP dans la box : bucket 192.168.1.72 (Wi-Fi d8:b3:2f:a3:89:81), PC 192.168.1.83 (Wi-Fi 3c:0a:f3:f5:75:c9).
- UFW : deny incoming / allow outgoing ; 22, 8188 et 11434 ouverts en IPv4/IPv6 ; 8189 autorisé depuis 192.168.1.0/24. Aucune règle 8083 affichée. Conserver les règles existantes dans cette intervention.
- Lecteurs utilisateur mémorisés mais « Non disponible » : W: racine SSHFS LAN /home/malmo ; X: racine SSHFS malmo@bucket ; Y: /data ; Z: /data/ComfyUI/output. WinFsp.Launcher fonctionne. X:\data\ComfyUI\output\video\Upscale absent dans cette session.
- Les ports 8083 loopback et Tailscale et le transfert Serve vers 127.0.0.1:8083 sont confirmés par les sorties administratives.
- Préparation d'une entrée systemd LAN liée à 192.168.1.72:8083, proxy vers 127.0.0.1:8083, accès UFW limité au PC 192.168.1.83 sur wlp13s0.
- Noms prévus : panelforge-llm-lan.socket et panelforge-llm-lan.service. Les fichiers étaient absents de /etc/systemd/system au relevé.
- Syntaxe des deux unités vérifiée avec systemd-analyze verify sur systemd 255 de bucket, dans un dossier temporaire supprimé après contrôle : code retour 0, aucune sortie d'erreur. Aucun service installé, activé ou redémarré ; aucune règle ajoutée par l'agent.
- Socket : ListenStream=192.168.1.72:8083, FreeBind=yes, NoDelay=yes, WantedBy=sockets.target. Service : Requires/After socket et llama-swap.service ; ExecStart=/usr/lib/systemd/systemd-socket-proxyd 127.0.0.1:8083 ; DynamicUser=yes, NoNewPrivileges=yes, ProtectSystem=strict, ProtectHome=yes.
- Fournir à l'utilisateur les commandes d'installation de ces seuls fichiers et de la règle UFW, sans écrasement de fichiers existants, puis deux lectures /v1/models depuis Windows par LAN et par Tailscale. Le code PanelForge et ses URL courantes restent inchangés.
- Après les résultats : rétablir le montage X: avec le chemin logique existant, sans suppression de données ni relance des anciennes copies. Les montages W/Y/Z restent hors modification à ce stade.
- Retour arrière prévu de cette seule entrée : désactiver/arrêter panelforge-llm-lan.socket et arrêter panelforge-llm-lan.service ; supprimer uniquement la règle UFW exacte nouvellement ajoutée. Aucun arrêt de llama-swap, ComfyUI ou Tailscale.

Ces éléments complètent les limites du relevé précédent : règles UFW et réservations DHCP sont désormais connues ; accès LAN LLM et partage X: restent à mettre en service et à valider.

## Entrée LAN LLM en service — résultats utilisateur du 28 septembre

- L'utilisateur a installé les deux unités et la règle UFW prévue. Socket activé à 07:18:25 UTC. Les lectures /v1/models depuis Windows renvoient HTTP 200 par LAN et par Tailscale.
- Contrôle SSH en lecture seule : fichiers système conformes au contenu vérifié ; socket enabled/active, proxy service active/running, Result=success pour les deux. La sortie de terminal collée était tronquée visuellement mais les fichiers réels sont complets.
- Cette validation couvre la connexion et le catalogue. Aucun appel de génération ni essai hors WAN/Tailscale ou après redémarrage effectué.
- Préparation de X: : SSHFS-Win installé ; une négociation SSH sans authentification soumise confirme les méthodes serveur publickey,password sur le LAN. Le code retour 255 de cette sonde est attendu ; aucun mot de passe erroné essayé.
- Commandes proposées pour la session Windows habituelle non élevée : retirer uniquement le mapping X: indisponible, puis net use X: vers \\sshfs.r\malmo@192.168.1.72, demande de mot de passe interactive et /persistent:yes. Le préfixe sshfs.r conserve la racine distante / et donc le chemin d'export existant.
- Après réussite du montage : vérifier X: et les trois dossiers export/KREA2 modèles/LoRA ; vérifier écriture/lecture avec un fichier temporaire nommé par UUID sous le dossier d'export existant, puis retirer uniquement ce fichier.
- La commande /persistent:yes conserve le mapping ; la disponibilité automatique après ouverture de session et la gestion des identifiants restent à qualifier. Ne pas annoncer un montage réussi avant retour utilisateur.
- W/Y/Z et les anciens jobs restent inchangés. Aucune relance massive des copies. Le futur mode Tailscale devra aussi tenir compte du transport du montage X: : le choix réseau ne doit pas laisser un export LAN quand le PC n'est plus sur ce LAN.
- Références de syntaxe : https://github.com/winfsp/sshfs-win et documentation Microsoft net use. Aucun code applicatif modifié.

## Partage LAN X: validé — 28 septembre 2026

- Résultats utilisateur : X: remonte \\sshfs.r\malmo@192.168.1.72 ; export DLSS, modèles KREA2 et LoRA KREA2 donnent tous True. Le fichier temporaire unique a été écrit, relu à l'identique puis supprimé : lecture/écriture LAN validée.
- Relecture depuis la session de diagnostic : les trois répertoires sont également visibles. HKCU\Network\X confirme RemotePath LAN, fournisseur Windows File System Proxy, utilisateur malmo.
- Vérification ciblée cmdkey /list pour cette seule cible : aucune entrée d'identification enregistrée. /persistent:yes mémorise le mapping mais la reconnexion sans saisie après nouvelle session reste à configurer/qualifier.
- La documentation WinFsp indique que la case de mémorisation de sa fenêtre d'identification enregistre les identifiants dans le Gestionnaire Windows. Son fournisseur consulte un credential générique nommé par le chemin UNC. Préférer la reconnexion par l'Explorateur avec mémorisation ; ne pas fournir une commande contenant le mot de passe en clair.
- La réussite cmdkey /generic seule ne suffirait pas à certifier l'usage par SSHFS : une difficulté est signalée dans le dépôt, et le fournisseur impose un blob UTF-16 terminé par zéro. Aucune écriture ou lecture de mot de passe par l'agent.
- Procédure proposée à l'utilisateur : hors copie active, retirer seulement le mapping X:, le recréer dans l'Explorateur sur le même UNC LAN avec reconnexion à l'ouverture de session et mémorisation des identifiants, puis lire la présence de l'entrée ciblée et vérifier le dossier d'export. Aucun redémarrage requis pour cette étape.
- Le processus PanelForge courant utilise toujours --base-url http://bucket:8188 et --llm-base-url http://bucket:8083/v1. Ses racines KREA2 par défaut restent UNC bucket ; les futures configurations LAN devront utiliser les chemins LAN qualifiés. Ne pas annoncer l'application déjà entièrement basculée.
- Aucun export PanelForge postérieur au remontage identifié dans le journal consulté : la visibilité du montage et la copie complète depuis le processus applicatif restent à qualifier sans relancer les anciens échecs automatiquement.
- Références : https://winfsp.dev/doc/WinFsp-Service-Architecture/ ; https://github.com/winfsp/winfsp/blob/master/src/dll/np.c ; https://github.com/winfsp/sshfs-win/issues/462 ; https://learn.microsoft.com/windows-server/administration/windows-commands/cmdkey

## Identifiants SSHFS mémorisés — confirmation utilisateur du 28 septembre

- Après reconnexion via l'Explorateur, cmdkey ciblé affiche bien une entrée générique pour \\sshfs.r\malmo@192.168.1.72, utilisateur malmo, persistance de l'ordinateur local. Aucun mot de passe transmis ou lu.
- Test-Path du dossier X:\data\ComfyUI\output\video\Upscale renvoie True après cette opération. Le test complet de lecture/écriture/suppression avait réussi avant la reconnexion.
- Le socle LAN des machines est installé et les accès nécessaires testés en session courante : adresses réservées, ComfyUI HTTP/WebSocket/télémétrie, catalogue LLM LAN et Tailscale, stockage LAN accessible et identifiants mémorisés.
- Limites conservées : reconnexion réelle après ouverture de session ou redémarrage, copie depuis le processus PanelForge après remontage, générations et démarrage sans WAN/Tailscale non testés. Le code et le lanceur PanelForge restent inchangés ; le dernier processus observé appelle encore bucket/Tailscale.
- La future implémentation doit inclure les chemins KREA2 LAN et traiter explicitement le transport de X: pour le profil Tailscale hors LAN. Ne pas présenter le seul changement des deux URL comme un basculement complet des fichiers.
- Aucun nouveau paramétrage demandé à l'utilisateur dans cette réponse. Arguments --network-mode lan|tailscale et badge Local/Tailscale près du logo toujours différés ; aucun sélecteur dans l'interface.
