# Modèle distinct pour le prompt final

Dans H3 Base et REF2V, le sélecteur **Modèle LLM** pilote la préparation du plan.
Cocher **Utiliser un autre modèle pour le prompt final** affiche un second
sélecteur, avec son propre choix Local · Unsloth. Laisser la case décochée
conserve le même modèle pour les deux appels. Aucun couple Qwen/Gemma n'est imposé.

Activation explicite pour les recettes à deux étapes suivantes, dans les deux écrans :

- Classique Mise en scène `1.0.0`, `classic.cinematic.planned`.
- Combat `1.3.0`, `combat.planned`.
- Sensuel `1.0.0`, `sensual.planned`.

Les identités exactes sont dans `domain/prompt_writer.py`. Les autres recettes
ne proposent pas ce réglage et refusent une surcharge non nulle côté domaine.
Une nouvelle version doit adopter explicitement la capacité.

Le changement concerne uniquement le routage du modèle dans l'appel Writer
existant, y compris sa révision explicite. Il n'ajoute aucun appel. Le plan,
l'intention, les rôles, les consignes, le schéma et les validations restent
identiques. Les images sont déjà réservées au premier appel ; le Writer reçoit
le plan et son contexte sous forme de texte. La qualité réelle avec chaque
modèle doit être évaluée dans l'atelier.

Le choix est enregistré dans la composition (`writer_model_id`, schéma 5),
restauré à l'ouverture et conservé lors d'une duplication dans l'écran, ainsi
que d'une continuation compatible vers H3. Lecture des schémas 1–4 conservée,
sans réécriture à la lecture. Une nouvelle préparation vierge repart sans
modèle distinct. Aucun réglage global ni modification des sessions historiques.

Dans un atelier existant, changer le second sélecteur enregistre le modèle
pour la **prochaine** rédaction, sans invalider le plan ou le prompt déjà
validés. Après un échec, choisir un autre Writer puis relancer seulement le
prompt final. La sélection reste verrouillée pendant un appel dans cet écran.
Le journal LLM existant enregistre le modèle demandé et celui de la réponse ;
le sélecteur n'est pas une attribution rétroactive des anciens prompts.

API : création via le champ optionnel `writer_model_id` du POST composition,
puis PUT `composition/writer-model` avec `writer_model_id` et
`expected_writer_model_id` (null explicite pour revenir au modèle principal).
La valeur attendue et la sauvegarde conditionnelle protègent contre un autre
enregistrement concurrent. Une erreur de sauvegarde est affichée à côté du
sélecteur, qui reprend sa valeur enregistrée. Actualiser les modèles conserve
un modèle choisi devenu absent du catalogue, avec une indication explicite.

Déploiement local : après les traitements en cours, redémarrer le Lab puis
Ctrl+F5. Aucun redémarrage ni appel réel n'a été exécuté pendant le patch.

Tests préparés, à lancer par l'utilisateur :

```powershell
python -m unittest tests.test_prompt_writer_model tests.test_prompt_writer_model_browser tests.test_prompt_composition_storage
```

Ils utilisent des réponses simulées et des transports factices : compatibilité
historique, deux appels avec un ou deux modèles, streaming, reprise du Writer,
validation et persistance API, sélecteurs indépendants et réouverture.
