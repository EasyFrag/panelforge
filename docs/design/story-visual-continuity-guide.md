# Histoires : clarté et continuité visuelle

Implémentation du 22 septembre 2026, après l’[audit Pommes, Citron et Kiwina](../diagnostics/audit-histoires-continuite-2026-09-22.md).

## Ce qui change

- L’écriture privilégie une relation compréhensible, une occasion, un acte ou une ellipse lisible, puis une conséquence. « Ma copine » établit le couple ; un prénom seul ne le fait pas. Un médecin disponible dans l’univers n’est pas un complice obligatoire, et une fin avec retournement n’exige pas plusieurs intrigues.
- La relecture des scènes voit les paroles, gestes et situations de départ, ainsi que les épisodes précédemment joués. Elle ne reçoit pas la bible, les secrets, les états finaux déclarés ni le résumé dramatique. La conception de l’arc et les contrôles des événements restent en place ; la relecture des scènes est centrée sur la compréhension du spectateur.
- Un registre distingue l’identité d’un personnage de son physique, sa tenue et les objets transmis. Chaque attribut persiste indépendamment. Un changement de muscles ne répare pas un vêtement déchiré.
- Seuls les objets importants pour la compréhension ou la reconnaissance méritent un suivi. Le suivi textuel ne crée aucune tâche image. Une invention volée et une puce cassée reçue en échange restent deux objets distincts.

Ces changements réutilisent les appels narratifs existants. Une image de variante reste un travail supplémentaire seulement si elle est choisie et générée.

## Parcours conseillé

1. Créer une histoire suivie et écrire l’intention du nouvel épisode. Pour une suite, mettre l’ancien récit dans **Continuer une histoire · contexte précédent**. Le bouton **Créer une suite** préremplit cette mémoire et conserve le lien au projet précédent.
2. Après le développement, ouvrir **Continuité**, sous le résumé du scénario. Vérifier le drame en une phrase, les éléments suivis et les dates de leurs changements. Les corrections sont enregistrées sans appel LLM.
3. Utiliser **Suivi textuel** pour un accessoire simple ou un ajustement mineur. Choisir **Image de référence** pour un objet distinctif ou un changement d’apparence important. Cocher une variante seulement à l’état qui la justifie.
4. Valider la fabrication et préparer les images d’identité, les lieux et les objets suivis dans le lot habituel. Les variantes ne sont pas cochées par défaut dans ce lot, afin de les créer à partir de l’identité retenue.
5. Pour une variante, choisir **Modifier avec Qwen** dans Continuité. Cela ouvre un projet Qwen avec l’identité comme source et une intention d’édition préremplie. Aucun appel ou rendu n’est lancé par cette action. Converser, générer et comparer dans Qwen, puis revenir à la fabrication et choisir **Résultats Qwen → Utiliser**. L’import d’une image dans la fiche reste possible.
6. Les scènes utilisent automatiquement la variante lorsque l’état est acquis. L’onglet Scènes affiche les références résolues et leur numérotation effective. Les anciens prompts ne sont pas écrasés : une préparation affectée passe à actualiser.

**Exemple Citron.** Le changement « carrure massive, débardeur déchiré » est acquis *pendant* la scène 4. Cette scène commence avec l’apparence précédente ; la scène 5 commence avec la carrure massive et le débardeur déchiré. Si la scène suivante décrit seulement des épaules plus larges, la tenue déchirée et la dernière ancre visuelle restent conservées. Un nouveau changement majeur, y compris un retour à l’apparence initiale, peut justifier une nouvelle variante.

**Exemple Kiwina.** Suivre l’invention avec une forme, des matières et une image commune aux scènes où elle apparaît. Suivre séparément la puce cassée, éventuellement en texte seul. Un verre banal ou un meuble déjà reconnaissable dans le décor n’a généralement pas besoin de fiche supplémentaire.

**Participant silencieux.** Si Banane est visible mais manque dans le casting déclaré, un diagnostic invite à vérifier sa présence. Un nom dans la prose ne suffit pas à l’ajouter automatiquement. Dans Continuité, ajouter Banane et cocher les scènes où elle est visible permet d’y envoyer sa référence.

## Compatibilité et limites

- Contrat des nouveaux appels : **2.2.0** ; le moteur et le stockage restent V2. Les brouillons 2.1 restent reconnus. L’annexe `scenario.visual_continuity` est facultative.
- Une annexe visuelle invalide ne rejette pas à elle seule le scénario et ne déclenche pas une nouvelle boucle LLM. Le texte est conservé, un avertissement apparaît, l’annexe reçue reste dans le brouillon original, et seuls les états valides précédents/hérités sont conservés. Corriger le suivi dans l’interface avant la fabrication si nécessaire. Les erreurs du scénario principal conservent leurs contrôles habituels.
- Aucune migration des fabrications existantes. Elles gardent leurs entrées jusqu’à une modification explicite de Continuité. Les modifications dans Fabrication concernent cette copie ; celles du scénario préparent les nouvelles fabrications et la mémoire narrative des suites.
- Les variantes acquises et les objets peuvent reprendre une image d’une fabrication précédente de la même histoire ou de sa lignée. Les objets utilisent leur ID explicite. Les références choisies manuellement restent vérifiables et remplaçables.
- Les modifications de continuité sont refusées pendant les traitements de cette fabrication. Les prompts/rendus déjà enregistrés conservent leurs entrées. Les conflits entre fenêtres demandent une actualisation plutôt qu’un écrasement silencieux.
- Si l’état d’une variante déjà illustrée change, confirmer ou remplacer l’image avant une nouvelle préparation. L’ancienne image et les anciens essais restent disponibles.
- Un écart entre la durée prévue par le prompt et celle du rendu est signalé ; le prompt n’est pas réécrit automatiquement.
- Le registre renforce la transmission des consignes. La fidélité visuelle et la lisibilité finales restent à évaluer sur les prochains rendus ; elles ne sont pas garanties par la seule structure des données.

## Vérification à lancer par l’utilisateur

L’agent a effectué des contrôles statiques uniquement. Aucun test fonctionnel, appel LLM, rendu ni redémarrage n’a été lancé pour cette implémentation.

Depuis `D:\Code\panelforge-krea2-flux`, avec l’environnement habituel :

```powershell
D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_story_visual_continuity tests.test_episode_visual_continuity tests.test_story_contracts_v21 tests.test_long_stories tests.test_episodes
```

Ces tests emploient des données enregistrées ou des services simulés et des répertoires temporaires. Pour l’essai réel, redémarrer le Lab lorsque les traitements en cours sont terminés, puis actualiser la page. Vérifier en priorité : couple explicitement présenté, ellipse comprise, muscles et déchirures maintenus, Banane référencée même silencieuse, invention identique entre deux scènes.
