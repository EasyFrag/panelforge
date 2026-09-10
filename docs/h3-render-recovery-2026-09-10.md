# Blocage H3 par un essai orphelin — 10 septembre 2026

## Diagnostic et réparation immédiate

Le nouveau projet `h3-render-1df62d1dc6104b2d8b5b865787ba70b0` conservait cinq essais préparés, jamais soumis, à la suite du message `another H3 Base render is already active`.

Le blocage global venait de l’essai `attempt-2afce7589f3d4d289b853ed8d768f8be` dans `h3-render-39bf331e2f294e0cbd671c93b5e6474e`, encore `running` depuis le 9 septembre à 17:17 UTC. Son exécution `bddc4cf0-85f8-48e9-9a90-12187928d244` était absente de l’historique Bucket et des files running/pending. Les files étaient vides à la première observation. Cela établit la perte du suivi distant, pas la cause du nettoyage de l’historique ni l’absence d’un éventuel fichier vidéo sur disque.

Après une nouvelle lecture historique → file → historique, sauvegarde du JSON original puis mise à jour atomique du seul état de cet essai vers `failed`, avec un message explicite. Prompt, réglages, identifiant d’exécution, workflow compilé et autres essais conservés. Comparaison des octets originaux avant remplacement pour refuser l’écriture si le projet avait changé pendant l’intervention.

Sauvegarde locale : `D:\Code\panelforge\workspace\h3_render_projects\h3-render-39bf331e2f294e0cbd671c93b5e6474e\recovery\project-before-orphan-recovery-20260910.json`.

Le GET de ce projet sur le Lab existant, port 7861, confirme l’essai en échec et le précédent essai réussi préservé. Aucun essai H3/REF2V n’était encore queued/running/cancel_pending au dernier relevé. Les cinq candidats préparés ne sont ni supprimés ni soumis automatiquement. Le déblocage est effectif sans redémarrage ; le code préventif sera chargé au prochain démarrage habituel par l’utilisateur.

## Correction préventive

- Pour un essai running/cancel_pending sans worker local, l’absence dans l’historique déclenche une consultation de la file, puis une seconde lecture de l’historique. Si l’exécution est toujours absente, elle passe en échec et libère l’admission H3/REF2V.
- Une exécution présente dans la file, une réponse invalide ou une erreur réseau ne constitue pas une preuve de disparition : son état reste conservé. Les workers locaux encore propriétaires de leur essai ne sont pas réconciliés par ce chemin.
- Une vidéo terminée entre les lectures est importée normalement. Un état distant `interrupted` est reconnu même avec `completed: false`.
- L’admission recharge le projet après réconciliation. Elle ne réécrit plus un ancien snapshot qui pourrait remettre un essai récupéré en état actif dans le même atelier.
- Le message de conflit réel est en français et identifie l’atelier et le numéro d’essai bloquants.
- La lecture de file Comfy refuse les réponses dont l’un des tableaux running/pending est absent ou null, au lieu de les interpréter comme une file vide.

La politique existante d’un rendu H3/REF2V actif à la fois est conservée. Ce correctif ne crée pas une file de rendus H3 et ne relance, n’annule ou ne supprime aucune exécution distante. Les réglages de seed, MP, recettes et LoRA restent inchangés.

## Vérification

Tests préparés dans `tests/test_h3_render_recovery.py` : récupération dans le même projet et dans un autre, annulation en attente, exécution distante running/pending, panne réseau aux différentes lectures, réponse invalide, worker local actif, fin de rendu pendant la réconciliation, interruption et protection contre une file incomplète. Tous les appels Comfy y sont simulés ; soumettre ou annuler un workflow fait échouer le scénario.

**Tests non exécutés.** Contrôles effectués : analyse syntaxique AST des trois fichiers Python concernés, revue des contrats et contrôle du diff. La réparation du projet réel a utilisé seulement des GET distants et une écriture locale sauvegardée ; aucun import applicatif de vérification, appel LLM, génération, annulation distante ou redémarrage.

Commande pour l’utilisateur : `python -m unittest tests.test_h3_render_recovery`.
