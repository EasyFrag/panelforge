# Implémentation des profils réseau — 28 septembre 2026

## Résultat

Le lanceur du checkout D:/Code/panelforge-krea2-flux accepte --network-mode lan
et --network-mode tailscale. Sans argument, la commande existante conserve ses
adresses, montages et règles de configuration. Badge discret Local/Tailscale
près du logo uniquement pour un profil explicite.

[Commandes de lancement complètes](network-mode-launch-commands-2026-09-28.md).

## Changements techniques

- Résolveur unique en infrastructure, appelé après argparse et avant build_app.
  Pas de résolution DNS, montage ou test de disponibilité dans ce résolveur.
- Injection des URL et transports dans les neuf clients ComfyUI serveur, les
  passerelles LLM serveur/local, l'administration llama-swap, la surveillance
  thermique et les flux de prévisualisation/suivi. Le client, le suivi et les
  contrôles de disponibilité DLSS restent sur le PC avec transport direct.
- Les profils explicites désactivent les proxys uniquement pour ces transports :
  opener urllib dédié, HTTPX trust_env=False et option WebSocket proxy=None
  lorsqu'elle existe. Compatibilité avec les signatures websockets 13/14/15.
- En LAN, FastEmbed local_files_only=True même si l'index doit être reconstruit.
  L'ancien lancement et Tailscale gardent la règle d'indexation précédente.
- Racines modèles/LoRA en UNC du profil. DlssVideoExporter sépare racine logique
  et accès physique. Le contrôle exact du chemin mémorisé reste appliqué ; seul
  le suffixe validé date/identifiant est utilisé sous la racine physique.
  Identifiant, date, comparaison du contenu, temporaire et remplacement atomique
  restent protégés. Aucun repli vers X: si l'UNC choisi est inaccessible.
- GET /api/network-mode renvoie seulement mode/label. Un script indépendant
  affiche le badge à partir de cette configuration, sans sondage des serveurs.
  En historique, échec de requête ou ancien backend, le badge reste masqué.
- Aucun nouveau paquet requis. Aucun changement des recettes ou prompts.

## Vérifications effectuées

- Analyse AST et compilation en mémoire des dix fichiers Python concernés.
- Compilation JavaScript dans Chrome isolé, sans exécuter le script applicatif.
- Aperçu statique des deux badges inspecté.
- Revue du diff par rapport aux sauvegardes prises avant cette tâche, distincte
  des nombreux changements déjà présents dans la branche de travail.

Les tests fonctionnels ne sont pas exécutés : AGENTS.md les réserve à l'utilisateur
sauf demande explicite contraire. tests/test_network_modes.py couvre l'ancienne
commande, les valeurs héritées, les contradictions, l'injection des profils,
les connexions directes, les versions WebSocket, l'indexation hors ligne, le badge
et les exports d'anciens jobs. Aucun vrai service ou montage réseau n'est utilisé
par ce module de tests.

L'accès UNC authentifié pour chaque cible dans la session applicative, l'écriture
réelle sur le même dossier serveur et une production complète sans Internet
restent à qualifier par l'utilisateur. Aucun résultat de ces recettes n'est revendiqué.

## État de livraison

Code modifié uniquement dans le checkout de lancement D:/Code/panelforge-krea2-flux.
Les guides et la continuité sont également conservés dans D:/Code/panelforge.
Aucun redémarrage, appel LLM, rendu, modification des jobs existants, commit ou
push. La version master publiée précédemment reste le snapshot avant ces profils.
Le WinError 5 d'enregistrement local DLSS reste hors du périmètre de ce patch.

Sauvegardes des fichiers, manifeste de hachages, diff limité à cette tâche,
compilation et aperçu statique :
D:/Code/panelforge/.agent/diagnostics/network-modes-implementation-20260928/.
