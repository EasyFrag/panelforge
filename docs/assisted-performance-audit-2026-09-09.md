# Audit de fluidité Assisted — 9 septembre 2026

**Complément après retour utilisateur** : le rendu courant REF2V est désormais **0.2.1** avec les deux MP modifiables, à **0,2 / 0,2**, comme H3 courant. « Réutiliser le seed » est coché par défaut dans les deux ateliers. La description ci-dessous de la première passe fixe reste exacte pour **l’ancien 0.2.0**, conservé dans Historique ; elle ne décrit plus le rendu courant. Les valeurs d’un essai repris restent celles enregistrées.

## Constats et limites

Inspection du code et des fichiers locaux, sans appel au Lab, à ComfyUI ou à un LLM. Aucun test ou rendu exécuté. Il ne s’agit pas d’une mesure du temps réel entre un clic et son résultat ; aucun gain chiffré n’est annoncé.

Au moment de la lecture : **313 ateliers Assisted**, 5 023 788 octets de `project.json` au total. Le dernier atelier `krea2-create-0ef1603e4ae64877b6d5a382598211f6` contient **22 essais réussis**, 8 messages et environ 142 ko de JSON. Aucun essai en attente dans cet instantané. Une lecture et un décodage JSON bruts des 313 fichiers ont pris environ **38 ms**, sans reconstruction/validation des objets métier, sans sérialisation HTTP et sans concurrence avec leurs verrous. Ce chiffre ne mesure donc ni le coût complet de la file ni la lenteur ressentie.

| Point | Ce que le code faisait | Intervention |
| --- | --- | --- |
| Images qui disparaissent pendant l’attente | Toutes les cartes et leurs images `loading=lazy` étaient détruites/recréées chaque seconde, même sans changement. | Garder les cartes par identifiant et ne reconstruire que celles qui changent. Garder aussi le nœud image quand seul le feedback ou les métadonnées changent. |
| Conversation et arbre | Les deux étaient reconstruits à chaque polling, avec perte possible de l’ouverture des détails. | Actualiser seulement lorsque leurs données changent. |
| Clic avant mise en file | Vérification complète checkpoints + LoRA avant chaque ajout : parcours récursif des dossiers configurés, métadonnées/sidecars, appels d’inventaire ComfyUI. Dossiers par défaut sur `\\sshfs.r\malmo@bucket\...`. | Accepter rapidement une sélection présente dans le dernier catalogue chargé. Les sélections inconnues déclenchent toujours la découverte ; le worker refait une validation fraîche avant l’envoi. |
| Bouton bloqué après enregistrement | Après le POST réussi, l’interface attendait encore un GET de la file globale, puis redessinait à nouveau la galerie. | Réactiver dès le POST terminé ; le polling met ensuite les positions à jour. Invalider les réponses de polling antérieures au clic. |
| Historique de gauche | `list(30)` désérialisait les 313 ateliers avant d’en retenir 30. | Trier les dates avant de charger les seuls projets demandés. |
| File globale | `_next_queue_order` et `_pending_renders` relisent toujours tous les ateliers, sous le verrou applicatif. Le worker inspecte aussi cette file lorsqu’il attend. | Point restant à mesurer. Pas de nouvel index persistant ou de cache de projets dans cette passe. |

Le cache des sélections ne change ni les chemins configurés, ni les paramètres enregistrés, ni la découverte de nouveaux checkpoints à l’ouverture/au rafraîchissement du catalogue. Si un fichier connu a été retiré depuis ce chargement, l’essai peut être admis dans la file puis signalé en échec par la vérification du worker avant ComfyUI. Le cache évite précisément que cette vérification réseau bloque chaque clic ; il ne retire pas la vérification avant exécution.

Les assets avaient déjà des en-têtes de cache HTTP `immutable`. Le clignotement ne suffit donc pas à conclure à un téléchargement complet de chaque image : la destruction des éléments DOM, leur chargement différé et leur remise en page constituent un problème distinct.

## H3 / REF2V et éléments à surveiller

- La capture « Rendu actuel 0.2.0 » correspond au rendu **REF2V**. Son paramètre `megapixels` est la **sortie finale**, et le graphe conserve **0,2 MP pour la première passe**. Cette valeur n’est pas exposée par son manifeste. Les deux champs sont maintenant visibles, nommés « MP avant upscale » / « MP sortie », avec indication explicite et champ désactivé pour une première passe fixe. H3 actuel 0.1.3 et BUNNY gardent leurs deux valeurs modifiables. Aucun manifeste historique changé.
- Le libellé de révision H3 0.3.0 contenait littéralement `?` à la place de caractères accentués. Corrigé en « dialogues et caméra compilée » ; ce n’était pas un réglage du navigateur.
- DLSS : le correctif de l’enregistrement des métadonnées livré précédemment attend toujours une validation utilisateur. Aucun upscale relancé pendant cet audit.
- « Replacer dans un décor » reste une fonction expérimentale pour la qualité visuelle. Aucun élément de cet audit ne permet de l’accuser de bloquer la file lorsqu’elle n’est pas utilisée.
- Les boutons secondaires répétés sur chaque carte augmentent la densité visuelle. Une prochaine passe peut regrouper preset / remplacement de décor dans des actions secondaires et limiter les vieux essais visibles à la demande. **Aucune suppression décidée ici** : conserver feedback, enregistrement et reprise immédiats paraît plus utile que déplacer tout l’atelier.
- Les prompts de combat inspirés de BUNNY sont inscrits dans [le backlog](backlog.md), sans ajout de recette ou activation automatique d’un LoRA.

## Vérification préparée et prochaine observation

Les régressions préparées portent sur l’admission sans scan, la revalidation avant envoi, la découverte d’un modèle inconnu, l’historique limité, les cartes stables lors du polling et des fins de rendu, la sélection DLSS et la possibilité d’enchaîner deux ajouts sans attendre le GET de file. Elles restent **à exécuter par l’utilisateur** : `tests.test_krea2_assisted_render_queue`, `tests.test_krea2_assisted_performance`, `tests.test_krea2_assisted_poll_browser`, `tests.test_krea2_assisted_web`.

L’API POST `.../attempts?enqueue=true` expose désormais un en-tête **Server-Timing** (`prepare`, `worker`, `serialize`, durées en millisecondes). Il est visible dans les outils réseau du navigateur, sans activer de diagnostic ni déclencher d’appel supplémentaire. Il permet de distinguer préparation/admission, réveil du worker et sérialisation ; il ne couvre pas le transport, l’attente avant entrée dans la route ou le dessin dans le navigateur. Il n’est pas enregistré dans les anciens runs.

Après son prochain rechargement du Lab, l’utilisateur peut observer ses rendus habituels : retour du bouton, stabilité des images et délai d’envoi à ComfyUI. Si la lenteur persiste, mesurer séparément les scans réseau du worker et le parcours de la file avant d’entreprendre un index global ou de supprimer des fonctions.
