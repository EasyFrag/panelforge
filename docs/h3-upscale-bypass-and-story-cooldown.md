# Bypass H3 et repos des vidéos Histoires

Les recettes courantes H3 Base `0.1.7` et REF2V `0.2.5` choisissent leur branche à partir des dimensions réellement alignées sur 32 pixels :

- cible supérieure aux MP initiaux : upscale latent puis finition ;
- cible égale : décodage direct de la première passe ;
- cible inférieure : même décodage direct, à la résolution initiale, sans réduction.

À dimensions égales, la case temporaire **Forcer l’upscale** réactive l’ancienne branche pour comparer les deux chemins avec une même seed. Elle n’est pas proposée pour BUNNY, les recettes historiques ou une cible de taille différente.

Dans Histoires, la chaîne vidéo applique par défaut 30 secondes de repos entre deux rendus. Le GPU distant reste réservé pendant ce délai ; le LLM local peut continuer. Le garde thermique existant est ensuite évalué avant le rendu suivant et peut prolonger l’attente.

Le suivi distingue la voie LLM locale de la voie GPU distante et conserve les lecteurs vidéo déjà montés pendant le polling. Une mise à jour de statut ne doit donc plus interrompre une lecture en cours.
