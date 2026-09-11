# Analyse média : crochet JSON final manquant

## Incident et correction

L’appel `llm-79b7038e6cef4bd29d7109070847bf63` du 11 septembre 2026 à 13:06 UTC a reçu les dix captures de l’extrait vidéo et s’est terminé normalement en environ 26 secondes. La réponse contenait l’intention, les observations et les incertitudes, mais le tableau final `uncertainties` n’avait pas son crochet fermant. Le lecteur JSON rejetait donc toute l’analyse. Whisper n’intervenait pas dans cet appel.

La récupération reste locale à `application/media_analysis.py` : après un échec de décodage, elle accepte seulement l’erreur de séparateur à l’accolade finale. L’ajout d’un seul `]` doit produire un objet contenant exactement les trois champs attendus, sans doublon, avec `uncertainties` en dernier. Toutes les validations de contenu, de types et de longueurs sont ensuite appliquées. La liste doit déjà contenir une valeur ; aucune valeur ou fin de phrase n’est inventée.

Exemple structurel : `"uncertainties": ["Point incertain"}` devient `"uncertainties": ["Point incertain"]}`. Les chaînes restent identiques, y compris guillemets, accents et caractères ressemblant à du JSON. Les autres JSON malformés, champs supplémentaires, doublons, types incorrects et réponses signalées comme tronquées restent refusés.

Une récupération acceptée est signalée dans le journal applicatif avec le `call_id`. La réponse brute conservée par la passerelle dans les traces LLM reste inchangée. Aucun appel LLM supplémentaire ni modification des prompts, de H3/REF2V, du stockage ou des fichiers d’interface. Pas de changement de version de cache nécessaire.

## Vérification et reprise

Tests préparés dans `tests/test_media_analysis.py`, à exécuter par l’utilisateur depuis le checkout :

```powershell
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_media_analysis
```

Cas couverts : JSON valide inchangé, récupération compacte et multiligne avec ou sans bloc Markdown, texte préservé, journal corrélé à l’appel, rejets stricts, réponse tronquée non récupérée, conservation et réouverture du résultat, un seul appel malgré une nouvelle consultation.

Contrôles statiques de la version : syntaxe de 50 fichiers Python, 13 JSON et 11 JavaScript, 591 empreintes historiques inchangées, diff du correctif sans erreur d’espacement. Les tests ne sont pas exécutés. Aucun modèle, transcription, rendu ou service n’est lancé ou redémarré. Après ses traitements en cours, l’utilisateur redémarre le Lab pour charger ce correctif serveur. Les anciens échecs ne sont pas rejoués automatiquement ; une nouvelle tentative explicite utilise le lecteur corrigé.

## Version GitHub

Version de livraison : `snapshot-media-analysis-json-2026-09-11`, branche `snapshots/media-analysis-json-2026-09-11` sur `EasyFrag/panelforge`.

Le commit `9c70b51` conserve les évolutions déjà présentes avant ce correctif (Classique, Analyse média, LoRA, navigation et correctifs récents). Le correctif du crochet est un commit distinct. Les points de restauration antérieurs, dont `stable-avant-masque-2026-09-06`, sont conservés.
