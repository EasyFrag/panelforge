# CONTINUITY

## Goal

- Construire PanelForge comme atelier local de canon visuel et de recettes versionnées, réutilisables ensuite dans une Forge narrative de panels.

## Current state

- Works:
  - Image Lab : `character.change_view@0.2.0` exécute asset → ComfyUI → candidat persistant, avec provenance, contrôles, review et historique.
  - Prompt Lab : observations par image, Brief `minimax.h3.reference@0.3.0`, streaming, édition/révision, approbations et journal borné des appels LLM.
  - Fighter : `fighter.arcade_versus@0.1.0` fournit le flux Ref2VA supervisé plan de références → beat sheet → prompt H3.
  - I2V simple : `0.1.0` reste témoin et `0.2.0` est active. Le premier retour visuel est encourageant ; le prompt androïde respecte mieux durée, progression et état final.
  - Ref2V : `undressing.single_shot@0.7.1` est active. Elle conserve les prompts de `0.7.0`, mais répare par code une pose finale placée exactement à la fin demandée en ajoutant au moins 2 s de tenue, avec avertissement et sans nouvel appel LLM.
  - Le premier rendu V0.6 de 14 s est visuellement réussi et réduit le clipping. Sur le second couple d’images, le run Thinking passe de 10 à 11 s et persiste un prompt valide (`haut 4,5 s`, `jupe 4,5 s`, `pose/caméra 2 s`) ; l’Instruct était plus rapide mais rejeté pour un `<Image 1>` parasite.
  - Le cas réel V0.7 qui bloquait à `pose finale = 10 s` est couvert : en `0.7.1`, il devient un plan de 12 s et poursuit directement vers le writer.
  - Les révisions Observation/Interprétation/Brief/cookbook extraient uniquement le document attendu. Le Brief normalise ses neuf titres avec ou sans tiret, rejette les sections absentes et revient en haut après génération ; le brut reste dans les logs.
  - llama.swap garde la responsabilité GPU ; le bouton global `Libérer la VRAM` décharge ses modèles via PanelForge, sans exposer le serveur au navigateur. Le sélecteur partagé privilégie `Qwen3.6-27B-Huihui-abliterated-Q8_0`, conserve un choix manuel et se replie si le modèle manque. Les assets du Lab sont servis sans cache. Suite complète : 180 tests verts.
- Broken / missing:
  - I2V simple, Ref2V et Fighter ne sont pas encore qualifiés visuellement de bout en bout dans MiniMax H3.
  - Les tags H3 stricts ne sont pas encore compilés : Qwen abrège de façon répétée `[French]` en `FR`/`fr`.
  - Une session ne porte qu’une composition ; comparaison de versions/forks à ajouter. Le journal n’a pas encore de statut distinct « LLM terminé, document rejeté ». Aucun test navigateur automatisé.

## Decisions

- Les profils portent l’analyse/Brief LLM ; les cookbooks portent les slots, étapes et contrats vidéo. Les deux restent versionnés séparément.
- I2V réutilise l’orchestration existante mais déclare seulement `final_prompt` : aucune étape Fighter cachée.
- Ref2V réutilise le profil Observation/Brief générique et spécialise seulement son cookbook final ; aucune validation adulte n’est dupliquée dans PanelForge, ce contrôle étant assuré en amont du serveur.
- Le format strict Ref2V V0.2 est compilé par le code depuis quatre champs LLM ; les révisions repassent par le même compilateur et le Brief partagé reste inchangé.
- Ref2V V0.3+ conserve les trois étapes visibles Observation → Brief → Prompt, mais son bouton final orchestre deux appels : plan JSON validé et auto-approuvé, puis rédaction. La seconde observation est filtrée en apparence seule avant le planner ; aucune règle n’a été ajoutée au Brief partagé.
- Ref2V V0.6 versionne un retiming entièrement algorithmique : mêmes templates que V0.5, gestes simples inchangés, redistribution bornée et métadonnées d’ajustement retirées avant le writer.
- Ref2V V0.7 garde les contrôles structurels indispensables, mais rend consultatifs les labels, landmarks et durées supérieures à 15 s. Elle conserve le décalage pose → caméra au lieu de raccourcir la mise en scène.
- Ref2V V0.7.1 ne change aucun prompt : son parseur tolère une marge finale récupérable, puis le retiming ajoute la tenue manquante. Un ordre ou un chevauchement impossible reste bloquant.
- Le run V0.3 du 2026-08-09 a validé les deux appels mais révélé un rejet applicatif des champs inline et une contradiction `frontal_axis`/orbite ; correctifs portés par le compilateur et la V0.4 sans altérer la recette témoin.
- `minimax.h3.i2v.simple@0.1.0` reste immuable ; l’onglet sélectionne explicitement `0.2.0` pour les nouveaux parcours.
- La prose reste au LLM, mais les futurs tags H3 stricts seront insérés/normalisés par code depuis des champs structurés ; ne pas surcharger `0.2.0` pour ce cas.
- Chaque livrable reste générable, éditable, révisable et approuvable manuellement ; pas de chaîne d’agents autonome en V1.

## Next steps

1. Qualifier V0.7.1 sur plusieurs images et vérifier les avertissements de retiming dans MiniMax H3.
2. Concevoir V0.8 : plan chorégraphique supervisé, sous-étapes, durées proposées et contradictions éditables avant compilation.
3. Définir le contrat structuré de dialogue I2V, puis ajouter plusieurs compositions/forks par session.

## Risks / open questions

- La conformité du prompt ne garantit pas la qualité vidéo ; seuls les essais MiniMax H3 qualifient une recette.
- Une rotation à 180° depuis une unique vue frontale force H3 à inventer le dos du sujet ; ce cas bénéficiera d’une référence arrière en Ref2VA.
- L’onglet I2V réutilise pour l’instant le profil générique d’observation/Brief `minimax.h3.reference@0.3.0` ; un profil I2V dédié ne se justifiera que si les tests montrent un manque.
- Ref2V fait le même choix ; la seconde image peut influencer excessivement pose ou décor malgré le contrat textuel, ce qui doit être mesuré dans H3.
- Les marges V0.7.1 restent des heuristiques ; elles ne savent pas estimer une sous-action comme trois boutons puis un retrait complet. Une durée supérieure à 15 s reste dépendante du moteur vidéo ciblé malgré son acceptation par PanelForge.
- Le dernier Brief/plan demande une jupe inchangée tout en rendant visible un attribut anatomique qu’elle couvre ; cette contradiction sémantique et le glissement du haut classé trop simplement doivent être remontés par le futur plan supervisé.
- La variante Ref2V à une seule référence corporelle, avec vêtements initiaux décrits, est différée à une version ultérieure.
- llama.swap ne fournit pas de pourcentage fiable de chargement ; un stream interrompu ne reprend pas après redémarrage.
- Libérer la VRAM pendant un appel LLM interrompt potentiellement sa génération ; l’interface l’indique dans l’infobulle.
