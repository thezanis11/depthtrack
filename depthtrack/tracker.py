"""Causal RGB-D odometry. No ground-truth input, resets or scale fitting."""

from dataclasses import asdict, dataclass
import time

import cv2
import numpy as np

from .geometry import angle_degrees, estimate_pose, inverse


@dataclass(frozen=True)
class Config:
    keyframes: bool = True
    refine: bool = True
    depth_filter: bool = True
    keyframe_age: int = 10
    ratio_test: float = .75
    reprojection_px: float = 3.
    minimum_inliers: int = 12
    minimum_ratio: float = .3
    max_translation_speed: float = 3.
    max_rotation_speed: float = 360.


CASES = {
    "clean": dict(stride=1,lag=False,mask_fraction=0.),
    "skip_3": dict(stride=3,lag=False,mask_fraction=0.),
    "skip_5": dict(stride=5,lag=False,mask_fraction=0.),
    "depth_mask_70": dict(stride=1,lag=False,mask_fraction=.7),
    "depth_lag_100ms": dict(stride=1,lag=True,mask_fraction=0.),
}


def match_pose(reference, current, config, seed=42):
    valid=reference["strict"] if config.depth_filter else reference["valid"]
    ids=np.flatnonzero(valid)
    info=dict(matches=0,inliers=0,inlier_ratio=0.,grid_cells=0,reprojection_px=None,quality=0.)
    if len(ids)<8 or len(current["desc"])<2:
        return None,info
    matcher=cv2.BFMatcher(cv2.NORM_HAMMING)
    candidates=matcher.knnMatch(reference["desc"][ids],current["desc"],k=2)
    selected=[];used=set()
    good=[pair[0] for pair in candidates if len(pair)==2 and pair[0].distance<config.ratio_test*pair[1].distance]
    for match in sorted(good,key=lambda m:m.distance):
        if match.trainIdx not in used:
            selected.append(match);used.add(match.trainIdx)
    info["matches"]=len(selected)
    if len(selected)<8:
        return None,info
    points=np.array([reference["xyz"][ids[m.queryIdx]] for m in selected])
    pixels=np.array([current["uv"][m.trainIdx] for m in selected])
    estimated=estimate_pose(points,pixels,refine=config.refine,threshold=config.reprojection_px,seed=seed)
    if estimated is None:
        return None,info
    pose,inliers,errors=estimated
    cells=(pixels[inliers]/np.array([80.,80.])).astype(int)
    occupied=len(np.unique(cells,axis=0))
    ratio=len(inliers)/len(selected)
    median=float(np.median(errors[inliers]))
    quality=float(np.clip(min(len(inliers)/80.,ratio/.7,occupied/12.)*np.exp(-median/3.),0.,1.))
    info.update(inliers=len(inliers),inlier_ratio=ratio,grid_cells=occupied,reprojection_px=median,quality=quality)
    if len(inliers)<config.minimum_inliers or ratio<config.minimum_ratio:
        return None,info
    return pose,info


def run(features,config=Config(),case="clean",seed=42,stationary=False):
    cv2.setNumThreads(1)
    settings=CASES[case]
    indices=np.arange(0,len(features.times),settings["stride"])
    times=features.times[indices]
    poses=np.full((len(indices),4,4),np.nan)
    diagnostics=[]
    reference=None;reference_pose=None;reference_index=None
    previous=None;previous_pose=None;previous_index=None
    for row,index in enumerate(indices):
        started=time.perf_counter()
        current=features.frame(index,lag=settings["lag"],mask_fraction=settings["mask_fraction"],seed=seed)
        info=dict(matches=0,inliers=0,inlier_ratio=0.,grid_cells=0,reprojection_px=None,quality=0.)
        status="lost"
        if stationary:
            poses[row]=np.eye(4);status="stationary"
        elif reference is None:
            valid=current["strict"] if config.depth_filter else current["valid"]
            if np.count_nonzero(valid)>=config.minimum_inliers:
                reference=current;reference_pose=np.eye(4);reference_index=int(index)
                previous=current;previous_pose=reference_pose;previous_index=int(index)
                poses[row]=reference_pose;status="initialized"
        else:
            relative,info=match_pose(reference,current,config,seed+int(index))
            used_pose,used_index=reference_pose,reference_index
            if relative is None and config.keyframes and previous_index!=reference_index:
                relative,info=match_pose(previous,current,config,seed+int(index))
                used_pose,used_index=previous_pose,previous_index
            if relative is not None:
                candidate=used_pose@inverse(relative)
                # Gating uses the last successful output, never reference motion truth.
                delta=inverse(previous_pose)@candidate
                dt=float(times[row]-features.times[previous_index])
                velocity=np.linalg.norm(delta[:3,3])/max(dt,1e-6)
                rotation=angle_degrees(delta[:3,:3])/max(dt,1e-6)
                if velocity<=config.max_translation_speed and rotation<=config.max_rotation_speed:
                    poses[row]=candidate;status="tracked"
                    previous,previous_pose,previous_index=current,candidate,int(index)
                    if not config.keyframes or index-reference_index>=config.keyframe_age or info["inlier_ratio"]<.5 or used_index!=reference_index:
                        reference,reference_pose,reference_index=current,candidate,int(index)
                else:
                    status="motion_rejected";info["quality"]=0.
        diagnostics.append(dict(frame=int(index),timestamp=float(times[row]),status=status,
            reference_frame=reference_index,**info,tracking_ms=(time.perf_counter()-started)*1000))
    return dict(times=times,indices=indices,poses=poses,diagnostics=diagnostics,config=asdict(config),case=case,seed=seed)

