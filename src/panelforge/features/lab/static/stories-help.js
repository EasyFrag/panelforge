(() => {
  "use strict";
  const root = document.getElementById("stories-workspace");
  if (!root) return;
  const help = {
    "workflow-mode": ["Automatique ou manuel guidé", "Les mêmes contrôles s’appliquent dans les deux modes. Automatique avance jusqu’au scénario prêt ; Manuel guidé te laisse valider la direction puis les séquences.", "Exemple : laisse le moteur inventer une première version ; reprends la main pour changer la fin. Les vidéos ne démarrent pas avec ce choix."],
    "active-mode": ["Qui décide de continuer ?", "Manuel guidé marque les pauses d’auteur. Automatique enchaîne les étapes recevables et s’arrête si une difficulté persiste.", "Choisis le mode puis clique sur Continuer. Reprendre la main laisse terminer l’appel actif ; ton brouillon de retour reste conservé."],
    universe: ["Univers des personnages", "L’apparence des personnages est indépendante du genre de l’histoire. Une indication ici prévaut sur l’univers par défaut de la famille en histoire suivie.", "Exemples : gouttes d’eau pour un mélodrame visuel ; fruits ou humains pour une dispute au restaurant. Vide : le moteur choisit dans le cadre de la famille."],
    "long-delivery": ["Une vidéo ou une série", "Une vidéo continue peut être écrite en plusieurs séquences sans résumés ni fins artificielles entre elles. Une série contient des épisodes publiables séparément.", "Exemples : la dispute de l’addition est une vidéo ; une aventure publiée en trois rendez-vous forme une série. Le montage final des séquences reste une étape de production."],
    "target-seconds": ["Durée souhaitée", "Cette durée concerne toute l’histoire créée. Elle propose un découpage et un plafond de clips ; le budget réel arrondi est affiché sous les réglages.", "Exemples : 80 secondes pour une joute verbale ; 120 secondes pour tester l’ouverture des compteurs. La référence complète des compteurs dure environ 6 min 30."],
    "long-profile": ["Ce qui fait avancer l’histoire", "Automatique choisit une mécanique adaptée à ton idée. Les profils orientent les causes et les conséquences ; ils n’imposent pas une suite de scènes identiques.", "Quotidien : négociations et refus autour d’une addition. Mélodrame : trahison des gouttes. Transformation : pouvoir acquis. Suspense : indice compris plus tard. Fantastique : temps de vie échangeable."],
    "long-narration": ["Comment le public comprend", "Visuelle : gestes, objets, regards. Dialogues : paroles qui cherchent à obtenir ou empêcher quelque chose. Audio : informations nécessaires compréhensibles à l’écoute.", "Exemples : les gouttes se comprennent surtout à l’image ; l’addition avance par les répliques. Visuelle autorise quelques paroles ; seule une famille muette les interdit. Automatique suit ton idée."],
    "long-ending": ["La dernière conséquence", "Résolution ferme le problème. Ouverte permet une suite. Retournement inverse le rapport de force ou la compréhension. Victoire avec coût associe réussite et perte.", "Exemples : le mauvais payeur se retrouve à demander de l’aide = retournement ; un héros acquiert un pouvoir et part en quête = ouverte. Automatique choisit une fin préparée par le récit."],
    recipe: ["Famille éditoriale", "La famille fournit des conventions de personnages et de ton. En histoire suivie, l’univers explicite et le profil narratif affinent cette base.", "Exemples : Mélodrame fruits sert aussi à la joute verbale avec des fruits ; Chats de couple impose une comédie féline sans paroles. Les familles adultes ont leurs contraintes propres."],
    "creation-mode": ["Inventer ou adapter", "Inventer part d’une phrase, voire d’aucune idée. Développer un récit fourni préserve ses moments importants. Les entrées Script fidèle et Continuer concernent le parcours historique court.", "Exemples : « Une addition qui dégénère » pour inventer ; un résumé avec une fin précise pour adapter. Un simple « compose » appartient au premier choix."],
    "dialogue-language": ["Langue parlée", "Détermine la langue des nouvelles répliques. Les descriptions restent en français. Un script fidèle conserve les paroles déjà fournies.", "Exemples : français pour la dispute ; anglais pour une autre version des gouttes. La langue n’améliore pas à elle seule la progression narrative."],
    "dialogue-register": ["Vocabulaire des personnages", "0 conserve le comportement du modèle. 1 demande un oral direct. 2 autorise un ton cru. 3 accentue l’argot lorsque le personnage s’y prête.", "Exemples : 1 pour une serveuse ferme et naturelle ; 2 pour une dispute familière. Ce réglage ne remplace ni le conflit ni la qualité de la chute."],
    "long-units": ["Parties d’une seule histoire", "Pour une vidéo, les séquences sont des parties internes. Pour une série, ce nombre désigne ses épisodes. Il ne s’agit jamais du nombre de propositions.", "Exemples : une séquence pour l’addition en un lieu ; plusieurs séquences pour une fuite qui change de lieu et d’objectif. Changer ce nombre modifie le budget total affiché."],
    "scene-count": ["Clips par séquence", "En histoire suivie, c’est un plafond par séquence ou épisode. Le rédacteur peut utiliser moins de clips. En scénario court, le nombre est exact.", "Exemples : 1 séquence × 8 clips × 10 secondes = 80 secondes maximum ; 2 × 6 × 10 = 120 secondes. Ce nombre ne doit pas provoquer du remplissage."],
    duration: ["Secondes par clip", "C’est le temps disponible pour les actions, paroles et réactions de chaque clip. Ce n’est pas la durée totale de l’histoire.", "Exemples : une courte réaction peut tenir en 5 secondes ; une négociation avec plusieurs répliques demande plus de temps. La fabrication reprend cette durée."],
    "architect-model": ["Modèle de conception", "Construit l’histoire, examine les incohérences et vérifie les raccords. Le rédacteur peut utiliser le même modèle ou un autre.", "Pour comparer deux parcours, garde les mêmes modèles. Local indique où le modèle tourne, pas un niveau de créativité."],
    "writer-model": ["Modèle de rédaction", "Transforme la progression en scènes jouables et applique tes retours ciblés.", "Exemple : l’architecte prévoit un refus de paiement ; le rédacteur écrit les réactions et les paroles. Tu peux garder ton couple de modèles habituel."],
    title: ["Nom du projet", "Un repère pour retrouver ton histoire. Le titre sera mis à jour à partir de la proposition.", "Mets l’intention narrative dans Ton idée, pas seulement dans ce nom."],
    brief: ["Une intention minimale", "Une phrase peut suffire : le moteur doit inventer la progression. Tu peux aussi imposer ce qui compte pour toi.", "Exemples : « Une trahison amoureuse entre des gouttes d’eau » ; « Un premier rendez-vous dérape à l’arrivée de l’addition ». Si tu demandes une question finale au public, elle sera intégrée au récit."],
    "format-long": ["Histoire suivie", "Ajoute une architecture, une mémoire des événements et des contrôles. Ce parcours fonctionne aussi pour une vidéo d’une minute.", "Exemples : une dispute avec une progression précise ; une aventure sur plusieurs épisodes. Le scénario court garde son parcours direct historique."],
    "format-short": ["Scénario court", "Un scénario complet écrit dans un nombre exact de micro-scènes, avec le parcours historique.", "Choisis Histoire suivie pour les nouveaux modes automatique et manuel guidé, même pour une vidéo courte."],
  };
  for (const [id, [title, effect, examples]] of Object.entries(help)) {
    const field = document.getElementById(`story-${id}`), label = field?.closest("label") || root.querySelector(`label[for="story-${id}"]`);
    if (!label) continue;
    const button = document.createElement("button"); button.type = "button"; button.className = "story-info";
    button.textContent = "ⓘ"; button.setAttribute("aria-label", `Informations : ${title}`); button.setAttribute("aria-haspopup", "dialog");
    button.addEventListener("click", event => {
      event.preventDefault(); event.stopPropagation();
      document.getElementById("story-help-title").textContent = title;
      const content = document.getElementById("story-help-content");
      content.replaceChildren(...[effect, examples].map(text => { const p = document.createElement("p"); p.textContent = text; return p; }));
      document.getElementById("story-help").showModal();
    });
    label.classList.add("story-has-info"); label.append(button);
  }
})();
