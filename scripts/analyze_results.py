"""Separate reliability during tracking from the tautological detection of loss."""

import csv
import gzip
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from depthtrack.experiments import write_rows


def fmt(value,digits=3):
    return "non défini" if value is None else f"{value:.{digits}f}"


def analyze(out="reports"):
    out=Path(out)
    rows=json.loads((out/"metrics.json").read_text())
    diagnostics=[]
    for row in rows:
        with gzip.open(out/row["trace"],"rt",encoding="utf-8",newline="") as stream:
            samples=list(csv.DictReader(stream))
        usable=[r for r in samples if r["rpe_05s_m"] and r["status"] in ("tracked","stationary")]
        labels=[float(r["rpe_05s_m"])>.05 or float(r["rpe_05s_deg"])>5. for r in usable]
        warning=[r["warning"]=="True" for r in usable]
        tp=sum(y and w for y,w in zip(labels,warning));fp=sum(not y and w for y,w in zip(labels,warning))
        fn=sum(y and not w for y,w in zip(labels,warning));tn=sum(not y and not w for y,w in zip(labels,warning))
        diagnostics.append({key:row[key] for key in ("sequence","method","case","seed")} |
            dict(eligible_tracked_frames=len(usable),bad_tracked_frames=sum(labels),tp=tp,fp=fp,fn=fn,tn=tn,
                 precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None,
                 false_warning_rate=fp/(fp+tn) if fp+tn else None,
                 always_warn_precision=sum(labels)/len(labels) if labels else None,
                 never_warn_recall=0. if sum(labels) else None))
    write_rows(out/"diagnostic_tracked_only.csv",diagnostics)
    sequences=list(dict.fromkeys(r["sequence"] for r in rows))
    lines=["# Résultats mesurés — DepthTrack","",
        "Données réelles TUM RGB-D ; dégradations de profondeur, synchronisation et fréquence appliquées artificiellement.","",
        "## Méthodes sur les séquences sans dégradation","",
        "Erreurs de position avec alignement à la première pose commune, sans ajustement d'échelle. "
        "La métrique held-last pénalise les périodes sans estimation ; elle n'est pas une sortie produite par le suivi.","",
        "| Séquence | Rôle | Frame : erreur m | Keyframe : erreur m | Keyframe : couverture % | Keyframe : RPE 0,5 s m / degrés |",
        "|---|---|---:|---:|---:|---|"]
    wins=0
    for sequence in sequences:
        frame=next(r for r in rows if r["sequence"]==sequence and r["method"]=="frame" and r["case"]=="clean")
        key=next(r for r in rows if r["sequence"]==sequence and r["method"]=="keyframe" and r["case"]=="clean")
        wins+=key["held_last_ate_rmse_m"]<frame["held_last_ate_rmse_m"]
        lines.append(f"| {sequence} | {key['split']} | {fmt(frame['held_last_ate_rmse_m'])} | {fmt(key['held_last_ate_rmse_m'])} | "
            f"{100*key['tracked_fraction']:.1f} | {fmt(key['rpe_05s_translation_rmse_m'])} / {fmt(key['rpe_05s_rotation_rmse_deg'])} |")
    lines += ["",f"L'approche à images clés réduit cette erreur de position sur {wins}/{len(sequences)} séquences comparées à la référence frame. "
        "Ce comptage est descriptif : les séquences ne sont pas des domaines indépendants. "
        "La référence immobile reste publiée ; une faible erreur de position sur un mouvement surtout rotatif ne garantit pas une bonne orientation.","",
        "## Robustesse et pertes de suivi","","| Séquence | Condition | Seed | Couverture % | Plus longue perte s | Erreur held-last m |",
        "|---|---|---:|---:|---:|---:|"]
    for row in rows:
        if row["method"]=="keyframe" and row["case"]!="clean" and row["seed"]==42:
            lines.append(f"| {row['sequence']} | {row['case']} | 42 | {100*row['tracked_fraction']:.1f} | "
                         f"{row['longest_loss_s']:.2f} | {fmt(row['held_last_ate_rmse_m'])} |")
    lines += ["","Les seeds 43 et 44 de profondeur masquée sont aussi présentes dans les CSV. "
        "Elles mesurent une sensibilité au masque sur le même enregistrement, pas trois validations physiques indépendantes.","",
        "## Diagnostic pendant le suivi, pertes déjà déclarées exclues","",
        "Une perte de suivi est forcément signalée par le système : l'inclure peut gonfler artificiellement le rappel. "
        "Le tableau suivant ne garde que les poses effectivement suivies et évaluables sur un horizon de 0,5 s. "
        "Un cas est marqué mauvais au-delà de 5 cm ou 5 degrés de RPE. Aucun seuil n'est ajusté à ces résultats.","",
        "| Séquence propre | Poses évaluables | Erreurs locales marquées | Précision alerte | Rappel alerte | Faux avertissements |",
        "|---|---:|---:|---:|---:|---:|"]
    for row in diagnostics:
        if row["method"]=="keyframe" and row["case"]=="clean":
            lines.append(f"| {row['sequence']} | {row['eligible_tracked_frames']} | {row['bad_tracked_frames']} | "
                         f"{fmt(row['precision'])} | {fmt(row['recall'])} | {fmt(row['false_warning_rate'])} |")
    lines += ["","Les valeurs non définies restent non définies : absence d'alerte ou absence d'erreur positive ne prouve pas une bonne détection. "
        "Les références « toujours avertir » et « jamais avertir » figurent dans `diagnostic_tracked_only.csv`. "
        "Ce score peut manquer une dérive géométriquement cohérente ; il ne démontre pas une prédiction de panne future.","",
        "## Coût et limites","",
        "Les temps de suivi excluent la lecture des images et l'extraction ORB. Les mesures d'extraction figurent dans `data_quality.json`. "
        "Les graphes et la relecture proviennent des traces exportées. Il n'y a ni fermeture de boucle, ni correction d'échelle, ni démonstration sur véhicule.","",
        "Les réglages ont été fixés sur xyz/rpy avant examen des résultats desk/floor. Les résultats de test sont ensuite interprétés publiquement ; "
        "toute évolution ultérieure devra déclarer leur exposition. Aucune précision statistique artificielle n'est calculée sur les images corrélées.",""]
    (out/"RESULTS_FR.md").write_text("\n".join(lines),encoding="utf-8",newline="\n")
    print(f"Analyzed {len(rows)} trials; tracked-only diagnostics exported")


if __name__=="__main__":analyze(sys.argv[1] if len(sys.argv)>1 else "reports")
