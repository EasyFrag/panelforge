# Sons de fin des rendus

Un carillon bref de trois notes ascendantes signale les générations image et vidéo réussies. Il partage le mécanisme Web Audio existant, avec une mélodie distincte des deux notes de fin LLM. Les sons LLM et d'échec existants restent inchangés ; aucune nouvelle option ou dépendance.

Raccordements : H3 Base et Ref2V (atelier de rendu commun), KREA Assisted, Edit, Image Lab simple, Batch, Changer de vue, Video Lab et rendus Production V1/V2. Social Lab prépare les contenus et utilise les ateliers de rendu correspondants. En Production/Batch, le succès d'un rendu ne déclenche plus en plus l'ancien bip LLM de fin du traitement global.

Le suivi utilise les états reçus par les rafraîchissements existants de l'interface. Aucun nouvel appel serveur, polling global ou changement de file ComfyUI. Une seule notification par identifiant dans l'onglet, même après plusieurs rafraîchissements ou retours de réponse périmés. La première lecture d'un historique terminé reste silencieuse. Les nouveaux résultats apparus entre deux lectures d'une même collection sont détectés même si le navigateur n'a pas reçu leur état intermédiaire. Les retouches locales par masque sont exclues.

Chaque résultat d'une série peut être signalé ; ceux reçus à moins de 120 ms d'intervalle sont regroupés pour ne pas superposer les mélodies. Échecs/annulations ne produisent pas le carillon de succès. Le son dure environ 0,56 s et conserve l'enveloppe de volume existante.

Le Lab doit rester ouvert et suivre le rendu : ce n'est pas une notification système après fermeture de l'onglet. Comme pour les LLM, l'audio est activé par une interaction souris/clavier ; si le navigateur le suspend ou bloque l'audio, l'atelier continue normalement. Le suivi des autres projets reste celui déjà assuré par chaque écran, sans service de surveillance supplémentaire.

Caches des dix scripts concernés : `20260907.8`. Recharger la page pour utiliser le changement ; aucun redémarrage du service n'a été effectué.

Test hors ligne préparé : `python -m unittest tests.test_render_notifications`. Il utilise Chromium local et un AudioContext simulé, sans audio réel, LLM, génération ou serveur. Cas couverts : distinction des mélodies, historique silencieux, dédoublonnage, rendus rapides, série, rafraîchissements périmés, annulations/échecs, composition locale et indisponibilité de l'audio. Tests UI/cache existants actualisés. **Tests non exécutés par l'agent** ; seuls les contrôles statiques de syntaxe ont été faits.
