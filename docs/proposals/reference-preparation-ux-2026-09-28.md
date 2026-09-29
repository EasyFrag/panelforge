# Préparation des références : accès aux fiches avant lancement

## Problème et résultat

Les cartes de références dépendaient exclusivement des éléments du dernier lot lancé. Cocher une référence ne mettait à jour que le bouton de lancement ; aucune carte n’apparaissait avant de générer.

Le panneau affiche maintenant les cartes dès la sélection, avec l’image retenue lorsqu’elle existe, même sans lot. Chaque ligne possède aussi un bouton « Ouvrir la fiche », indépendant de la case de sélection. Les cartes sont placées avant le bouton de lancement.

Pendant un lot, les cases permettent de consulter les références et de préparer la sélection suivante. Elles ne changent pas le lot actif. Les résultats du dernier lot restent accessibles avec leurs actions de validation ; le lancement d’un second lot demeure bloqué pendant le traitement. Les images validées affichent la référence actuellement retenue, y compris après une nouvelle sélection dans la fiche.

L’ouverture d’une fiche sauvegarde les modifications en cours, ouvre la bonne référence, mémorise le choix et amène le champ de sélection à l’écran. La reprise automatique des réglages d’une fiche vierge est évitée pendant un traitement, afin de ne pas créer de modification implicite lors d’une consultation. Les protections existantes des fiches occupées restent actives.

## Périmètre

Trois fichiers du checkout actif D:/Code/panelforge-krea2-flux :

- `src/panelforge/features/lab/static/episodes.js` : galerie indépendante du lancement, navigation partagée, consultation pendant les lots.
- `src/panelforge/features/lab/static/episodes.css` : bouton par ligne et disposition adaptée aux écrans étroits.
- `src/panelforge/features/lab/static/index.html` : explication courte, ordre galerie/lancement, libellé « Fiche de référence », nouvelles URL de cache JS/CSS.

Aucun endpoint, génération, scénario, prompt narratif, image, sélection persistée ou service modifié. Les améliorations d’écriture et de rendu relevées dans les deux audits restent conservées pour un correctif distinct.

## Vérification effectuée

- Compilation syntaxique V8 du JavaScript final, sans exécution du code applicatif : OK.
- Identifiants HTML concernés uniques et cartes situées avant le lancement : OK.
- `git diff --check` sur les trois fichiers : OK, hors avis Git habituels de normalisation LF/CRLF.
- Lecture HTTP locale du HTML, du JS et du CSS : 200, contenu exactement identique aux fichiers corrigés. Le serveur déjà lancé les sert sans redémarrage ; recharger la page suffit, les URL des ressources ont été renouvelées.
- Relecture du diff par rapport aux sauvegardes prises avant la tâche, afin de préserver les nombreux changements préexistants.
- Aucun test fonctionnel ni navigateur exécuté, conformément à AGENTS.md du checkout actif ; aucun appel LLM ni rendu de vérification. Aucun nouveau test ajouté pour cette modification d’interface limitée.

## Recette utilisateur

1. Après avoir enregistré une éventuelle saisie en cours, recharger la page.
2. Cocher une référence existante : sa carte et son image doivent apparaître avant tout lancement.
3. Ouvrir une fiche depuis la ligne ou la carte, puis une autre après une modification : la première saisie doit être conservée.
4. Pendant un lot déjà lancé, consulter une autre référence : les résultats et la progression du lot doivent rester visibles, sans nouveau lancement.
5. Une proposition non validée doit conserver son bouton de validation ; une référence sans image doit rester ouvrable pour préparer sa fiche.

Sauvegardes, diff et reçus de vérification : D:/Code/panelforge/.agent/diagnostics/reference-preparation-ux-20260928/.
