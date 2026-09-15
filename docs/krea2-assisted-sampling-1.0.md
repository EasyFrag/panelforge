# Presets de rendu KREA2 Assisted — 1.0

Patch du 15 septembre 2026, limité à Création assistée.

Dans **Paramètres du prochain rendu**, le sélecteur **Preset de rendu** propose :

| Preset | Passe 1 | Passe 2 |
| --- | --- | --- |
| Actuel (défaut) | 8 · er_sde / simple | 2 · er_sde / simple |
| Finition 4 steps | 8 · er_sde / simple | 4 · er_sde / simple |
| Moody · Beta · expérimental | 8 · euler_ancestral / beta | 4 · euler_ancestral / beta |

**Réglages des deux passes** est replié initialement. Chaque passe possède ses
steps (entier de 1 à 50), sampler et scheduler. Une modification manuelle passe
le sélecteur à **Personnalisé**. Rechoisir un preset réapplique ses six valeurs.

Les CFG restent à 1,1 puis 1,0 ; les denoise à 1 puis 0,30. L'agrandissement
latent reste ×1,5. Un changement de preset conserve checkpoint, LoRA, prompt,
ratio, MP et seed. Le checkpoint ne sélectionne pas implicitement un preset.
Les variantes sont des essais proposés, sans garantie de gain de qualité.

Chaque clic **Lancer un rendu** sauvegarde les valeurs dans l'essai et le
brouillon de sa branche. Les modifications suivantes ne changent pas les rendus
déjà dans la file. **Reprendre réglages**, la réouverture du projet et le retour
dans une branche restaurent le sampling enregistré. Un ancien essai sans ces
champs reprend Actuel 8+2. Les actualisations du catalogue et le polling des
rendus ne réinitialisent pas les saisies en cours.

Le sampling est consultable en survolant les informations du rendu et dans
son fichier de métadonnées. Les presets de style partagés continuent à appliquer
modèle/LoRA selon leur fonctionnement existant ; le sampling appartient aux
essais Assisted. Aucun contrôle ajouté dans Batch, Modif, H3/REF2V ou DLSS.

L'extension de workflow `image.generate.assisted/krea2-sampling@1.0.0` référence
explicitement le graphe Batch `krea2-community@0.2.0` et son SHA-256. Seuls six
bindings définis dans son manifest sont modifiables ; le compilateur et le
graphe Batch existants restent intacts. Le preset Actuel produit les mêmes
paramètres de calcul. Le stockage Assisted passe au schéma 9 et lit les schémas
1 à 8 sans migration à la lecture. Preset/version et valeurs réelles sont
enregistrés ensemble, avec vérification de cohérence côté serveur.

Après installation : **redémarrer le Lab puis Ctrl+F5**. Aucun service ni rendu
n'a été lancé par l'agent. Contrôles AST Python, syntaxe JavaScript (y compris
fixtures assemblées), HTML, hash du workflow et diff effectués. Tests fonctionnels
préparés, à lancer par l'utilisateur depuis le checkout actif :

```powershell
& D:\Code\panelforge\.venv\Scripts\python.exe -m unittest tests.test_krea2_assisted_sampling tests.test_krea2_assisted_web tests.test_krea2_assisted_render_queue tests.test_krea2_assisted_ui tests.test_krea2_assisted_sampling_browser tests.test_krea2_assisted_poll_browser
```

Les tests utilisent des fichiers temporaires et des transports simulés. Les
tests navigateur nécessitent le Chromium local de Playwright et n'appellent
aucun LLM ni ComfyUI. La qualité des images reste à évaluer par l'utilisateur.
