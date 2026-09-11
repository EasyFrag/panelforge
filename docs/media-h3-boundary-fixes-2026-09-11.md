# Analyse média et Plan H3 — correctifs du 11 septembre 2026

## Diagnostic

Lecture seule des journaux locaux : les appels Classique Mise en scène `llm-6658345f33f143a69879619fb06dd1a9` (11:42:03 UTC) et `llm-07f29e7459624e639226a3c605949911` (11:42:34 UTC) ont reçu un Plan JSON complet. Les deux Plans contenaient une balise de parole sans préfixe de langue. Le second contenait aussi une indication d’absence de mouvement, `rather than any camera motion`, prise à tort pour une directive caméra libre. Échec de validation applicative du Plan, avant le second appel et avant ComfyUI ; pas un manque de capacité du modèle vidéo.

Dans l’analyse média correspondante, des citations parenthétiques de captures avaient été incluses dans l’intention. La consigne autorisait de numéroter les images pour justifier les observations sans délimiter suffisamment l’intention transférable. Ces numéros ne correspondent pas nécessairement aux références choisies ensuite dans H3/REF2V.

## Intention transférable

Nouvelles consignes **visuelles 1.0.1 / avec paroles 1.1.1** ; versions 1.0.0 / 1.1.0 conservées sur disque. Les indices sont réservés aux observations/incertitudes. L’intention doit décrire directement sujets/actions/états et chronologie, sans transformer les numéros de capture en timestamps ni inventer ce qui manque.

Un nettoyage local retire uniquement les citations entre parenthèses/crochets, comme `(images 8–10)`, sans modifier les mots des dialogues entre guillemets. Les renvois intégrés à une phrase ne sont pas supprimés à l’aveugle : le candidat reste éditable avec un avertissement, et son enregistrement/transfert demande de les reformuler. Les observations et l’intention brute du LLM restent conservées.

Les anciennes analyses sont nettoyées lors d’un enregistrement ou transfert explicite. Le navigateur reprend le texte retourné par le serveur avant le transfert H3/REF2V. Aucun atelier H3/REF2V existant, brouillon en cours ou journal n’est réécrit. Cache d’intégration **20260911.2** ; pas de nouveau choix de priorité à l’action, qui reste en discussion.

## Langue et caméra

Le schéma du nouveau Plan Classique demande `spoken_languages`, un nom de langue par entrée de `spoken_lines`, dans le même ordre. Les actions déclarent toujours les balises canoniques. Quand le LLM omet une balise de langue, le compilateur la complète seulement à partir de la langue explicitement déclarée pour ces mots exacts, ou d’une balise déjà présente dans le Plan approuvé. Aucun texte ajouté, traduit ou réordonné, aucune détection approximative de langue. Les langues contradictoires sont rejetées. Le Writer peut réutiliser cette information sans appel supplémentaire.

Les anciens Plans valides restent lisibles sans le nouveau champ grâce à leurs balises existantes. Un ancien brouillon dépourvu à la fois de balises de langue et de métadonnées demande une correction explicite du Plan, ou une nouvelle préparation avec le schéma corrigé. La langue n’est jamais choisie arbitrairement. Classique conserve son parcours en deux appels ; aucun changement créatif de Combat ni des anciennes recettes.

Le validateur caméra commun accepte désormais les mentions explicites d’absence de mouvement (`without camera movement`, `rather than any camera motion`, etc.). Il conserve les contrôles de mouvements libres, de cibles, de modificateurs et de clauses compilées. Ce correctif de validation général est adopté et couvert pour Classique et Combat ; aucune consigne de famille n’est importée dans l’autre.

## Vérification utilisateur

Tests préparés avec exemples neutres, **non exécutés par l’agent** :

```powershell
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_prompt_boundary_regressions tests.test_minimax_h3_protocol tests.test_classic_cinematic tests.test_combat_cinematic tests.test_media_analysis tests.test_media_transcription tests.test_media_analysis_browser tests.test_h3_render
```

Couverture : citations/ranges, quotes et temps préservés, ancien enregistrement, transfert du texte réellement sauvegardé, renvoi ambigu laissé éditable, caméra négative acceptée et vrai mouvement libre rejeté, Plan/Writer anglais et français, métadonnées absentes/contradictoires, dialogues non inventés, indépendance des schémas Classique/Combat.

Contrôles statiques réussis : syntaxe de 13 fichiers Python et trois sources/scénarios JavaScript, aucune liaison HTML manquante ou ID dupliqué, 591 empreintes d’anciens assets inchangées, anciennes consignes média 1.0.0 / 1.1.0 intactes. Aucun test, appel LLM, rendu, import applicatif de vérification ou redémarrage de service. Après ses traitements, l’utilisateur redémarre le Lab et recharge la page pour obtenir les nouveaux contrats. Aucun commit, push ou tag créé ; points de restauration antérieurs préservés.
