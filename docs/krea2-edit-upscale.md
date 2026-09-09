# KREA2 Edit — amélioration facultative des détails

Implémentation du 2026-09-08, à expérimenter par l'utilisateur. Aucun rendu, appel LLM, test ni redémarrage exécuté par l'agent.

## Utilisation

1. Redémarrer le Lab et recharger la page pour charger le patch.
2. Dans **Modifier avec KREA2**, sélectionner un essai réussi dans **Après**.
3. Cliquer **Améliorer les détails**. Le panneau affiche le candidat ciblé ; changer ensuite le comparateur ne change pas cette cible.
4. **Lancer**, ou ouvrir **Modèle d'amélioration** pour choisir un autre upscaler.
5. À la fin, **Après** sélectionne le nouvel essai, **Avant** son candidat parent. Comparer, retoucher, utiliser comme feedback ou **Valider et continuer**.

ClearReality (`4x-ClearRealityV1.pth`) est présélectionné s'il est disponible ; le choix reste modifiable. La liste vient d'UpscaleModelLoader au moment d'ouvrir le panneau. Aucun téléchargement automatique. Ouvrir le panneau ou sélectionner un modèle ne lance aucun traitement. Une erreur conserve le panneau ; une nouvelle tentative avec la même sélection réutilise l'identifiant de demande.

Le bouton n'ajoute pas d'étape à la frise. L'essai s'appelle, par exemple, **Essai 5 — Amélioré 1** ou **Essai 5 — Retouche 1 — Amélioré 1**. Les numéros des générations restent indépendants. Le prompt en cours, les paramètres de génération et les brouillons de masque ne sont pas réécrits. Les étapes validées/historiques restent immuables ; utiliser la reprise d'étape existante pour les retravailler.

## Images et masque

- La sortie conserve exactement les dimensions orientées de la source de l'étape. Le facteur natif du modèle, par exemple ×4, est intermédiaire ; il ne multiplie pas les dimensions finales par quatre.
- Le modèle reçoit la génération d'origine à sa résolution native, normalisée en PNG. Le graphe agrandit avec le modèle puis redimensionne en Lanczos aux dimensions demandées.
- Pour une retouche enregistrée, on traite la génération sous-jacente, puis on réapplique l'harmonisation et le masque enregistrés. Les pixels décodés de source hors masque sont conservés par le compositeur existant.
- Reprendre le masque d'un résultat amélioré charge l'image améliorée avant composition et le masque enregistré. Un nouveau dessin ne repart donc pas du composite aplati.
- Comparer un autre upscaler sur un candidat déjà amélioré repart de la génération initiale, avec le masque du candidat sélectionné. Aucun empilement de passes d'upscale.
- Les limites de préparation/composition restent 16 MP et 25 Mio par image ; orientation EXIF respectée, écart de proportions supérieur à 1 % refusé. Aucun recalage ou recadrage automatique.

La netteté, les textures et d'éventuels halos sont à comparer visuellement à la même échelle. La disponibilité d'un fichier modèle ne constitue pas une validation de sa qualité ou de son chargement.

## Contrats

- Workflow explicite `image.esrgan.upscale@0.1.0`, opération `image.upscale`, dans `workflows/image.upscale/esrgan/0.1.0`. Cinq nœuds natifs : LoadImage → ImageUpscaleWithModel (+ UpscaleModelLoader) → ImageScale → SaveImage. Aucun KSampler, VAE, LLM ou prompt dans ce graphe.
- Empreinte du graphe : `3308cc9a46b17065e100bd04dbbf472c9552c658eaf19fd5970aa849a2f8c782`. Identifiants et liaisons dans le manifeste/graphe, sans identifiant de nœud dans le code de fonctionnalité.
- Essai de type `upscale`, avec référence du workflow d'amélioration, modèle, génération initiale, parent sélectionné, masque, harmonisation, dimensions et image améliorée avant composition. La recette et les paramètres Edit hérités restent disponibles pour **Reprendre prompt et réglages**.
- Suivi ComfyUI Edit existant : préparation, mise en attente, exécution, réussite/échec, annulation et récupération d'une exécution enregistrée après redémarrage. Aucun worker/service supplémentaire. Même exclusion des rendus Edit simultanés que les générations ; pas de nouveau gestionnaire de file global.
- GET `/api/image-lab/krea2-edit/upscalers` : catalogue à la demande. POST `/api/image-lab/krea2-edit/sources/{source_id}/attempts/{attempt_id}/upscale` : modèle et `request_id`, candidat persistant et suivi existant. Une répétition de la demande ne crée ni candidat ni soumission supplémentaire ; une autre sélection avec le même ID est refusée.
- Stockage **schéma 8**, lecture des schémas 1–7. Pas de migration globale ; les nouvelles sauvegardes nécessitent ce code pour être lues. Aucun original remplacé.
- Feedback, prochaine source, frise et export prennent l'`output_asset_id` sélectionné. L'export comprend l'image finale, les entrées d'upscale, son résultat avant masque et la provenance ; masque/source de composition également exportés si concernés. Les paramètres de génération hérités sont distingués du traitement d'amélioration.
- Cache Edit JS `20260908.4`, CSS `20260908.1`. Carillon de fin existant réutilisé ; aucune modification du moteur audio. Tag `stable-avant-masque-2026-09-06` conservé.

## Vérification préparée

Tests **non exécutés**, avec images temporaires et ComfyUI/LLM simulés :

```powershell
python -m unittest tests.test_krea2_upscale tests.test_krea2_upscale_browser tests.test_krea2_retouch tests.test_krea2_retouch_browser tests.test_krea2_edit_web tests.test_krea2_edit_versions_browser
```

Scénarios : sélection d'un ancien essai, nouvelle sortie sans changement du prompt, masques vide/plein/partiel et transition douce, harmonisation et pixels protégés, réouverture, retouche d'une amélioration, changement d'upscaler sans accumulation, persistance/anciens schémas, feedback/validation/export, doublon HTTP, catalogue Comfy ancien/nouveau, modèle absent, échec, annulation et récupération d'exécution. Navigateur : ouverture sans rendu, cible stable, double clic, nouvelle tentative après erreur, fermeture pendant chargement, consultation des étapes validées.

Contrôles effectués par l'agent : analyse AST des fichiers modifiés, compilation JavaScript et des scénarios navigateur sans invocation, vérification des champs HTTP, IDs HTML et empreinte/liaisons du graphe. Les appels distants se limitent à trois GET de descriptions de nœuds ComfyUI.
