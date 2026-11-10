# Présentation en cinq minutes

Ouvrir `reports/index.html` après téléchargement du dépôt. Le rapport est autonome : la relecture des trajectoires ne nécessite ni serveur ni téléchargement des images originales.

| Temps | Action | Explication |
|---|---|---|
| 0:00–0:45 | Présenter une trajectoire propre et sa référence | Images couleur + profondeur, estimation géométrique sur CPU |
| 0:45–1:45 | Comparer frame et keyframe sur la même séquence | Montrer l'erreur et la couverture, y compris si la méthode simple gagne |
| 1:45–2:45 | Choisir skip_5 ou depth_lag_100ms | Distinguer les acquisitions réelles des dégradations artificielles |
| 2:45–3:30 | Déplacer le curseur sur une perte ou une erreur | Expliquer la couleur d'avertissement et ses limites |
| 3:30–4:15 | Montrer les ablations | Mesurer ce qu'apportent raffinement et filtre de profondeur |
| 4:15–5:00 | Présenter le protocole et une limite | Validation séparée, aucune correction d'échelle, aucune preuve de sécurité robotique |

Lire `RESULTS_FR.md` avant l'entretien pour choisir un échec réel du rapport. Une démonstration intéressante explique un compromis, pas seulement une trajectoire agréable à regarder.
