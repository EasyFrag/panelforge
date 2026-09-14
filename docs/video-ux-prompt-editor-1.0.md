# UX vidéo et recettes LLM — 1.0

Implémentation du patch validé le 14 septembre 2026. Un redémarrage du Lab
est nécessaire pour charger les nouveaux services et routes ; recharger
ensuite la page. Aucun service n'a été redémarré automatiquement.

## Rendu H3 Base / REF2V

Recette, checkpoint et preset sont regroupés. Les MP initiaux/après upscale,
durée, ratio, seed avec Réutiliser et musique restent visibles. Les quatre
LoRA sont repliables avec résumé et fiches ; un interrupteur remplace le
sélecteur technique de profil. Les paramètres enregistrés sont conservés.

Le sélecteur BUNNY applique les anciens raccourcis Rapide 9/4/5 ou Classique
30/25/5. Il conserve le Turbo, le checkpoint, les LoRA, les MP et la seed.
Une modification des steps donne Personnalisé. Turbo et aperçu sont accessibles
dans Réglages avancés. Le sampling reste celui des workflows existants ; les
nouveaux presets EROS attendent leur adaptation technique distincte.

## Éditer les consignes

**Recettes LLM** dans la barre supérieure, ou **Consignes LLM** près de la
préparation, ouvre l'éditeur. Sélectionner la recette, la révision et les
consignes : Plan, Rédaction, ajustement avant rendu ou après rendu. Les règles
conditionnelles sont accessibles par une case supplémentaire.

**Enregistrer et appliquer** crée une révision persistante. Un autre onglet
ayant changé la version active provoque un conflit explicite au lieu d'écraser
sa modification. **Appliquer cette version** réactive une révision antérieure.
La portée reste un couple recette/version, propre au mode et à la famille.

Un Plan déjà préparé conserve son paquet de consignes pour la Rédaction,
même après modification de l'active. Un nouveau Plan ou ajustement utilise
l'active. Les choix séparés de modèles Plan/Rédaction sont conservés.

**Voir le prochain appel**, depuis un atelier existant, construit le message
système et son contexte sans appeler de modèle. Il affiche la révision réellement
retenue par le prochain appel, qui peut être celle du Plan déjà validé. Pour
la Rédaction, un Plan approuvé est nécessaire. Les brouillons non enregistrés
doivent être enregistrés avant cet aperçu.

Voir [le rangement des fichiers](../prompt_sources/README.md).

## Échanges après rendu

**Échanges LLM** dans une carte de rendu donne accès aux requêtes et réponses
archivées : messages exacts, modèles, révisions, erreurs et raisonnement fourni
par le modèle. L'historique de l'atelier dans l'éditeur montre aussi les appels
ayant échoué. Le journal technique tournant de vingt appels est conservé à côté.

La préparation et les échanges de l'atelier sont liés au rendu lors de sa
création. Un prompt modifié manuellement est signalé ; ses modifications ne
sont pas attribuées au LLM. Les variantes DLSS utilisent l'ID de leur rendu
d'origine, sans créer d'appel LLM fictif. Les anciennes traces non enregistrées
ne sont pas reconstituées à partir des consignes actuelles.

## Correctifs et compatibilité

- Le parseur reconnaît « Durée cible : 12.95 secondes. » et distingue cette
  durée des repères d'action, tout en refusant deux vrais totaux incompatibles.
- Classique r2 explicite les préfixes de cible caméra acceptés, dont `beside`
  et `along`, et évite `alongside` sans changer le validateur global.
- Stockage des compositions en schéma 6, lecture des schémas 1 à 5 conservée.
  Les révisions enregistrent l'ID d'appel et la révision des consignes.
- Bibliothèque historique et sources actuelles séparées ; pas de migration
  automatique des anciennes recettes vers les parcours actuels.

## Vérifications

Analyse syntaxique Python et JavaScript, structure HTML et identifiants,
contrôle du diff. Comparaison structurelle des onze fonctions externalisées :
les 61 fragments initiaux sont identiques aux constantes et interpolations
précédentes. Aucun appel LLM, rendu ni test fonctionnel exécuté par l'agent,
conformément aux instructions du projet.

Tests préparés pour l'utilisateur :

```powershell
Set-Location D:\Code\localQ\.panelpatch
$env:PYTHONPATH = Join-Path (Get-Location) "src"
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_prompt_recipes tests.test_prompt_composition_storage tests.test_prompt_writer_model tests.test_classic_cinematic tests.test_llm_call_logs tests.test_h3_render_controls_browser tests.test_lab_web
```

Essai UI conseillé : reprendre un rendu existant et vérifier ses réglages ;
modifier une consigne Classique, enregistrer, lancer une nouvelle préparation,
ouvrir ses échanges puis réactiver la version précédente. Garder P1 I2V et
P2 analyse média adaptative pour les itérations suivantes.
