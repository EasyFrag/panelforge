# Proposition de patch LAN / Tailscale — 28 septembre 2026

Description demandée par l'utilisateur après intégration de la version actuelle dans master.
Document d'alignement conservé. Implémentation autorisée et réalisée ensuite dans le checkout de lancement ; voir [le rapport](network-modes-implementation-2026-09-28.md) et [les commandes actuelles](network-mode-launch-commands-2026-09-28.md). La recette utilisateur reste à effectuer.

## Résultat utilisateur

Un argument optionnel --network-mode avec deux valeurs : lan et tailscale.
Le choix s'applique au démarrage. Indication discrète Local ou Tailscale près du logo
pour le profil explicitement choisi, sans menu ni bascule à chaud.

| Accès | lan | tailscale |
| --- | --- | --- |
| ComfyUI serveur | http://192.168.1.72:8188 | http://bucket:8188 |
| LLM serveur | http://192.168.1.72:8083/v1 | http://bucket:8083/v1 |
| SSHFS serveur | \\sshfs.r\malmo@192.168.1.72 | \\sshfs.r\malmo@bucket |

Unsloth PC (127.0.0.1:8888), DLSS PC (127.0.0.1:8188), workspace et dossiers de
livraison locaux gardent leurs rôles. Les profils doivent couvrir tous les clients
ComfyUI, les appels LLM, l'administration llama-swap, les flux WebSocket et le suivi.

## Configuration et compatibilité proposées

- Résoudre le profil une seule fois avant la création des services et injecter les
  mêmes valeurs dans chaque client concerné.
- En l'absence de --network-mode, conserver les règles historiques des arguments et
  variables d'environnement. Le lancement existant avec les URL bucket continue à
  fonctionner ; il ne devient pas automatiquement un profil entièrement Tailscale.
- Avec un mode explicite, les URL et racines du profil suffisent. Une ancienne URL
  explicitement fournie et incompatible entraîne une erreur claire, pas une route
  différente de celle annoncée. Les valeurs d'environnement réseau héritées ne doivent
  pas détourner silencieusement le profil choisi ; leur priorité doit être couverte
  par les tests du résolveur.
- Le badge de profil est réservé à un mode explicite validé. En lancement historique,
  décrire les accès réels dans la console et signaler un mélange éventuel sans
  afficher à tort un profil intégralement local. Pas de troisième mode sélectionnable.
- Aucun repli automatique entre LAN et Tailscale ; une panne reste attribuée au
  service concerné et ne provoque aucune nouvelle soumission sur l'autre accès.

## Fichiers et exports : proposition affinée

Les racines KREA2 utiliseront directement le chemin UNC SSHFS du profil. Pour les
exports, séparer la destination logique conservée dans les jobs du chemin physique
utilisé pour l'écriture. Le montage X: de l'Explorateur reste intact : le programme
ne retire ni ne remonte ce lecteur à chaque lancement.

Le code actuel DlssVideoExporter.target() fabrique un chemin stocké dans
video_export.path ; export() exige ensuite l'égalité exacte avec ce chemin. Un simple
remplacement de X: par un UNC dans la configuration casserait donc la reprise des
anciens jobs. La proposition ajoute une résolution limitée de la destination
connue : même racine logique et même suffixe date/identifiant, accès physique LAN
ou Tailscale selon le profil. Les anciens chemins ne sont pas réécrits en masse.

Conserver les vérifications d'identifiant/date, de destination et de contenu,
l'écriture par fichier temporaire et les protections contre l'écrasement.
Aucune substitution arbitraire de préfixes sur des chemins libres. Les destinations
personnalisées hors de cette racine ne doivent pas être redirigées silencieusement.

L'accès direct UNC, sa mémorisation d'identifiants et l'équivalence des deux adresses
avec la même destination serveur devront être qualifiés dans la session Windows de
PanelForge avant de déclarer la bascule des exports validée. Aucune relance massive
des copies historiques en échec n'est prévue.

## Interface et diagnostics

Petit libellé près du logo, typographie/palette cohérentes, compact sur petite largeur.
Il indique le profil, pas une garantie de connexion. Console : profil, adresses et
racines effectives, sans clés. Une indisponibilité ne modifie pas le profil choisi.

Le mobile Android reste indépendant du transport PC vers bucket. Son accès distant
et ses notifications gardent leurs besoins Tailscale/Internet. La production LAN
avec les ressources déjà installées doit pouvoir continuer sans WAN ; il ne s'agit
pas de transformer les téléchargements ou notifications en services locaux.

## Vérifications prévues

- Résolution des deux profils, ancien lancement, priorités et contradictions.
- Propagation cohérente aux clients API, administration et suivi.
- Racines KREA2, export d'un ancien job au chemin logique X:, même fichier physique
  par les deux accès, respect des vérifications de destination et absence de repli.
- Badge conforme au mode, comportement de diagnostic d'un lancement historique.
- Recette utilisateur : lancement LAN, production représentative hors WAN/Tailscale
  en conservant le LAN, export, puis retour Tailscale ; reconnexion après nouvelle
  session. Les contrôles simples déjà réussis ne remplacent pas cette recette.

Pas de nouvelle dépendance prévue. Pas de modification des modèles, workflows,
prompts ou comportements de génération. Les tests fonctionnels et générations
restent à exécuter par l'utilisateur selon les instructions du checkout.
