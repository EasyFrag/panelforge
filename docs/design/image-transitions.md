# Transitions d’images

L’onglet **Transitions**, à côté de l’usine, prépare les vidéos intermédiaires entre des images déjà disponibles. N images ordonnées donnent N−1 transitions H3 first/last.

## Parcours

1. Créer une frise et lui donner un nom dans les réglages communs.
2. Ajouter des fichiers, ou ouvrir **Depuis un atelier** pour choisir des versions précises dans KREA, Qwen ou MiniMax. **Sélectionner la chaîne validée** coche le départ et les résultats acceptés ; les autres essais terminés restent sélectionnables.
3. Réordonner les vignettes par déplacement ou par les flèches. Le bouton de remplacement accepte un fichier ou une version d’atelier. Retirer une vignette ne supprime aucun asset ni projet source.
4. Sélectionner les transitions à préparer. Une action courte peut être saisie dans la liste ; le panneau de droite contient l’indication personnelle et les réglages particuliers.
5. Cliquer sur **Proposer les transitions**. Le LLM voit les deux images de chaque paire, les réglages communs et les indications disponibles. Les propositions sont françaises et restent à relire.
6. Corriger si nécessaire, puis **Valider la sélection** ou **Valider cette transition**.
7. **Envoyer à l’usine** ajoute les versions relues à sa préparation. **Voir dans l’usine** ouvre les unités reçues ; leur lancement utilise le parcours habituel Plan → Prompt → Vidéo, avec DLSS facultatif.

Les champs non enregistrés sont signalés. **Enregistrer** les conserve ; les actions de préparation, validation, import, navigation entre paires et envoi enregistrent également les champs avant de poursuivre. Actualiser permet de recharger une modification venant d’une autre fenêtre, en demandant confirmation avant d’abandonner des champs non enregistrés.

## Miniatures et agrandissement

La frise affiche les images dans une zone de 360 × 252 px sur ordinateur, soit trois fois la taille initiale ; elle reste défilable horizontalement et s’adapte aux écrans étroits.

Toutes les miniatures — frise, paires, comparaison à droite et sélection depuis un atelier — proposent un aperçu flottant au survol ou au focus clavier. Il agrandit l’image visible ×3, dans la limite de l’écran, sans déformer son format. L’aperçu disparaît en quittant la miniature, au défilement ou avec Échap.

Chaque miniature dispose aussi d’un bouton loupe qui ouvre la vue agrandie. Dans la liste des paires, cette loupe ne change pas la transition sélectionnée ; le clic sur l’image ou sur la flèche conserve la navigation habituelle. L’agrandissement reste disponible pendant l’analyse.

Ces ajustements d’affichage se chargent avec **Ctrl+F5**, sans redémarrage du Lab.

## Réglages

Les réglages communs comprennent description de l’ouvrier, rythme, caméra, ambiance sonore, musique, conservation, durée, cadrage et DLSS. Le cadrage automatique choisit le format H3 supporté le plus proche de la première image.

Trois modèles sont paramétrables : propositions visuelles, plan H3 et prompt H3. Les identifiants locaux/serveur du catalogue existant sont conservés ; aucun remplacement silencieux d’un modèle absent. L’analyse des paires nécessite un modèle et un accès capables de lire les images. Les valeurs initiales reprennent les modèles de l’usine : Gemma Unsloth pour les propositions et le prompt, Qwen local pour le plan.

Chaque transition peut remplacer la durée, la caméra et le rythme communs. Un déplacement vers l’intérieur d’un arbre peut ainsi avoir un rythme différent des travaux accélérés. Les paramètres détaillés du rendu restent ajustables dans l’usine.

## Relecture et versions

- Une proposition distingue observations, opération suggérée et incertitudes. Un outil inféré n’est pas présenté comme un fait visible.
- Une intention modifiée manuellement est conservée lors d’une nouvelle analyse. La nouvelle proposition apparaît séparément et ne la remplace qu’au clic explicite.
- Une réponse arrivée après modification des images ou consignes n’est pas appliquée.
- Remplacer l’image centrale retire la validation des deux transitions adjacentes ; les intentions restent consultables. Les autres paires conservent leur validation.
- Réordonner conserve les transitions dont les deux voisins restent les mêmes, et crée celles nécessaires au nouvel ordre.
- La relecture est liée aux images, au texte et aux réglages précis envoyés.
- L’envoi répété de la même version retrouve l’unité existante. Les entrées exactes sont enregistrées avant réception par l’usine pour permettre une reprise après interruption.
- Modifier la frise ne modifie jamais une unité déjà envoyée. Une nouvelle version relue crée une nouvelle unité ; les anciennes restent accessibles.
- L’ordre de la frise détermine celui des nouvelles unités lors de l’envoi. La priorité des unités déjà présentes reste gérée dans l’usine.
- Le retour depuis une ancienne unité signale une frise modifiée ou une transition retirée.

## Exécution et stockage

Projets : `workspace/image_transitions/index.json` et `workspace/image_transitions/transitions-<id>.json`. La sauvegarde est atomique et utilise des révisions explicites. Les références pointent vers des assets précis, avec leur origine dans l’atelier.

Les propositions passent par le gateway LLM partagé, son journal et sa coordination des machines. Un lot est traité paire par paire, avec deux images réduites pour l’analyse et un contexte textuel commun. Fermer l’onglet n’annule pas la tâche côté serveur. Après redémarrage, une analyse interrompue est signalée ; elle n’est pas rejouée implicitement.

L’onglet conserve les liens et les états légers des unités de l’usine. Il ne duplique pas le moteur H3, ses workflows ni les opérations Plan/Prompt. La description de l’ouvrier exprime une continuité souhaitée ; la qualité des raccords et des actions demande une qualification visuelle.

La création autonome de nouvelles images reste le **deuxième volet**, documenté dans `docs/proposals/image-sequence-generation-brief-2026-09-28.md`, sans implémentation dans ce patch.

## Vérifications et mise en service

Préparés : 16 tests de domaine/service, sources et HTTP dans `tests/test_image_transitions.py`, et un scénario navigateur avec API simulée dans `tests/test_image_transitions_browser.py`. Ils couvrent les références exactes, la relecture, la conservation des corrections, les réponses obsolètes, l’envoi dédupliqué et sa reprise après interruption.

**Tests non exécutés**, conformément aux consignes du projet. Aucun appel LLM, rendu ni redémarrage de service effectué. Contrôles statiques : 11 fichiers Python parsés, 5 sources JavaScript compilées sans exécution des scénarios, imports des nouveaux modules et aide du lanceur vérifiés, références HTML et IDs contrôlés.

Pour lancer les tests ciblés depuis le checkout actif, avec `src` dans `PYTHONPATH` :

```powershell
$env:PYTHONPATH = 'D:\Code\panelforge-krea2-flux\src'
& 'D:\Code\panelforge\.venv\Scripts\python.exe' -m unittest discover -s tests -p 'test_image_transitions*.py'
```

Le nouveau backend sera chargé au prochain démarrage habituel du Lab ; actualiser ensuite la page. La validation visuelle se fait alors sur une courte frise, en relisant les intentions avant le lancement dans l’usine.

Sauvegardes et diagnostic isolé du patch : `D:/Code/panelforge/.agent/diagnostics/image-transitions-20260928/`.
