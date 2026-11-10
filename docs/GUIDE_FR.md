# Comprendre DepthTrack

## Le problème

Une caméra se déplace. À chaque instant, nous avons une image et une profondeur pour ses pixels. Nous voulons reconstruire son mouvement, puis mesurer quand cette reconstruction dérive ou devient indisponible.

La caméra TUM est portée à la main : les données sont réelles, mais ce n'est pas une démonstration sur un robot autonome. Le projet porte sur une brique de localisation.

## Parcours d'apprentissage

1. Lire les résultats, regarder les trajectoires, puis identifier un cas où la méthode simple gagne.
2. Comprendre la profondeur : une valeur PNG de 5000 correspond à un mètre. Expliquer pourquoi on ne multiplie pas encore par la correction Kinect.
3. Dessiner trois repères : caméra de référence, caméra courante, monde. Expliquer pourquoi la transformation PnP doit être inversée avant de composer la trajectoire.
4. Suivre un point : pixel de référence, profondeur, point 3D, correspondance dans l'image courante, projection prédite et résidu.
5. Expliquer RANSAC : chercher une pose soutenue par suffisamment de correspondances malgré les erreurs d'appariement. Expliquer ce que le raffinement optimise ensuite.
6. Comparer erreur et couverture. Une trajectoire très courte peut avoir une faible erreur et être inutilisable.
7. Lire les faux avertissements et les erreurs non signalées. Le score géométrique n'est pas une probabilité de sécurité.

## Choix importants

**RGB-D plutôt que monoculaire :** la profondeur fournit une échelle métrique. Ajuster l'échelle à la vérité terrain masquerait certaines erreurs ; le protocole l'interdit.

**ORB et PnP plutôt qu'un réseau neuronal :** un ordinateur sans GPU suffit et chaque étape possède une interprétation géométrique. Le défi est dans la synchronisation, les repères, les correspondances et l'évaluation.

**Images clés :** une référence conservée peut réduire l'accumulation des erreurs, mais devient plus difficile à apparier lorsque le point de vue change. Le résultat doit déterminer si ce compromis est utile.

**Absence de pose en cas d'échec :** le programme ne prétend pas avoir retrouvé une position. Le calcul held-last est une convention d'évaluation séparée pour empêcher la disparition des mauvaises périodes du score.

**Réglages sur rpy :** les séquences desk/floor servent à examiner le transfert des choix. Plusieurs milliers d'images du même bureau ne sont pas plusieurs milliers d'expériences indépendantes.

## Questions d'entretien

- Pourquoi une faible erreur de reprojection peut-elle accompagner une mauvaise trajectoire ? Mauvaises correspondances cohérentes, faible contrainte géométrique, défaut de profondeur/calibration ou accumulation d'erreurs.
- Pourquoi la matrice PnP ne se compose-t-elle pas directement ? Elle transforme la scène de la caméra de référence vers la caméra courante ; la trajectoire représente l'inverse, caméra vers monde.
- Quelle différence entre ATE et RPE ? L'ATE mesure la trajectoire globale dans un repère aligné ; la RPE compare un déplacement sur un horizon donné.
- Que mesure 100 % de couverture ? La disponibilité d'une sortie, pas sa justesse. La référence immobile a aussi 100 % de couverture.
- Peut-on parler de temps réel ? Seulement après avoir additionné acquisition/lecture, extraction, estimation et sortie sur une plateforme définie. Les temps du rapport distinguent extraction et suivi.
- Est-ce du SLAM ? Non : pas de carte globale optimisée, de fermeture de boucle ni de reconnaissance de lieu.
- Le diagnostic prédit-il une panne future ? Non. Cette version mesure un avertissement contemporain, comparé à l'erreur locale et aux pertes observées.

## Améliorations personnelles à réaliser

1. Modifier un seuil sur une nouvelle séquence de validation et garder une autre séquence intacte pour le test. Ne pas rebaptiser un test déjà observé « aveugle ».
2. Étudier une calibration alternative en appliquant la géométrie couleur/profondeur correctement, puis comparer sans ajustement d'échelle.
3. Ajouter une petite optimisation locale multi-images avec un budget CPU mesuré.
4. Ajouter un second domaine de scène et expliquer ce qu'il change. Éviter de multiplier les datasets sans question précise.
5. Construire une alerte anticipée avec horizon futur fixé, séparation temporelle et mesure de délai — uniquement après avoir distingué cette tâche du diagnostic actuel.

## Formulation CV proposée

« Projet personnel de localisation visuelle RGB-D sur données réelles TUM : estimation de pose par ORB/PnP-RANSAC, comparaison d'images clés et d'ablations, évaluation conjointe de la dérive et des pertes de suivi, avec perturbations contrôlées et protocole reproductible sur CPU. »

Le développement initial a été réalisé avec assistance IA. Adapter les verbes aux parties que vous avez comprises et personnellement reprises ; ne pas revendiquer une expérience sur véhicule, un système embarqué déployé ou une performance non mesurée.
