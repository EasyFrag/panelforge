# Services IA locaux

État vérifié le 2026-08-08. Ce fichier consigne des capacités observées ; les endpoints et modèles restent configurables et aucun secret ne doit être ajouté ici.

## Accès

| Service | URL préférée | Vérification |
| --- | --- | --- |
| llama.swap | `http://bucket:8083/v1` | `/health`, `/v1/models`, `/running` et chat OK |
| ComfyUI | `http://bucket:8188` | `/system_stats` et `/queue` OK |

- `bucket` est le nom MagicDNS Tailscale ; éviter de figer l'IP `100.x` dans le code.
- llama.swap reste lié à `127.0.0.1:8083` et une règle Tailscale Serve TCP existante publie `bucket:8083` dans le tailnet. Aucun tunnel SSH supplémentaire n'est requis.
- ComfyUI `0.30.1` répond par LAN et Tailscale. Aucun workflow n'a été soumis pendant ce diagnostic.

## Capacités LLM validées

- Le catalogue live contient 18 IDs ; `GET /v1/models` est la source de vérité, pas un ancien `.env`.
- `Qwen3.6-35B-A3B-UD-Q8_K_XL-instruct` : texte, une image et trois images ordonnées validés.
- Le nouvel adaptateur `OpenAICompatibleGateway` a été validé en situation réelle : 18 modèles découverts et inférence une image réussie.
- Cette validation porte sur le modèle MoE actuellement servi. La cible du Prompt Lab est `Qwen3.6-27B` dense, encore absente du catalogue au moment du test.
- `/v1/models` ne décrit pas fiablement les modalités : PanelForge devra conserver des capacités explicitement qualifiées par modèle.

## Points de vigilance

- Les appels ont réussi sans clé API applicative ; l'accès est actuellement protégé par le tailnet. Ajouter une authentification applicative avant d'élargir l'accès.
- Envoyer le JSON en UTF-8 explicite ; un probe PowerShell mal encodé a été rejeté avant inférence.
- Rejouer les probes texte, UTF-8, JSON structuré, une image et trois images après installation de `Qwen3.6-27B` dense.
