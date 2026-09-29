# Usine : rangement des bases, résultats compacts et archives

Statut : implémenté localement après validation. L’utilisateur a choisi un
quatrième onglet principal Archives. La migration des quatre bases existantes
a été effectuée lors du tour précédent ; aucun média ou journal runtime n’a
été déplacé/modifié pendant cette implémentation.

## Rangement validé et migration effectuée

Organisation visée pour toutes les familles :

```text
DLSS/<famille>/<date>/
  video_DLSS.mp4
  video_Instagram.txt
  base video/
    video_Video.mp4
```

La vidéo sans DLSS appartient à base video, y compris si DLSS est désactivé
ou échoue. Ouvrir le dossier continue à mener au dossier de date ; Voir la
vidéo privilégie le DLSS disponible, sinon la base. Le texte IG reste à la
racine de date. Cette politique est désormais appliquée aux nouveaux exports.

Inventaire en lecture seule des dossiers déclarés par les quatorze fiches
exportées au moment du contrôle : Petits hommes/2026-09-26 contient quatre
bases, douze DLSS et seize TXT ; Histoire/2026-09-26 contient deux DLSS.
Toutes les fiches publiées pointent déjà vers un DLSS, aucune vers une base.

Les quatre bases migrées sous
D:/AI/PanelForge/LocalOutput/dlss/Petits hommes/2026-09-26/base video :

- Incendie_France_bd2bb8f3_d14ab3d2_Video.mp4
- Petits_homes_dans_un_desert_61de97fe_fde28b8f_Video.mp4
- Petits_hommes_dans_la_glace_5cb52892_baaed9b5_Video.mp4
- Secheresse_Coree_ebc1f624_1e1b8f09_Video.mp4

Chaque export a été relié à une seule fiche et à son asset source par IDs,
puis taille et SHA-256 vérifiées contre asset.json. Sources/destinations
absolues et absence de jonction contrôlées, pas d’écrasement. Déplacement
natif PowerShell, empreinte vérifiée après. Médias sources, DLSS, TXT, journal
usine et chemins de livraison inchangés. Rapport conservé dans le repo principal :
.agent/factory-base-migration-2026-09-26.json.

La migration est autorisée et faite ; ne pas redemander cette autorisation.
Aucune prétention à avoir migré des fichiers hors des dossiers connus de l’usine.
Le plan de publication place la base dans base video ; publish crée et
revalide ce sous-dossier avant d’écrire. Le champ folder et le TXT conservent
la racine de date. Un IG tardif garde le dossier affecté à sa vidéo ; une reprise
DLSS conserve la base dans son sous-dossier et publie le DLSS à la racine.
Les contrôles d’empreinte, de collision et de chemin sont conservés.

## Résultats et Archives compacts : implémentation

L’utilisateur demande trois colonnes dans la cellule État. Le statut reste
un texte ; deux rangées suffisent pour un résultat terminé avec toutes sorties :

| Colonne 1 | Colonne 2 | Colonne 3 |
| --- | --- | --- |
| Terminé | Voir le DLSS | Ouvrir le dossier |
| Texte IG | Archiver | Supprimer |

Pour une erreur, afficher En erreur et Reprendre la chaîne ; l’action unique
de reprise est conservée. Les actions indisponibles sont absentes. La grille utilise trois colonnes, avec le statut dans la première case et
deux rangées pour les six éléments habituels. Deux colonnes sous 700 px.
Les notes d’erreur/export s’étendent sur la largeur. Dans Archives, Restaurer
remplace Archiver ; les cinq étapes et leurs durées restent consultables.

## Archivage : comportement implémenté

- Quatrième onglet Archives, avec compteur distinct. Les fiches archivées
  quittent Résultats et son compteur ; aucun archivage automatique.
- Archiver sur la ligne ou dans la fiche ; Archiver la sélection pour un lot.
  Le filtre À archiver isole les réussites éligibles avant une sélection globale.
- Seules les lignes réussies avec toutes leurs étapes réussies/désactivées et
  leur export final réussi sont éligibles. Le contenu publié doit correspondre
  au contenu courant, y compris un texte IG arrivé après la vidéo. Les erreurs,
  annulations, récupérations et travaux en cours ne sont pas masqués.
- Vérification serveur de toute la sélection avant écriture, avec contrôle
  des révisions. Une ligne inéligible fait refuser tout le lot, sans archive partielle.
- archived_at persiste séparément du statut de traitement. Les anciens journaux
  sans ce champ restent lisibles ; aucune migration des traitements requise.
- Archives conserve sources, intentions, prompts, durées, historique et fichiers.
  Vidéo/DLSS, dossier, copie/TXT IG, détails et agrandissement d’image restent accessibles.
- Restaurer dans Résultats, unitaire ou par sélection, enlève seulement archived_at,
  puis ouvre Résultats sur les fiches restaurées. Aucune étape n’est remise en attente.
- Les fiches archivées ne sont ni éditées ni reprises directement ; restaurer
  d’abord. Supprimer garde son sens existant et conserve les médias.
- Le renvoi identique reste dédoublonné et affiche Déjà archivé / Archives,
  avec Ouvrir vers le bon onglet. Dupliquer crée une nouvelle Préparation et
  l’ouvre ; les métadonnées de localisation sont conservées, aucun ancien ID
  de rendu/essai/DLSS n’est repris et l’archive reste intacte.
- La publication automatique ignore les archives. L’archivage ne déplace aucun
  fichier et ne déclenche pas de génération.

## Vérifications et prise en compte

Contrôles statiques réussis : AST de sept fichiers Python, sept imports,
parsing V8 du script usine et de huit fragments de fixtures navigateur ;
31 identifiants usine uniques et quatre onglets dans le balisage ;
git diff --check. Avertissement existant Starlette/httpx à l’import du client
de test. Aucun test fonctionnel, navigateur ou traitement exécuté.

Régressions préparées : dix cas service/HTTP dans test_video_factory_archives,
trois nouveaux cas de rangement et adaptation de l’idempotence dans
 test_video_factory_results, scénario navigateur complet dans test_video_factory_web.

```powershell
python -m unittest tests.test_video_factory tests.test_video_factory_archives tests.test_video_factory_results tests.test_video_factory_web tests.test_video_factory_timing_retry
```

Cache video-factory.js/css : 20260926.patch4. Au prochain redémarrage habituel
du Lab, recharger avec Ctrl+F5. Aucun service redémarré, aucun résultat existant
archivé ou restauré par l’agent. Les quatre bases déplacées précédemment restent
dans base video ; aucun second déplacement nécessaire.
