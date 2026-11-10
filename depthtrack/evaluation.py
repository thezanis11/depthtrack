"""Coverage-aware metric trajectory evaluation; never correct metric scale."""

import numpy as np

from .geometry import angle_degrees, inverse, rigid_align


def rmse(values):
    finite=np.asarray(values)[np.isfinite(values)]
    return float(np.sqrt(np.mean(finite**2))) if len(finite) else None


def evaluate(result,truth,warning_threshold=None):
    poses=result["poses"];times=result["times"]
    valid=np.isfinite(poses).all(axis=(1,2))
    gt_valid=np.isfinite(truth).all(axis=(1,2))
    both=valid & gt_valid
    absolute=np.full(len(times),np.nan);rotation_error=absolute.copy()
    relative_translation=absolute.copy();relative_rotation=absolute.copy()
    held_translation=absolute.copy();aligned=np.full_like(poses,np.nan)
    rigid_ate=None
    if np.any(both):
        anchor=int(np.flatnonzero(both)[0])
        alignment=truth[anchor]@inverse(poses[anchor])
        aligned[valid]=alignment@poses[valid]
        for i in np.flatnonzero(both):
            error=inverse(truth[i])@aligned[i]
            absolute[i]=np.linalg.norm(error[:3,3])
            rotation_error[i]=angle_degrees(error[:3,:3])
        held=aligned[anchor]
        for i in range(len(times)):
            if valid[i]:held=aligned[i]
            if gt_valid[i]:held_translation[i]=np.linalg.norm(held[:3,3]-truth[i,:3,3])
        if both.sum()>=3:
            fit=rigid_align(poses[both,:3,3],truth[both,:3,3])
            projected=(fit[:3,:3]@poses[both,:3,3].T).T+fit[:3,3]
            rigid_ate=rmse(np.linalg.norm(projected-truth[both,:3,3],axis=1))
        # Fixed 0.5s horizon with at most 40ms matching tolerance. Endpoints must be tracked.
        for i in np.flatnonzero(both):
            j=int(np.searchsorted(times,times[i]-.5))
            if j>=i or abs(times[i]-times[j]-.5)>.04 or not both[j]:continue
            expected=inverse(truth[j])@truth[i]
            predicted=inverse(poses[j])@poses[i]
            error=inverse(expected)@predicted
            relative_translation[i]=np.linalg.norm(error[:3,3])
            relative_rotation[i]=angle_degrees(error[:3,:3])
    duration=float(times[-1]-times[0]) if len(times)>1 else 0.
    weights=np.diff(times,append=times[-1])
    lost=(~valid)
    loss_events=int(np.count_nonzero(lost & ~np.r_[False,lost[:-1]]))
    longest=0.;current=0.
    for missing,dt in zip(lost,weights):
        current=current+dt if missing else 0.
        longest=max(longest,current)
    metrics=dict(frames=len(times),tracked_frames=int(valid.sum()),
        tracked_fraction=float(valid.mean()),tracked_time_fraction=float(weights[valid].sum()/duration) if duration else 0.,
        ground_truth_fraction=float(gt_valid.mean()),evaluated_frames=int(both.sum()),
        initial_alignment_ate_rmse_m=rmse(absolute),rigid_alignment_ate_rmse_m=rigid_ate,
        held_last_ate_rmse_m=rmse(held_translation),orientation_rmse_deg=rmse(rotation_error),
        rpe_05s_translation_rmse_m=rmse(relative_translation),rpe_05s_rotation_rmse_deg=rmse(relative_rotation),
        rpe_pairs=int(np.isfinite(relative_translation).sum()),loss_events=loss_events,longest_loss_s=float(longest),
        tracking_median_ms=float(np.median([r["tracking_ms"] for r in result["diagnostics"]])),
        tracking_p95_ms=float(np.quantile([r["tracking_ms"] for r in result["diagnostics"]],.95)))
    quality=np.array([row["quality"] for row in result["diagnostics"]])
    labels=(relative_translation>.05)|(relative_rotation>5.)|lost
    diagnostic_valid=np.isfinite(relative_translation)|lost
    if warning_threshold is not None:
        warning=(quality<=warning_threshold)|lost
        metrics.update(diagnostic_metrics(labels[diagnostic_valid],warning[diagnostic_valid]))
        metrics["diagnostic_always_warn_precision"]=float(labels[diagnostic_valid].mean()) if diagnostic_valid.any() else None
        metrics["diagnostic_never_warn_recall"]=0. if labels[diagnostic_valid].any() else None
    return metrics,dict(aligned=aligned,absolute_error=absolute,relative_translation=relative_translation,
                        relative_rotation=relative_rotation,diagnostic_valid=diagnostic_valid,bad=labels,quality=quality)


def diagnostic_metrics(labels,warnings):
    tp=int(np.sum(labels&warnings));fp=int(np.sum(~labels&warnings))
    fn=int(np.sum(labels&~warnings));tn=int(np.sum(~labels&~warnings))
    return dict(diagnostic_tp=tp,diagnostic_fp=fp,diagnostic_fn=fn,diagnostic_tn=tn,
        diagnostic_precision=tp/(tp+fp) if tp+fp else None,
        diagnostic_recall=tp/(tp+fn) if tp+fn else None,
        diagnostic_false_warning_rate=fp/(fp+tn) if fp+tn else None)
