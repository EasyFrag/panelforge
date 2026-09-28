# Alignement réseau entièrement local — 28 septembre 2026

## Objectif

Expliquer le chemin réseau actuel et proposer un mode PC + bucket sur le LAN, indépendant de Tailscale et d'Internet pour la production. Demande d'alignement : aucune bascule appliquée.

## Constats vérifiés en lecture seule

- Processus PanelForge : `--base-url http://bucket:8188`, `--llm-base-url http://bucket:8083/v1`, port 7861, workspace `D:/Code/panelforge/workspace`.
- `bucket` résout vers `100.85.117.28`, route Windows par Tailscale.
- Tailscale actif, sans alerte ni exit node sélectionné. Ping bucket direct IPv6 : 6 ms ; adresse distante dans le préfixe /64 directement connecté au Wi-Fi du PC. Transport actuellement local, sans relais DERP observé. Le champ `Relay=par` ne signifie pas que le trafic observé passe par un relais.
- PC : `192.168.1.83/24` sur Wi-Fi. Bucket confirmé par SSH : `192.168.1.72/24` sur Wi-Fi. Adresse attribuée dynamiquement : réservation DHCP à vérifier, elle peut déjà exister.
- GET LAN `http://192.168.1.72:8188/system_stats` : HTTP 200, 78 ms. GET via bucket : HTTP 200, 94 ms. Même GPU RTX PRO 6000 et OS Linux.
- GET LAN `http://192.168.1.72:8083/v1/models` : timeout à 4 s. GET via bucket : HTTP 200, 94 ms, 30 modèles listés. Aucun chargement de modèle ni génération.
- `ss -ltn` confirme ComfyUI sur toutes les interfaces, et le port 8083 seulement sur `127.0.0.1` et les adresses Tailscale IPv4/IPv6. UFW actif ; règles non examinées ni modifiées.
- Unsloth du PC est configuré sur `127.0.0.1:8888/v1` dans le lanceur consulté. Le ComfyUI DLSS a pour adresse par défaut `127.0.0.1:8188`.

Ces mesures décrivent l'instant du relevé, pas le chemin lors de l'incident d'hier. Aucun essai avec Internet ou Tailscale coupé n'a été effectué.

## Timeouts du 27 septembre

Le diagnostic situe les erreurs avant soumission du workflow, probablement pendant l'upload de référence : timeout HTTP 30 s, connexion réinitialisée, puis serveur injoignable. Un redémarrage de bucket a été observé. La cause profonde reste inconnue : Internet, Tailscale, Wi-Fi et service ne peuvent pas être départagés. Le LAN ne corrigera pas une panne du serveur ou du réseau local.

Rapport : `.agent/diagnostics/factory-timeout-2026-09-27/README.md`.

Tailscale peut relier les machines directement sur le LAN. Il utilise aussi un service de coordination et peut recourir à un relais. Des connexions existantes peuvent continuer avec des informations en cache lors d'une indisponibilité de coordination ; ce n'est pas une garantie générale d'autonomie après coupure ou redémarrage.

Références officielles :

- https://tailscale.com/docs/reference/connection-types
- https://tailscale.com/docs/reference/coordination-server-down

## Proposition

1. Production sur le LAN par défaut, PC et bucket conservant leurs rôles : ComfyUI par `192.168.1.72:8188`, sans MagicDNS ni tunnel.
2. Rendre d'abord le LLM serveur accessible en LAN : adapter son écoute ou son proxy, avec accès limité aux machines LAN autorisées ; préserver l'accès Tailscale. Ensuite seulement, changer l'URL LLM du lanceur. Unsloth reste sur la boucle locale du PC.
3. Garder Tailscale comme accès distant facultatif, notamment pour le futur téléphone. Aucun repli silencieux vers Tailscale dans un mode déclaré entièrement local. Tailscale peut rester actif sans porter les appels de production.
4. Vérifier les chemins de fichiers : racines SSHFS KREA2 utilisant `malmo@bucket`, export DLSS par défaut sur `X:`. Aucun mapping X: retourné dans la session de diagnostic ; cela ne prouve pas son absence dans la session utilisateur. Les rendre accessibles par LAN, ou utiliser des destinations locales explicites.
5. Couvrir la production avec modèles, nœuds et ressources déjà installés. Les enrichissements Civitai et l'installation du catalogue Clio comportent des accès externes distincts ; ressources nécessaires à conserver localement et mises à jour facultatives.
6. Recette ultérieure au moment choisi : lectures LAN, puis production autorisée avec Tailscale arrêté et Internet coupé en conservant le Wi-Fi/LAN ; vérifier aussi le démarrage hors Internet. Aucune coupure de diagnostic effectuée ici.

## État

Documentation uniquement. Aucun code applicatif, configuration, service, pare-feu, routage ou runtime modifié. Aucun test applicatif, appel LLM, rendu, redémarrage, commit ou push. Les requêtes de diagnostic étaient en lecture.

Pré-vérifications approfondies et proposition de choix du mode : [audit LAN / Tailscale](network-modes-preflight-2026-09-28.md).
