# Lancement LAN ou Tailscale — 28 septembre 2026

Les profils sont implémentés dans le checkout de lancement
D:\Code\panelforge-krea2-flux. Ce guide remplace les anciennes commandes avec
remontage de X:. Le programme utilise directement les accès SSHFS du profil.

Le choix se fait au lancement. Attendre la fin des traitements et copies puis
arrêter normalement PanelForge avant de choisir une autre commande. Le patch
n'a pas redémarré l'instance en cours.

## Préparation commune dans PowerShell

~~~powershell
Set-Location 'D:\Code\panelforge-krea2-flux'

$env:PANELFORGE_LOCAL_LLM_URL = 'http://127.0.0.1:8888/v1'
if (-not $env:PANELFORGE_LOCAL_LLM_API_KEY) {
    $pfSecret = Read-Host 'Clé API Unsloth' -AsSecureString
    $env:PANELFORGE_LOCAL_LLM_API_KEY = [System.Net.NetworkCredential]::new('', $pfSecret).Password
    Remove-Variable pfSecret
}

$pfCommon = @(
    '--workspace', 'D:\Code\panelforge\workspace'
    '--host', '127.0.0.1'
    '--port', '7861'
    '--local-llm-base-url', 'http://127.0.0.1:8888/v1'
    '--dlss-base-url', 'http://127.0.0.1:8188'
)
~~~

La clé déjà définie dans la console est conservée ; sinon elle est saisie sans
affichage. Aucun secret réel n'est enregistré dans ce guide. Ne pas ajouter les
anciens arguments de racines X: au tableau commun.

## Mode Local

~~~powershell
& 'D:\Code\panelforge\.venv\Scripts\python.exe' '.\scripts\run_lab.py' @pfCommon --network-mode lan
~~~

ComfyUI et le LLM serveur utilisent respectivement 192.168.1.72:8188 et
192.168.1.72:8083/v1. Les modèles, LoRA et exports utilisent
\\sshfs.r\malmo@192.168.1.72. Le PC et bucket doivent rester connectés au même LAN,
même lorsque l'accès Internet est coupé.

## Mode Tailscale

~~~powershell
& 'D:\Code\panelforge\.venv\Scripts\python.exe' '.\scripts\run_lab.py' @pfCommon --network-mode tailscale
~~~

ComfyUI et le LLM serveur utilisent bucket:8188 et bucket:8083/v1 ; les fichiers
passent par \\sshfs.r\malmo@bucket. Tailscale doit fonctionner sur les deux machines
et bucket doit résoudre vers son adresse Tailscale, comme dans la configuration
déjà vérifiée.

Dans les deux cas, ouvrir http://127.0.0.1:7861/. Le badge près du logo indique
Local ou Tailscale. Il décrit le profil choisi, pas l'état de connexion.

## Ancienne commande toujours compatible

Après la préparation commune des deux variables Unsloth :

~~~powershell
& 'D:\Code\panelforge\.venv\Scripts\python.exe' '.\scripts\run_lab.py' --workspace 'D:\Code\panelforge\workspace' --base-url 'http://bucket:8188' --llm-base-url 'http://bucket:8083/v1' --port 7861
~~~

Sans --network-mode, les règles et montages historiques sont conservés. Les API
de cette commande utilisent bucket, mais les exports dépendent du montage X:
existant, qui a été configuré sur le LAN. Aucun badge de profil intégral n'est
affiché pour ce lancement. La console décrit les adresses et dossiers utilisés.

## Règles des profils

- Avec --network-mode, les anciennes variables PANELFORGE_COMFY_URL,
  PANELFORGE_LLM_URL, PANELFORGE_KREA2_MODELS_ROOT et PANELFORGE_KREA2_LORAS_ROOT
  ne remplacent pas les valeurs du profil.
- Les arguments explicites --base-url, --llm-base-url et les racines serveur
  doivent correspondre au profil. Une contradiction produit une erreur au
  lancement avec le nom de l'option à retirer.
- Sans mode, les priorités historiques arguments > environnement > défauts
  restent inchangées.
- Le workspace, les sorties PC, la clé Unsloth et les options du LLM local restent
  identiques. La préparation commune ci-dessus fixe Unsloth et DLSS sur 127.0.0.1.
- Les connexions API et WebSocket internes des profils n'utilisent pas de proxy
  système/environnement. Aucun réglage proxy global n'est modifié.
- Aucun repli automatique vers l'autre mode ; aucun remontage de X:.
- Les anciens jobs gardent leur chemin logique X:. L'export utilise le chemin UNC
  du profil pour le même suffixe date/identifiant. Les destinations personnalisées
  hors de la racine historique nécessitent le lancement sans --network-mode.

## Vérification des accès fichiers dans la session Windows de lancement

Le montage X: a déjà été vérifié en LAN. Le nouveau profil utilise l'UNC direct :
il faut également que cet accès dispose des identifiants dans la même session.

Pour le LAN :

~~~powershell
$pfShare = '\\sshfs.r\malmo@192.168.1.72'
foreach ($pfRelative in @(
    'data\models\ComfyUi\diffusion_models\Krea2'
    'data\models\ComfyUi\loras\krea2'
    'data\ComfyUI\output\video\Upscale'
)) {
    $pfPath = Join-Path $pfShare $pfRelative
    [pscustomobject]@{ Chemin = $pfPath; Accessible = Test-Path -LiteralPath $pfPath }
}
~~~

Pour Tailscale, réutiliser ce bloc avec $pfShare = '\\sshfs.r\malmo@bucket'.
Si un accès échoue, ouvrir le chemin UNC dans l'Explorateur de la même session
et renseigner les identifiants SSHFS de malmo pour cette cible. Le programme
ne stocke ni ne modifie ces identifiants. Ne pas retirer X: pour ce contrôle.

## Validation et limites

Syntaxe Python/JavaScript et aperçu statique du badge vérifiés. Les tests unitaires
sont préparés mais non exécutés conformément à AGENTS.md. Ils utilisent des
simulations et dossiers temporaires, sans service réel ni génération :

~~~powershell
Set-Location 'D:\Code\panelforge-krea2-flux'
& 'D:\Code\panelforge\.venv\Scripts\python.exe' -m unittest discover -s tests -p test_network_modes.py
~~~

La recette sur les deux machines reste nécessaire : accès UNC direct, export puis
retour Tailscale, reconnexion après nouvelle session et production LAN sans WAN,
en gardant le Wi-Fi/LAN actif. Ne pas déduire une recette complète d'un simple HTTP 200.

Les modèles et ressources de production doivent être installés. En mode LAN,
l'indexation des exemples utilise uniquement les modèles en cache ; un modèle
manquant ne sera pas téléchargé automatiquement. Les enrichissements externes
déclenchés volontairement et téléchargements nécessitent toujours Internet.

Le mobile Android reste indépendant. Pour désactiver son serveur lors d'un essai
hors ligne, ajouter --mobile-port 0 à la commande Python. L'accès distant et les
notifications Web Push gardent leurs besoins réseau propres.

Le patch est local au checkout de lancement ; aucune nouvelle publication GitHub
n'a été effectuée dans cette étape. Le rapport technique est
[network-modes-implementation-2026-09-28.md](network-modes-implementation-2026-09-28.md).
