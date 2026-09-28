# Diagnostic DLSS : WinError 5 sur le journal local — 28 septembre 2026

## Conclusion

Aucun lien direct établi avec la préparation LAN/Tailscale ou l'intégration Git.
Le patch réseau n'est pas implémenté. L'échec est un refus Windows de remplacer
un JSON du workspace local, après un rendu ComfyUI réussi. Le processus ayant
éventuellement bloqué ce remplacement n'est pas identifié.

## Faits vérifiés en lecture seule

- Job : dlss-01d6ce55f8aa2617fbbf48200e05cff1.
- Endpoint DLSS : http://127.0.0.1:8188.
- Exécution : 6ecbf906-d96a-4356-9ce6-5495b0ebe8a5.
- Début : 09:14:57 UTC ; échec journal enregistré à 09:17:11 UTC, soit 11:17:11 Paris.
- ComfyUI /history de cette exécution : success, completed=true.
- JSON actuel lisible, status=failed, output_asset_id=null, pas de report_asset_id,
  keyframes ni candidate_id ; enhanced_asset_id, metadata et chemin local présents.
- Vidéo existante : D:/AI/PanelForge/LocalOutput/dlss/dlss-01d6ce55f8aa2617fbbf48200e05cff1_00001_.mp4.
- Taille : 142559048 octets ; métadonnées mémorisées 1268 x 2206, 60 fps,
  10,133333 secondes, audio présent. Pas de visionnage ni contrôle perceptuel.
- Le répertoire classé Petits hommes affiché dans l'interface ne désigne pas le
  fichier JSON en échec et ne prouve pas une livraison finale déjà effectuée.
- Erreur : remplacement .dlss-k0gafdbk.tmp vers le JSON du job sous workspace/dlss.
  Le temporaire a été nettoyé ; le code le retire dans finally.
- Fichier JSON non marqué lecture seule (Archive) ; workspace et dossier dlss sont
  des dossiers locaux sans jonction relevée. ACL héritées avec droits Modify pour
  les utilisateurs authentifiés, FullControl administrateurs/système ; aucun Deny affiché.
- Un serveur PanelForge observé : interpréteur PID 23480 sur 7861 et 8766, enfant du
  lanceur venv PID 22952. Les deux PID ne démontrent pas deux serveurs indépendants.
- LocalDlssJobs est créé une fois et partagé avec DlssService/runtime dans run_lab.py.
  Son RLock protège get/list/save dans cette instance ; ne pas attribuer sans preuve
  le blocage aux lectures ordinaires du même objet ou au mobile.
- Écriture dans infrastructure/storage/dlss_jobs.py : fichier temporaire, flush,
  fsync puis os.replace sans nouvelle tentative sur un refus transitoire.
  Aucun diff depuis le commit f2a61a5 du 9 septembre 2026, ni avec le snapshot 7036248.
- Après le premier refus, le gestionnaire d'erreur a pu enregistrer status=failed
  dans le même journal : indice d'un problème ponctuel plutôt que d'un refus permanent.
- Recherche dans les JSON de jobs existants : une seule occurrence WinError 5,
  ce job ; zéro fichier illisible. Lecture avec FileShare.ReadWrite | FileShare.Delete
  pour ne pas bloquer les remplacements réalisés par le processus applicatif.

## Hypothèse et limites

Un autre lecteur, un logiciel de protection ou un accès externe temporaire peut
bloquer un renommage Windows. Ce mécanisme est compatible avec les faits, mais
aucun processus n'a été identifié au moment du refus. Pas de preuve permettant
d'attribuer l'incident au mobile, à un antivirus ou à un outil de diagnostic précis.

Le passage de master au snapshot n'a ni suivi ni modifié workspace. Il ne change
pas la routine de stockage du job. Une éventuelle influence indirecte par un
processus externe ne peut pas être exclue sur le seul historique disponible.

## Suite envisageable, non appliquée

- Ajouter des tentatives courtes et bornées au remplacement atomique pour les
  erreurs Windows transitoires pertinentes ; préserver l'erreur finale, les verrous
  et l'atomicité. Ne pas contourner un vrai refus de permission.
- Vérifier par tests ciblés succès après verrou bref, abandon après délai borné,
  conservation du JSON précédent et nettoyage du temporaire.
- Reprendre l'enregistrement depuis l'exécution ComfyUI existante plutôt que recréer
  un rendu : son identifiant est conservé et l'historique success est encore disponible.
  La reprise normale le réutilise tant qu'il reste disponible ; aucune reprise effectuée.
- Le correctif de persistance est distinct du futur profil réseau.

Aucun code applicatif, job, média, permission, service ou configuration modifié.
Aucun rendu, appel LLM, test fonctionnel, relance, copie ou redémarrage effectué.

Références :
- https://docs.python.org/3/library/os.html#os.replace
- https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew
  (FILE_SHARE_DELETE : le partage doit autoriser suppression/renommage).
