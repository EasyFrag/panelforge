# Patch scènes et réponses — 20 septembre 2026

Le patch est implémenté dans `D:\Code\panelforge-krea2-flux`. Il couvre la progression des traitements, la persistance des réglages de rendu par scène et les erreurs de réponse observées dans le dernier audit.

## Comportement

- **◷ Planifié, ambre** : demande enregistrée, en attente du LLM ou d’une étape précédente. **● Bleu** : démarrage/chargement ou génération effectivement signalé par le moteur. **✓ Vert gras** : terminé. **X Rouge gras** : erreur. Les étapes à préparer restent noires. Le démarrage d’un thread ou un préfixe de texte compilé localement ne suffisent plus à afficher « en cours ».
- Les cartes, le sélecteur de scène et le suivi des traitements distinguent l’attente de l’exécution. Vidéo et DLSS indiquent leurs dépendances ; le DLSS non demandé est identifié. Un Plan en échec ne laisse pas le Rédacteur dans une fausse file active.
- Une modification dans le panneau de rendu devient un réglage propre à cette scène. Sauvegarde automatique après environ 800 ms, avec confirmation visible, et sauvegarde attendue avant changement de scène ou lancement. Exemple : régler 8 s, ouvrir une autre scène, revenir → 8 s ; la chaîne utilise cette durée.
- La durée narrative et les prompts existants restent inchangés. Aucun bouton d’application globale. Les paramètres déjà capturés par un traitement lancé ne changent pas rétroactivement. L’action explicite de retour aux réglages communs conserve son rôle.

## Récupération des réponses

Le cas observé `secrets=[]` avec une entrée `knowledge` ayant `secret_id:null` est normalisé localement : cette entrée sans secret est retirée, après validation de ses personnages et de son événement. Le scénario, les faits et le brouillon original sont conservés ; la normalisation est indiquée dans le suivi. Un secret non nul inconnu, un événement invalide ou un personnage inconnu restent bloquants. Si l’arc déclare de vrais secrets, une référence nulle reste bloquante aussi.

Les consignes précisent les IDs autorisés et la différence entre une connaissance de secret et une simple prise de conscience. Une consigne du Plan distingue également les personnages informés, complices et trompés, sans ajouter une étape de relecture.

Pour le JSON mal formé :

1. Les expressions limitées à une chaîne JSON suivie de `.replace("chaîne", "chaîne")` sont résolues par une opération locale sur des données décodées. Aucun code du modèle n’est exécuté ; les autres méthodes et expressions sont rejetées. La taille du résultat est bornée.
2. Si la syntaxe reste invalide pendant une génération, une seule tentative de correction du format est permise. Elle doit préserver toutes les clés et valeurs scalaires dans le même ordre, puis passer toute la validation habituelle. Échec → arrêt, original et diagnostic conservés. Pas de boucle ni de réécriture complète.
3. Aucun appel supplémentaire sur une réponse acceptée ou récupérable localement. Le plafond de sortie reste à 80 000 tokens. Une erreur de contenu ne déclenche pas cette réparation de syntaxe.

## Reprendre le brouillon déjà bloqué

Une fois les traitements en cours terminés, redémarrer PanelForge depuis le worktree actif, puis actualiser le navigateur avec **Ctrl+F5**. Ouvrir l’histoire en échec et utiliser **Revalider le brouillon**. Le bouton est proposé lorsque le brouillon passe la validation locale. Cette action ne relance pas le LLM ; elle reprend le texte conservé. Le parcours reste ensuite à poursuivre pour les vérifications restantes.

Aucune histoire enregistrée n’a été modifiée pendant l’implémentation ; aucun service n’a été redémarré et aucune génération n’a été lancée.

## Vérification

Contrôles statiques uniquement : syntaxe Python via `ast.parse`, syntaxe JavaScript via `node --check` (y compris les scripts embarqués du test navigateur), et `git diff --check`. Ces contrôles ne prouvent pas le comportement à l’exécution.

Des tests ciblés ont été ajoutés ou adaptés, **sans être exécutés**, conformément au choix de l’utilisateur. Commande à lancer manuellement dans PowerShell :

```powershell
Set-Location 'D:\Code\panelforge-krea2-flux'
$env:PYTHONPATH = 'D:\Code\panelforge-krea2-flux\src'
& 'D:\Code\panelforge\.venv\Scripts\python.exe' -m unittest tests.test_story_response_recovery tests.test_long_story_response_contracts tests.test_episodes tests.test_machine_work tests.test_episodes_browser
```

Ces tests utilisent des réponses et services simulés, sans appel LLM ni rendu réel. Le test navigateur dépend du Chromium local et peut être ignoré automatiquement s’il n’est pas installé.

Essai interface conseillé : modifier une durée puis changer immédiatement de scène, revenir, vérifier 8 s et le prompt inchangé ; lancer ensuite la chaîne avec ces choix. Lors de plusieurs préparations manuelles, observer une étape active et les autres planifiées. Le cas du brouillon existant peut être vérifié par la revalidation locale décrite ci-dessus.
