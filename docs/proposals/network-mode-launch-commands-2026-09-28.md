# Lancement LAN ou Tailscale — alignement du 28 septembre 2026

Les commandes ci-dessous utilisent les options existantes. Les arguments --network-mode lan
et --network-mode tailscale, ainsi que le badge près du logo, restent à implémenter.
Aucun code applicatif n'a été modifié pour ce chantier.

La branche observée dans D:\Code\panelforge-krea2-flux est
feature/krea2-v6-style-catalog-2026-09-26. Ne pas faire de checkout pour retrouver
l'ancien nom feature/vocal-normalizer-dialogue-register du mémo.

## Avant de changer de mode

Attendre la fin des traitements et copies, arrêter PanelForge normalement et fermer
les fichiers ouverts sur X:. Utiliser la session PowerShell habituelle, non administrateur.
Les commandes net use remplacent uniquement le montage X:, pas les données du serveur.
Si X: est déjà monté sur la cible choisie et fonctionne, les deux lignes net use peuvent
être sautées. Si X: est absent, son retrait peut simplement signaler cette absence.
En cas d'échec du montage, ne pas lancer PanelForge.

## Préparation commune, dans la console de lancement

~~~powershell
Set-Location 'D:\Code\panelforge-krea2-flux'
git branch --show-current

$env:PANELFORGE_LOCAL_LLM_URL = 'http://127.0.0.1:8888/v1'
if (-not $env:PANELFORGE_LOCAL_LLM_API_KEY) {
    $pfSecret = Read-Host 'Cle API Unsloth' -AsSecureString
    $env:PANELFORGE_LOCAL_LLM_API_KEY = [System.Net.NetworkCredential]::new('', $pfSecret).Password
    Remove-Variable pfSecret
}

$pfCommon = @(
    '--workspace', 'D:\Code\panelforge\workspace'
    '--host', '127.0.0.1'
    '--port', '7861'
    '--local-llm-base-url', 'http://127.0.0.1:8888/v1'
    '--dlss-base-url', 'http://127.0.0.1:8188'
    '--krea2-models-root', 'X:\data\models\ComfyUi\diffusion_models\Krea2'
    '--krea2-loras-root', 'X:\data\models\ComfyUi\loras\krea2'
    '--dlss-video-export-root', 'X:\data\ComfyUI\output\video\Upscale'
)
~~~

La clé déjà définie dans cette console est conservée ; sinon elle est demandée sans
affichage. Aucune clé ni aucun mot de passe n'est inclus dans ce guide ou la version GitHub.

## Choix A : production sur le LAN

PC et bucket doivent être sur le LAN prévu. Le LAN/Wi-Fi doit rester actif même si
Internet est coupé. Tailscale peut rester activé : ces adresses ne passent pas par lui.

~~~powershell
net use X: /delete
net use X: '\\sshfs.r\malmo@192.168.1.72' /persistent:yes
if ($LASTEXITCODE -ne 0) { throw 'Montage LAN de X: impossible.' }

foreach ($pfPath in @(
    'X:\data\models\ComfyUi\diffusion_models\Krea2'
    'X:\data\models\ComfyUi\loras\krea2'
    'X:\data\ComfyUI\output\video\Upscale'
)) {
    if (-not (Test-Path -LiteralPath $pfPath)) { throw "Dossier inaccessible : $pfPath" }
}

& 'D:\Code\panelforge\.venv\Scripts\python.exe' '.\scripts\run_lab.py' @pfCommon --base-url 'http://192.168.1.72:8188' --llm-base-url 'http://192.168.1.72:8083/v1'
~~~

## Choix B : production via Tailscale

Tailscale doit être connecté sur le PC et bucket ; dans la configuration vérifiée,
bucket résout vers 100.85.117.28. Le montage utilise aussi Tailscale.
SSHFS peut demander les identifiants de malmo pour cette cible distincte ; pour les
mémoriser, utiliser la case de mémorisation dans l'Explorateur Windows.

~~~powershell
net use X: /delete
net use X: '\\sshfs.r\malmo@bucket' /persistent:yes
if ($LASTEXITCODE -ne 0) { throw 'Montage Tailscale de X: impossible.' }

foreach ($pfPath in @(
    'X:\data\models\ComfyUi\diffusion_models\Krea2'
    'X:\data\models\ComfyUi\loras\krea2'
    'X:\data\ComfyUI\output\video\Upscale'
)) {
    if (-not (Test-Path -LiteralPath $pfPath)) { throw "Dossier inaccessible : $pfPath" }
}

& 'D:\Code\panelforge\.venv\Scripts\python.exe' '.\scripts\run_lab.py' @pfCommon --base-url 'http://bucket:8188' --llm-base-url 'http://bucket:8083/v1'
~~~

Dans les deux cas, ouvrir http://127.0.0.1:7861/ et garder la console ouverte.

## Périmètre convenu pour la future modification

- Un argument --network-mode, avec les deux valeurs lan et tailscale.
- Le choix couvre les URL ComfyUI/LLM, les racines KREA2 et le transport des exports.
- Même workspace, mêmes données et chemins logiques. Unsloth et DLSS restent sur le PC.
- Changement au lancement ; pas de bascule à chaud ni de repli automatique.
- Indication discrète Local ou Tailscale près du logo ; pas de sélecteur dans l'interface.
- Prévoir la gestion explicite du montage X: et des anciens arguments pour éviter
  un mode annoncé LAN avec des chemins encore Tailscale, ou l'inverse.
- Valeur par défaut et traitement détaillé des anciennes options à arrêter avant implémentation.

## Ce qui est validé et ce qui reste à vérifier

Adresses LAN réservées, accès ComfyUI, catalogue LLM LAN/Tailscale, trois dossiers X:
et lecture/écriture/suppression LAN validés. Le montage conserve les chemins historiques
d'export. La recette complète sans Internet/Tailscale et le démarrage à froid ne sont
pas encore validés. Ces commandes sont préparées et contrôlées sans lancer l'application.

Le suivi Android est indépendant du mode PC vers bucket. Le serveur mobile démarre
toujours par défaut sur 8766 ; son accès distant passe par Tailscale et ses notifications
Web Push nécessitent Internet. Pour désactiver ce suivi lors d'un essai entièrement
hors ligne, ajouter --mobile-port 0 à la commande Python. La production reste soumise
à la disponibilité des modèles et ressources déjà installés ; les téléchargements et
enrichissements externes ne deviennent pas des services locaux.

Tailscale peut établir une liaison directe entre les deux machines sur le LAN :
son utilisation ne signifie pas automatiquement que les données transitent par Internet.

Références de syntaxe et de comportement :
- https://github.com/winfsp/sshfs-win
- https://tailscale.com/docs/reference/connection-types
