# PanelForge — Contrats des histoires longues 2.1, 22 septembre 2026

Cette sauvegarde publie le correctif des erreurs successives de rédaction et l’amélioration du bouton de récupération, depuis la version `2673c24` du 22 septembre. Le contrat d’échange des nouveaux appels narratifs passe en 2.1.0 ; le stockage narratif et la fabrication restent compatibles avec le moteur V2 existant.

- Branche : `snapshots/long-stories-contracts-2.1-2026-09-22`
- Tag : `snapshot-long-stories-contracts-2.1-2026-09-22`

## Changements

- **Contrats partagés** entre consignes, schéma envoyé au serveur et validation locale. Les nouvelles réponses associent directement chaque scène à ses métadonnées ; le casting et les index sont assemblés par l’application.
- **Corrections ciblées** des champs de l’arc et des scènes, avec vérification de l’empreinte du document de base et conservation des passages non concernés.
- **Réactions et transitions** autorisées sans créer artificiellement un événement, avec ancrage sur une scène antérieure. Les indices publics, confirmations et connaissances des personnages sont distingués.
- **Récupération bornée** des fautes JSON reconnues, localement. Une syntaxe encore ambiguë est conservée sans réécriture automatique invérifiable. Les erreurs isolées de métadonnées peuvent faire l’objet d’une seule proposition de réparation sur des champs autorisés, sans modifier les actions ou dialogues.
- **Diagnostics regroupés et faisabilité** : contrôles de références, causalité, couverture, estimation de durée et avertissements de langue. Une surcharge manifeste peut déclencher directement la correction éditoriale avant la relecture LLM.
- **Historique et consommation visibles** : brouillons précédents téléchargeables, résultats source/correction distincts, compteurs et durées cumulées persistants au fil des reprises.
- **Interface de récupération** : brouillon lisible et bouton « Récupérer le brouillon · sans appel LLM » placé dans son panneau. Pour un brouillon échoué non récupérable, le bouton reste visible mais désactivé avec une explication. Il disparaît pendant un nouvel appel.

La création des personnages, les prompts de production, la vidéo, le DLSS et les réglages techniques par scène sont conservés. Le plafond de sortie reste à 80 000 tokens.

## Validation et limites

Contrôles statiques Python/JavaScript et du diff effectués. Les tests de régression sur réponses enregistrées et passerelles factices sont inclus, **sans avoir été exécutés par l’agent**, conformément au choix de l’utilisateur. Aucun appel LLM, rendu ou redémarrage n’est lancé pour cette publication.

L’utilisateur a relancé le parcours et signale qu’il semble fonctionner. Les deux nouvelles rédactions avaient été acceptées lors de la dernière inspection ; leur relecture était encore en cours. Ce retour ne constitue pas une validation exhaustive de tous les modèles ou scénarios.

Le lanceur demande les sorties JSON contraintes par défaut. Leur application effective dépend du serveur ; un refus explicite du schéma est expliqué et n’entraîne pas de relance silencieuse. Les options `--llm-structured-output off` et `--local-llm-structured-output off` permettent de conserver la validation locale sans contrainte au décodage pour un serveur incompatible.

Les contrôles de durée et de langue restent des estimations. La continuation d’une ancienne histoire vers le moteur long V2 reste un chantier distinct.

## Reprise et documentation

Pour le changement d’interface, recharger avec **Ctrl+F5**. Pour les changements Python sur un serveur qui ne les aurait pas encore chargés, redémarrer seulement après les traitements actifs.

Le bouton de récupération concerne le **dernier brouillon en échec**. Après une relance LLM, l’ancien brouillon reste dans les archives ; il n’est pas remis en place automatiquement par ce bouton. Les nouvelles scènes déjà rédigées peuvent poursuivre leur parcours normal.

- [Guide du correctif et de reprise](../diagnostics/correctif-contrats-histoires-2026-09-22.md)
- [Audit des erreurs et des traces](../diagnostics/audit-contrats-histoires-2026-09-22.md)

Les projets runtime, médias, traces LLM complètes et secrets restent hors de cette sauvegarde. Les preuves locales citées dans l’audit ne sont pas publiées ; seule une fixture réduite de régression est incluse.

Tests ciblés, à lancer par l’utilisateur depuis le dépôt avec son environnement Python :

```powershell
$env:PYTHONPATH = 'src'
python -m unittest tests.test_story_response_recovery tests.test_story_contracts_v21 tests.test_story_schema_transport tests.test_long_story_response_contracts tests.test_long_stories tests.test_story_workflow
```
