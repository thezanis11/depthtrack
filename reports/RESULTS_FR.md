# Résultats mesurés — DepthTrack

Données réelles TUM RGB-D ; dégradations de profondeur, synchronisation et fréquence appliquées artificiellement.

## Méthodes sur les séquences sans dégradation

Erreurs de position avec alignement à la première pose commune, sans ajustement d'échelle. La métrique held-last pénalise les périodes sans estimation ; elle n'est pas une sortie produite par le suivi.

| Séquence | Rôle | Frame : erreur m | Keyframe : erreur m | Keyframe : couverture % | Keyframe : RPE 0,5 s m / degrés |
|---|---|---:|---:|---:|---|
| xyz | development | 0.135 | 0.108 | 100.0 | 0.020 / 1.176 |
| rpy | validation | 0.252 | 0.127 | 100.0 | 0.041 / 1.947 |
| desk | test | 0.141 | 0.144 | 100.0 | 0.033 / 2.000 |
| floor | test | 0.248 | 0.244 | 93.2 | 0.014 / 0.919 |

L'approche à images clés réduit cette erreur de position sur 3/4 séquences comparées à la référence frame. Ce comptage est descriptif : les séquences ne sont pas des domaines indépendants. La référence immobile reste publiée ; une faible erreur de position sur un mouvement surtout rotatif ne garantit pas une bonne orientation.

## Robustesse et pertes de suivi

| Séquence | Condition | Seed | Couverture % | Plus longue perte s | Erreur held-last m |
|---|---|---:|---:|---:|---:|
| xyz | skip_3 | 42 | 100.0 | 0.00 | 0.149 |
| xyz | skip_5 | 42 | 100.0 | 0.00 | 0.108 |
| xyz | depth_mask_70 | 42 | 100.0 | 0.00 | 0.095 |
| xyz | depth_lag_100ms | 42 | 99.5 | 0.10 | 0.226 |
| rpy | skip_3 | 42 | 99.1 | 0.20 | 0.080 |
| rpy | skip_5 | 42 | 53.2 | 11.44 | 0.094 |
| rpy | depth_mask_70 | 42 | 16.3 | 20.30 | 0.121 |
| rpy | depth_lag_100ms | 42 | 99.6 | 0.10 | 0.128 |
| desk | skip_3 | 42 | 100.0 | 0.00 | 0.093 |
| desk | skip_5 | 42 | 78.3 | 4.40 | 0.271 |
| desk | depth_mask_70 | 42 | 100.0 | 0.00 | 0.108 |
| desk | depth_lag_100ms | 42 | 99.5 | 0.10 | 0.227 |
| floor | skip_3 | 42 | 98.5 | 0.50 | 0.234 |
| floor | skip_5 | 42 | 79.7 | 9.13 | 0.575 |
| floor | depth_mask_70 | 42 | 79.8 | 9.21 | 0.552 |
| floor | depth_lag_100ms | 42 | 58.4 | 20.64 | 0.858 |

Les seeds 43 et 44 de profondeur masquée sont aussi présentes dans les CSV. Elles mesurent une sensibilité au masque sur le même enregistrement, pas trois validations physiques indépendantes.

## Diagnostic pendant le suivi, pertes déjà déclarées exclues

Une perte de suivi est forcément signalée par le système : l'inclure peut gonfler artificiellement le rappel. Le tableau suivant ne garde que les poses effectivement suivies et évaluables sur un horizon de 0,5 s. Un cas est marqué mauvais au-delà de 5 cm ou 5 degrés de RPE. Aucun seuil n'est ajusté à ces résultats.

| Séquence propre | Poses évaluables | Erreurs locales marquées | Précision alerte | Rappel alerte | Faux avertissements |
|---|---:|---:|---:|---:|---:|
| xyz | 764 | 0 | 0.000 | non défini | 0.010 |
| rpy | 660 | 104 | 0.594 | 0.183 | 0.023 |
| desk | 547 | 48 | 0.185 | 0.104 | 0.044 |
| floor | 987 | 0 | 0.000 | non défini | 0.017 |

Les valeurs non définies restent non définies : absence d'alerte ou absence d'erreur positive ne prouve pas une bonne détection. Les références « toujours avertir » et « jamais avertir » figurent dans `diagnostic_tracked_only.csv`. Ce score peut manquer une dérive géométriquement cohérente ; il ne démontre pas une prédiction de panne future.

## Coût et limites

Les temps de suivi excluent la lecture des images et l'extraction ORB. Les mesures d'extraction figurent dans `data_quality.json`. Les graphes et la relecture proviennent des traces exportées. Il n'y a ni fermeture de boucle, ni correction d'échelle, ni démonstration sur véhicule.

Les réglages ont été fixés sur xyz/rpy avant examen des résultats desk/floor. Les résultats de test sont ensuite interprétés publiquement ; toute évolution ultérieure devra déclarer leur exposition. Aucune précision statistique artificielle n'est calculée sur les images corrélées.
