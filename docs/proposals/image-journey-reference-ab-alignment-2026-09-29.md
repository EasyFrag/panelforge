# Parcours autonome — alignement sur la fidélité et comparaison des références

## Décision utilisateur

L’utilisateur soupçonne un rôle majeur de la réduction à 1 MP et demande comment vérifier cette hypothèse, ainsi qu’une explication du prétraitement et de l’usage de l’original en référence supplémentaire.

Il **rejette la proposition d’un contrôle qualité suspendant le parcours** : l’objectif est de produire des résultats propres par conception. Cette décision remplace la proposition de garde-fou qualité des audits précédents. Conserver les deux rôles, l’UX épurée et la relecture des états pour piloter les travaux ; ne pas ajouter implicitement un critique, un seuil de qualité ou un rejeu. Les suspensions techniques existantes restent hors de cette discussion.

Alignement et documentation uniquement : aucun réglage applicatif changé, aucun test, appel LLM, rendu ni redémarrage exécuté.

## 1. Prétraitement

Le workflow enregistré impose `ImageScaleToTotalPixels`, cible 1 MP et interpolation `nearest-exact` avant l’entrée MiniMax. Le mode `ref_image_size=max` qui suit ne peut pas restituer une information déjà retirée. L’image de départ mesure 1120 × 1984 (2,22 MP) ; les résultats mesurent 2016 × 3584 (7,23 MP). La réduction est donc réappliquée à chaque nouvelle source, sans diminuer les dimensions finales.

Deux variables sont à distinguer : le nombre de pixels de référence et la méthode de redimensionnement. Leurs effets ne sont pas encore isolés. Le nombre de pixels n’est pas une mesure directe de la qualité et relever la limite ne garantit pas la disparition de toute dérive du moteur.

## Comparaison proposée, non exécutée

1. Extraire/inspecter l’image exacte après le prétraitement, en regard de la source, à échelle commune. Cela montre ce que la préparation fait perdre, sans prouver à elle seule la cause du rendu final.
2. Rejouer la première transformation depuis l’original propre dans un essai isolé. A : référence 1 MP, nearest-exact. B : référence 2 MP, nearest-exact. Le départ contient 2,22 MP ; cette comparaison apporte de vrais pixels de source sans prétendre créer de détails par suréchantillonnage.
3. Garder identiques le fichier source, le prompt sauvegardé, la seed, les modèles, le sampler, les 18 steps, la sortie 2016 × 3584 et l’absence de finition couleur. Ne pas redemander le prompt au LLM et ne pas ajouter de seconde référence dans cette comparaison. Vérifier les dimensions réellement reçues par le conditionnement MiniMax, pour exclure une autre réduction interne annulant la différence A/B. La version déployée du nœud distant n’a pas été vérifiée dans cet alignement.
4. Comparer les mêmes régions non visées : fines fissures d’écorce, mousse, feuilles et dégradés. Chercher la fidélité au départ, pas simplement une impression de netteté. Vérifier aussi que la porte reste correctement ajoutée. Enregistrer durée et mémoire si disponible, afin d’évaluer le coût du gain.
5. Une seule paire est un premier signal. Répéter sur deux ou trois seeds appariées si nécessaire, puis comparer deux courtes chaînes de trois ou quatre éditions depuis le même départ, avec les mêmes prompts et les mêmes seeds étape par étape. Chaque branche réutilise ses propres résultats : seule la politique de résolution diffère. Ce dernier essai mesure l’accumulation, qui est le problème utilisateur.
6. Si les branches à référence plus détaillée restent nettement plus fidèles sur plusieurs éditions et seeds, cela étaye un rôle majeur du plafond. Si le gain reste faible, la réduction n’explique pas à elle seule le défaut. Tester ensuite l’interpolation à résolution constante, puis seulement les autres mécanismes. Aucun réglage du workflow partagé ne sera modifié implicitement pour un essai.

## 2. Original comme référence permanente

Proposition distincte et secondaire : transmettre deux images au moteur avec des rôles explicites. L’état courant décrit les objets et travaux à conserver ; l’original indique l’aspect initial des zones restées stables, leur matière, lumière et palette.

Exemple : au moment d’ajouter le panneau solaire, l’état courant contient déjà porte et deck ; l’original conserve l’écorce de départ. Il ne s’agit ni d’un mélange de pixels ni d’un verrouillage technique de style. Les deux références conditionnent le moteur, qui peut mal interpréter leur rôle et faire régresser les travaux. Une région réellement transformée ne doit pas retrouver son ancienne matière.

Le code de compilation prend déjà en charge plusieurs références, mais clone actuellement le même prétraitement à 1 MP pour chacune (`infrastructure/presets/minimax_edit.py:60-64`). Ajouter l’original sans traiter ce point ne contournerait donc pas le plafond. Cette piste doit être comparée séparément, après la résolution, afin d’attribuer les gains au bon changement.

## Suite

Priorité proposée : isoler l’effet du plafond 1 MP, puis choisir la préparation qui améliore effectivement la fidélité au coût acceptable. La référence originale supplémentaire reste une piste à qualifier si nécessaire. Aucune qualification par rendu n’est autorisée ou lancée dans cette demande d’explication.
