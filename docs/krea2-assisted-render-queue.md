# File de rendus KREA2 Assisted

Implémentée le 2026-09-06. Les tests sont préparés mais non exécutés, à la
demande de l’utilisateur. Aucun appel LLM, rendu, annulation ou redémarrage
de service effectué pendant le développement.

## Utilisation

- Cliquer sur « Lancer un rendu », puis continuer à changer prompt, modèle,
  LoRA et seed. Le bouton devient « Ajouter un rendu à la file ».
- Chaque clic capture les valeurs du formulaire, la branche et le point de
  conversation. Un champ seed vide tire une nouvelle seed pour cet essai ;
  une seed explicite, y compris 0, est conservée.
- Une file commune aux ateliers Assisted conserve l’ordre d’ajout. Un seul
  essai est soumis/suivi à la fois par ce service. Les autres travaux ComfyUI
  conservent leur propre gestion ; cette file ne réordonne pas la file distante.
- Chaque carte affiche son état et, en attente, sa position globale (1 inclut
  l’essai actif). L’atelier actif distant est nommé et accessible depuis le
  bouton « Voir l’atelier en cours ».
- Annulation individuelle sur chaque carte. Annuler un essai encore en attente
  n’envoie aucune interruption à ComfyUI et ne supprime pas les autres essais.
- Les anciens essais « Préparé · non lancé » restent inactifs jusqu’au clic
  « Ajouter cet essai à la file ». Cette action utilise leurs réglages enregistrés.

## Exécution et reprise

Le serveur lance un worker lors du démarrage de l’application. La fermeture
de la page n’arrête pas la file. L’arrêt du serveur cesse le suivi sans annuler
les calculs distants ; le prochain démarrage relit les travaux en attente et
reprend les rendus déjà soumis avec leur identifiant ComfyUI.

Une erreur confirmée du rendu ou une ressource disparue marque cet essai en
échec, puis laisse passer le suivant. Un checkpoint ou une LoRA manquante ne
sont jamais remplacés/retirés silencieusement au moment de son exécution.

Une panne réseau/expiration du suivi conserve l’identifiant du calcul et
met la suite en attente. Le suivi réessaie sans soumettre une deuxième fois.
Si ComfyUI a lui-même perdu son historique, la fin du calcul ne peut pas être
déduite automatiquement ; l’utilisateur conserve la main sur l’annulation.

Le statut `submitting` est persisté avant l’envoi. Si le processus tombe entre
l’envoi et l’enregistrement de l’identifiant distant, la file s’arrête avec
un message explicite. Vérifier ComfyUI avant de retirer cette entrée : son
retrait local ne peut pas annuler un calcul dont l’identifiant est inconnu.

Le dispositif cible le serveur Lab unique habituel pour ce workspace ; ses
verrous ne constituent pas une coordination entre plusieurs processus Lab.

## Contrats

- Assisted schéma 6 ; lecture des schémas 1 à 5 conservée.
- `queue_order` conserve l’ordre global, sérialisé en chaîne pour éviter une
  perte de précision JavaScript. Les anciennes entrées sans ordre sont traitées
  avant les nouvelles, avec un ordre déterministe entre projets.
- POST `.../projects/{id}/attempts?enqueue=true` prépare et met en file en une
  sauvegarde. Le contrat historique sans paramètre prépare seulement.
- POST `.../attempts/{id}/start` ajoute un essai préparé ; un appel répété sur
  le même essai actif est sans duplication.
- GET `/api/image-lab/krea2-assisted/render-queue` expose états, positions,
  ateliers et erreurs. Le polling ne déclenche pas les générations.
- Le point d’entrée synchrone `execute_attempt`, utilisé par Production,
  respecte le même ordre et attend son résultat. Les autres moteurs de rendu
  (Edit, H3, etc.) n’ont pas été transformés en files.
- JS Assisted : cache `20260906.1`. Activation après redémarrage du serveur et
  rechargement du navigateur par l’utilisateur.

## Vérifications

Tests ajoutés avec fakes et dossiers temporaires : ordre entre ateliers,
snapshots/seed 0, essai préparé inactif, annulation locale et distante ciblée,
appels concurrents, redémarrage sans nouvelle soumission, perte de connexion,
erreur suivie d’un succès, envoi ambigu, disparition de LoRA, stockage,
worker autonome et parcours HTTP de mise en file atomique.

Ces tests n’ont pas été lancés. Les seuls contrôles effectués sont statiques :
syntaxe Python/JavaScript, structure HTML/identifiants et vérification du diff.
Le comportement réel et l’interface restent à valider par l’utilisateur.
# Fluidité — complément du 9 septembre 2026

Voir [l’audit et les correctifs ciblés](assisted-performance-audit-2026-09-09.md) : admission depuis le catalogue déjà connu avec revalidation fraîche dans le worker, bouton libéré dès l’enregistrement, cartes stables pendant le polling et historique limité avant désérialisation. FIFO, snapshots de réglages, reprise des exécutions et annulation restent inchangés. Mesures passives `Server-Timing` sur le POST d’ajout ; tests préparés, non exécutés.
