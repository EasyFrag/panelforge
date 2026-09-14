# Image Lab : catalogue en arrière-plan

Patch du 11 septembre 2026, limité au chargement d’Assisted et Edit et à leur catalogue partagé.

## Correction du retour utilisateur du 13 septembre

L’indicateur avait été inséré directement dans la grille de l’atelier, après la barre de navigation. Il prenait donc la colonne de gauche, décalait les contrôles dans celle de droite et repoussait les résultats à la ligne suivante. Il est désormais placé dans un emplacement du panneau latéral, pour Assisted et Edit. Les projets récents Assisted passent avant le formulaire ; « Nouveau projet » est repliable et s’ouvre automatiquement si aucun projet n’existe. La liste récente défile dans un espace limité.

L’ouverture d’un projet peut être remplacée par un autre clic pendant son chargement. La requête précédente est abandonnée, une réponse tardive ne remplace pas le dernier choix et un délai de quinze secondes libère l’interface avec un message visible. Les actions LLM/rendu restent protégées par leur verrou habituel. Les erreurs d’ouverture apparaissent à côté des projets.

Autre défaut corrigé : une réponse de catalogue était considérée comme appliquée avant la fin de l’affichage. Une exception pouvait donc laisser des contrôles incomplets et empêcher un nouvel essai avec une réponse identique. La signature n’est désormais validée qu’après un affichage réussi ; l’initialisation statique d’Edit est également reprise si nécessaire. Le message distingue une erreur de lecture du catalogue d’une erreur d’affichage et distingue les modèles LLM des ressources image.

Constat en lecture seule le 13 septembre : cache présent, 38 checkpoints et 60 LoRA, sans avertissement enregistré. Le Lab ne répondait plus sur `127.0.0.1:7861` lors de l’intervention ; seule l’écoute Python Unsloth était visible. Cela ne permet pas de conclure à la cause du message « catalogue indisponible » rencontré précédemment. Son texte complet a été demandé. Aucun serveur redémarré.

Cette correction est limitée aux assets statiques **20260913.1** : Ctrl+F5 suffit lorsque le Lab est démarré. Les tests préparés comprennent désormais le véritable HTML, CSS, sélecteur LLM et module Assisted, avec requêtes factices, pour contrôler la grille, l’ouverture des projets pendant le chargement, les réponses tardives et la reprise après une exception d’affichage. Tests non exécutés selon les consignes du projet ; vérification visuelle en fonctionnement restant à faire.

Le diagnostic relevait environ 7,7 s pour le spec Assisted, contre 0,07 s pour ses projets récents. La lecture répétée des fiches rgthree sur SSHFS représentait environ 6,2 s. L’interface attendait ces données avant d’autoriser la navigation. Ces mesures décrivent l’ancien comportement ; le gain après patch reste à mesurer dans le Lab.

## Comportement

- Projets, catalogue, presets et file de rendu sont demandés indépendamment. Ouvrir un projet Assisted n’attend plus la lecture de la file globale. Les trois ateliers récents d’Edit et leur bouton d’expansion sont conservés.
- Le dernier inventaire léger des checkpoints/LoRA est enregistré dans `<workspace>/krea2_inventory_cache.json`. Sa portée inclut les dossiers configurés et l’URL ComfyUI ; un changement de configuration ne réutilise pas un inventaire d’un autre serveur.
- Après cinq minutes, un accès déclenche une actualisation en arrière-plan. Un seul scan est partagé entre Assisted et Edit, même avec plusieurs onglets. Les lectures du cache n’attendent pas le verrou de découverte distante. Le bouton **Actualiser les modèles** force une découverte, sans charger de modèle ni soumettre de tâche.
- Les modèles LLM ont une découverte séparée, partagée par passerelle et mise en cache en mémoire. Leur première liste après redémarrage peut encore arriver plus tard ; elle ne retarde pas les projets ni le catalogue ComfyUI.
- En cas d’échec, le dernier inventaire reste affiché avec un message discret. Les tentatives automatiques sont espacées d’au moins trente secondes. Une sélection disparue reste visible comme indisponible ; aucun autre modèle n’est choisi à sa place.
- Le spec ne lit plus toutes les sidecars et n’embarque plus descriptions, mots entraînés et aperçus. Le **i** demande seulement la fiche sélectionnée. Ses métadonnées locales sont réutilisées pendant cinq minutes ; CivitAI reste une recherche explicite. Favoris, noms personnalisés, classements et notes continuent d’être enregistrés dans `krea2_resources.json` et sont répercutés immédiatement.
- Une actualisation conserve les réglages saisis, le prompt, le projet ouvert, les forces LoRA et le masque. Le worker Assisted vérifie toujours les ressources avant soumission, en lisant les inventaires sans parcourir toutes les fiches.

Les autres consommateurs du catalogue, dont Batch et les fiches H3, conservent leur contrat existant. Aucun projet, workflow, modèle, paramètre de sampling ou contenu de recette n’est migré.

## Validation et activation

Contrôles statiques Python/JavaScript et diff uniquement. Les tests sont préparés pour exécution par l’utilisateur, conformément à `AGENTS.md` :

```powershell
python -m unittest tests.test_image_catalog_cache tests.test_image_catalog_browser tests.test_krea2_assisted_web tests.test_krea2_assisted_performance tests.test_krea2_batch_catalog tests.test_h3_lora_resources
```

Les nouveaux tests utilisent des inventaires factices, des fichiers temporaires, et pour les tests DOM le Chromium local. Ils ne contactent pas Bucket, ne démarrent pas le Lab et ne génèrent rien. Les contrôles de cache statique des tests UI existants ont également été actualisés.

Après les traitements en cours, redémarrer le Lab avec la commande habituelle, puis recharger la page. Aucun redémarrage de ComfyUI ou d’Unsloth n’est nécessaire pour ce patch. Le premier accès construit le cache pendant que les ateliers sont déjà consultables. Vérifier ensuite :

1. Ouvrir plusieurs projets pendant l’actualisation des modèles.
2. Dans Edit, conserver un prompt saisi, une force LoRA et un masque en cours pendant une actualisation.
3. Ouvrir une fiche avec le **i**, la fermer pendant son chargement, puis la rouvrir.
4. Au redémarrage suivant du Lab, vérifier que le catalogue ComfyUI revient depuis le cache.

Le patch n’a pas redémarré les services ni lancé ces tests, un LLM ou une génération. Assets statiques concernés : version `20260913.1` après la correction du retour utilisateur. Le patch DLSS image déjà présent est conservé.
