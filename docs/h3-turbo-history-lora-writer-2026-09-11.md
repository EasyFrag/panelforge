# H3/REF2V — correctifs du 11 septembre 2026

## Turbo BUNNY et historique

« Ajouter le Turbo BUNNY » est directement visible sous la recette, coché par défaut. Décocher retire le Turbo supplémentaire du workflow, sans changer le checkpoint, les LoRA créatifs, les MP, le seed ni les steps. Cela permet les essais avec un checkpoint qui contient déjà Turbo ; le choix du checkpoint ne déduit pas automatiquement sa distillation de son nom.

Les réglages « Steps et aperçu BUNNY » restent accessibles dans un bloc repliable. Les boutons 9/4/5 et 30/25/5 changent seulement les steps, explicitement ; ils ne changent pas le checkbox. Les valeurs personnalisées et la désactivation sont conservées dans le brouillon et à la reprise d’un essai. Le serveur savait déjà contourner le nœud Turbo : pas de modification des manifests ou des graphes. Les defaults MP/seed du rendu classique sont inchangés.

Les récents projets H3 `8a977e6eeaaf47a5a7f98487999d980b` et `f312d533fe8d4cdcb92bc5a6ec0f93b8` sont présents et réussis. La liste des ateliers excluait les profils Classique Mise en scène, ajoutés depuis la première version de cette liste. Les deux profils H3/REF2V sont maintenant acceptés. L’origine Analyse média n’est pas un filtre et n’a pas supprimé les résultats. La limite de 30 sessions récentes, toutes familles avant filtrage, reste celle de l’API existante ; ce patch ne refond pas la pagination de l’historique.

## Fiches LoRA vidéo

Un bouton « i » ouvre la fiche du LoRA sélectionné dans H3/REF2V, sur les quatre lignes et sur les anciens contrôles à un LoRA. Même présentation que KREA2 : nom, annotations de force, notes, favori, lien CivitAI, actualisation et aperçus disponibles. Les forces annotées sont informatives ; elles ne changent jamais les réglages du rendu.

La fiche est chargée au clic, même pendant un rendu. L’inventaire existant H3 est réutilisé ; aucun scan des fichiers, hash ou chargement de modèle. La récupération CivitAI/rgthree suit le comportement existant de la fiche KREA, à son ouverture si nécessaire ou à l’actualisation explicite. Une absence de métadonnées ou un échec réseau ne doit pas modifier le brouillon du rendu.

Adaptateur injecté `H3LoraResourceCatalog` : réutilise les annotations/cache du catalogue existant, avec inventaire et rechargement exclusivement distants. Stockage séparé `workspace/h3_lora_resources.json` ; `krea2_resources.json` inchangé. Routes sous `/api/h3-render/video-loras/resources`, sans dépendance au service KREA2 de génération.

## Rédaction Classique : plans et phases

Trois réponses du 11 septembre, 12:09–12:10 UTC, ont été reçues correctement puis rejetées : `llm-1b9f09b3807542a69615840ea9d2aec9`, `llm-56633c951cb1493a882d93cfc9a0a9c0`, `llm-ac3cd46952a24d27b3228532ae9bac17`. Le Plan approuvé contenait un plan continu avec deux phases caméra ; le Writer envoyait deux objets `shots`, chacun contenant une seule phase. Erreur différente des balises de langue et du faux positif caméra corrigés précédemment.

- Le schéma transmis au Writer borne exactement le nombre de plans et le nombre de phases de chacun ; un squelette structurel explicite accompagne la demande initiale et les révisions.
- Le seul regroupement automatique de plans autorisé est un Plan approuvé à un plan/deux phases avec une réponse à deux plans/une phase chacun. Les deux paragraphes restent identiques et dans le même ordre. Le compilateur conserve la caméra, les temps et les validations du Plan approuvé.
- Toute autre incohérence de structure reste rejetée. Les vrais mouvements caméra libres, coupes ajoutées, répliques inventées ou balises invalides ne sont pas rendus acceptables par ce regroupement.
- Modification limitée à Classique Mise en scène 1.0. Les contrats, schémas et politiques Combat ne changent pas. Le parcours reste deux appels LLM ; aucune relance automatique supplémentaire.

Un ancien candidat brut n’est pas réécrit dans le workspace par ce patch. Après rechargement du serveur, relancer la rédaction depuis le Plan validé suffit pour utiliser le nouveau contrat ; aucune nouvelle analyse des médias requise.

### Complément : clé `phases2`, 11 septembre à 12:59 UTC

L’appel `llm-795cf8d48b2e47ba90dad84884612282` contient un seul objet `shots`, mais deux propriétés : `phases: [paragraphe 1]` et `phases2: [paragraphe 2]`. Le Plan approuvé (`llm-37bfa3830b1e4fa58ae6aedc80e5bc90`) prévoit bien un plan à deux phases. Le nouveau squelette était présent dans la demande ; la clé inventée ne venait pas des instructions. Le message `Extra inputs are not permitted` est la cause ; l’erreur de tableau vide est une conséquence de la validation du même objet.

Le parseur Classique réunit désormais ces deux listes dans `phases` avant validation, uniquement si le nombre de plans correspond, si ce plan prévoit exactement deux phases et si chaque liste contient une seule chaîne non vide. Aucun texte n’est supprimé ou réécrit. Une clé supplémentaire, une phase déjà présente, une liste vide, un type incorrect ou un nombre de plans incohérent reste rejeté. Les validations normales caméra/langue/paroles/structure restent actives après normalisation. Aucun troisième appel LLM ni modification Combat. Le schéma et le squelette rappellent maintenant explicitement qu’un plan possède une seule clé `phases`, avec les paragraphes dans le même tableau.

Tests neutres ajoutés dans `tests/test_classic_cinematic.py` : même compilation exacte pour H3 et REF2V, mono/multiplan, conservation du JSON brut et rejet des cas ambigus, mouvements caméra libres et paroles non approuvées. Préparés, non exécutés. Aucun candidat utilisateur ni Plan sauvegardé modifié par l’agent ; après redémarrage du Lab par l’utilisateur, le Plan validé peut être conservé pour relancer uniquement la rédaction.

## Validation par l’utilisateur

Contrôles statiques Python/JavaScript/HTML et diff effectués ; tests ci-dessous préparés, **non exécutés**. Aucun LLM, génération, navigateur, import applicatif de vérification ou redémarrage lancé par l’agent.

```powershell
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_h3_bunny_browser tests.test_h3_checkpoints tests.test_h3_history_browser tests.test_h3_lora_resources tests.test_h3_four_loras_browser tests.test_classic_cinematic tests.test_prompt_boundary_regressions tests.test_lab_web
```

Après la fin des traitements, redémarrer le Lab puis recharger la page pour les nouvelles routes et scripts (cache 20260911.3). Vérifier dans H3 et REF2V :

1. Turbo visible, coché sur une nouvelle recette BUNNY ; décocher garde 9/4/5 ou les valeurs personnalisées. Sélectionner explicitement les steps classiques si souhaité. Reprendre un ancien essai restaure ses propres réglages.
2. Les ateliers Mise en scène récents apparaissent ; leur ouverture retrouve le prompt et les essais existants.
3. Le bouton « i » cible le bon fichier après déplacement d’une ligne ; notes/favoris se retrouvent en rouvrant la fiche. Les forces/ordre/seed et les tâches en cours restent identiques.
4. Un plan continu à deux phases compile comme un seul plan, avec les deux phases ordonnées. Un véritable plan supplémentaire ou une phase manquante reste bloqué.

Les points de restauration Git existants sont conservés. Aucune publication supplémentaire réalisée.
