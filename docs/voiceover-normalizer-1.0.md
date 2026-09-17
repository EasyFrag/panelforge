# Voix off — normalisation locale 1.0

Les préparations **Mise en scène / Classique 1.0** de H3 Base et REF2V partagent
désormais un post-compilateur vocal local. Fabrication Histoires utilise la même
recette REF2V et bénéficie donc du même traitement.

Le post-compilateur intervient après la réponse du Rédacteur et avant la
validation finale. Il ne change ni le Plan, ni le schéma Writer, ni les prompts
système/utilisateur, et n’ajoute aucun appel LLM. Une demande sans voix off
explicite produit exactement le même prompt qu’avant.

Pour agir, il exige simultanément :

1. une réplique exacte et citée dans la source, explicitement marquée `VOIX OFF`,
   `NARRATION`, `PENSÉE` ou `VOIX INTÉRIEURE` ;
2. la même réplique dans une balise H3 `<d>[Language] …</d>` ;
3. une formulation Writer reconnue sans ambiguïté, par exemple
   `off-screen voice narrates`, `inner voice-over reads` ou
   `voice is heard in voice-over`.

Dans ce seul cas, l’enveloppe devient la formulation H3
`(Sx) says in an off-screen voiceover:` et une consigne immédiate maintient les
lèvres de tous les personnages visibles fermées et immobiles. Cette formulation
couvre aussi bien une pensée du personnage qu’un narrateur réellement invisible,
sans devoir deviner lequel est à l’image. Les identifiants vocaux sont stables
par locuteur dans la source et les références `<Picture N>` déjà présentes sont
conservées.

Une indication `HORS CHAMP`, `O.S.` ou `DERRIÈRE LA PORTE` reste un dialogue
diégétique hors cadre : elle n’est pas convertie en narration. Si la source est
claire mais que la prose Writer ne correspond à aucune forme sûre, le prompt
reste intact, n’est pas rejeté, et un avertissement est enregistré dans
`vocal_normalization.warnings` du contexte compilé. Ce choix privilégie la
qualité générale et la rétrocompatibilité aux réécritures spéculatives.
