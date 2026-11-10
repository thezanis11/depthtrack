"""Validation-only parameter selection, then a frozen reproducible campaign."""

from dataclasses import asdict,replace
from datetime import datetime,timezone
import csv
import gzip
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import platform
import time

import numpy as np

from .dataset import SEQUENCES,SPLITS,file_hash,ground_truth,load_sequence
from .evaluation import evaluate
from .features import Features,extract
from .tracker import CASES,Config,run

ROOT=Path(__file__).resolve().parent.parent
CORE=("dataset.py","features.py","geometry.py","tracker.py","evaluation.py")


def save_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")


def core_hashes():
    return {name:file_hash(ROOT/"depthtrack"/name) for name in CORE}


def config_for(method,base):
    if method=="frame":return replace(base,keyframes=False)
    if method=="no_refine":return replace(base,refine=False)
    if method=="no_depth_filter":return replace(base,depth_filter=False)
    return base


def calibration(data="data/raw",cache="data/features",out="reports/calibration.json"):
    start=time.perf_counter()
    # Only these sequences may be opened by calibration.
    development=Features(extract(data,"xyz",cache))
    result=run(development,Config(keyframes=False))
    dev_truth=ground_truth(load_sequence(data,"xyz")[0],result["times"])
    dev_metrics,_=evaluate(result,dev_truth)
    features=Features(extract(data,"rpy",cache))
    truth=ground_truth(load_sequence(data,"rpy")[0],features.times)
    candidates=[];trials=[]
    for age in (5,10,20):
        config=Config(keyframe_age=age)
        result=run(features,config)
        metrics,_=evaluate(result,truth)
        # Equal fixed units/weights for all candidates, no test data involved.
        score=(metrics["held_last_ate_rmse_m"] if metrics["held_last_ate_rmse_m"] is not None else 1e6)
        score+=.01*(metrics["orientation_rmse_deg"] if metrics["orientation_rmse_deg"] is not None else 1e6)
        score+=1.-metrics["tracked_fraction"]
        candidates.append(dict(config=asdict(config),validation_score=score,metrics=metrics))
        trials.append(result)
        print(f"validation age={age}: score={score:.5f}, coverage={metrics['tracked_fraction']:.3f}",flush=True)
    chosen=min(range(len(candidates)),key=lambda i:candidates[i]["validation_score"])
    quality=[r["quality"] for r in trials[chosen]["diagnostics"] if r["status"]=="tracked"]
    if not quality:raise RuntimeError("No successful validation tracking; stop before test")
    threshold=float(np.quantile(quality,.05))
    record=dict(protocol="depthtrack-v1",created_utc=datetime.now(timezone.utc).isoformat(),
        splits=SPLITS,core_sha256=core_hashes(),selected_config=candidates[chosen]["config"],
        warning_threshold=threshold,threshold_rule="5th percentile of successful clean rpy quality; no test labels",
        candidate_objective="held-last initial-aligned ATE[m] + 0.01*orientation RMSE[deg] + missing-frame fraction",
        candidates=candidates,development_baseline=dev_metrics,
        elapsed_seconds=time.perf_counter()-start,
        scope="Exploratory development; desk/floor not opened by calibration")
    save_json(out,record)
    return record


def write_rows(path,rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,lineterminator="\n")
        writer.writeheader();writer.writerows(rows)


def execute(features,sequence,method,case,seed,base,truth_root,threshold,out,cache):
    config=config_for(method,base)
    parameters=dict(sequence=sequence,method=method,case=case,seed=seed,config=asdict(config),
                    core=core_hashes(),feature_hash=json.loads((Path(cache)/f"{sequence}.json").read_text())["cache_sha256"])
    key=hashlib.sha256(json.dumps(parameters,sort_keys=True).encode()).hexdigest()[:20]
    folder=ROOT/"data"/"runs";folder.mkdir(parents=True,exist_ok=True)
    npz_path=folder/f"{key}.npz";meta_path=folder/f"{key}.json"
    cached=False
    if npz_path.exists() and meta_path.exists():
        saved=json.loads(meta_path.read_text())
        if saved["parameters"]==parameters and saved["sha256"]==file_hash(npz_path):
            with np.load(npz_path,allow_pickle=False) as source:
                result={k:source[k] for k in ("times","indices","poses")}
            result.update(diagnostics=saved["diagnostics"],case=case,seed=seed,config=asdict(config));cached=True
    if not cached:
        result=run(features,config,case,seed,stationary=method=="stationary")
        np.savez_compressed(npz_path,**{k:result[k] for k in ("times","indices","poses")})
        save_json(meta_path,dict(parameters=parameters,sha256=file_hash(npz_path),diagnostics=result["diagnostics"]))
    truth=ground_truth(truth_root,result["times"])
    metrics,details=evaluate(result,truth,threshold)
    name=f"{sequence}__{method}__{case}__{seed}"
    public_rows=[]
    for i,diag in enumerate(result["diagnostics"]):
        pose=details["aligned"][i]
        public_rows.append(dict(**diag,elapsed_s=float(result["times"][i]-result["times"][0]),
            x=float(pose[0,3]) if np.isfinite(pose[0,3]) else None,
            y=float(pose[1,3]) if np.isfinite(pose[1,3]) else None,
            z=float(pose[2,3]) if np.isfinite(pose[2,3]) else None,
            gt_x=float(truth[i,0,3]) if np.isfinite(truth[i,0,3]) else None,
            gt_y=float(truth[i,1,3]) if np.isfinite(truth[i,1,3]) else None,
            gt_z=float(truth[i,2,3]) if np.isfinite(truth[i,2,3]) else None,
            error_m=float(details["absolute_error"][i]) if np.isfinite(details["absolute_error"][i]) else None,
            rpe_05s_m=float(details["relative_translation"][i]) if np.isfinite(details["relative_translation"][i]) else None,
            rpe_05s_deg=float(details["relative_rotation"][i]) if np.isfinite(details["relative_rotation"][i]) else None,
            warning=diag["status"] not in ("tracked","initialized","stationary") or diag["quality"]<=threshold))
    trace=Path(out)/"traces"/f"{name}.csv.gz";trace.parent.mkdir(parents=True,exist_ok=True)
    buffer=io.StringIO(newline="");writer=csv.DictWriter(buffer,fieldnames=list(public_rows[0]),lineterminator="\n")
    writer.writeheader();writer.writerows(public_rows)
    trace.write_bytes(gzip.compress(buffer.getvalue().encode(),mtime=0))
    record=dict(sequence=sequence,split=SPLITS[sequence],method=method,case=case,seed=seed,**metrics,
                cached=cached,trace=f"traces/{name}.csv.gz",trace_sha256=file_hash(trace))
    replay=dict(name=name,sequence=sequence,method=method,case=case,seed=seed,
        samples=[[round(r["elapsed_s"],3),*[round(r[k],5) if r[k] is not None else None for k in
                  ("x","y","z","gt_x","gt_y","gt_z","quality","error_m")],r["status"],r["warning"]] for r in public_rows])
    return record,replay


def benchmark(data="data/raw",cache="data/features",out="reports",sequences=SEQUENCES,smoke=False):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    calibration_path=ROOT/"reports"/"calibration.json"
    selected=json.loads(calibration_path.read_text())
    if selected["core_sha256"]!=core_hashes():
        raise ValueError("Core changed since calibration: explicitly recalibrate and document test exposure")
    base=Config(**selected["selected_config"]);threshold=selected["warning_threshold"]
    rows=[];replays=[];start=time.perf_counter();quality=[]
    for sequence in sequences:
        path=extract(data,sequence,cache);features=Features(path)
        root=load_sequence(data,sequence)[0]
        quality.append(json.loads((Path(cache)/f"{sequence}.json").read_text()))
        recipes=[(method,"clean",42) for method in ("stationary","frame","keyframe","no_refine","no_depth_filter")]
        if not smoke:
            recipes += [("keyframe",case,42) for case in CASES if case!="clean"]
            recipes += [("keyframe","depth_mask_70",seed) for seed in (43,44)]
        for method,case,seed in recipes:
            record,replay=execute(features,sequence,method,case,seed,base,root,threshold,out,cache)
            rows.append(record);replays.append(replay)
            error=record["held_last_ate_rmse_m"]
            print(f"{sequence} {method} {case} seed={seed}: coverage={record['tracked_fraction']:.3f} held-ATE={error}",flush=True)
    write_rows(out/"metrics.csv",rows)
    save_json(out/"metrics.json",rows);save_json(out/"data_quality.json",quality)
    # Only derived trajectories, never keypoint descriptors or raw images, enter the replay.
    save_json(out/"replay.json",replays)
    source_files=list((ROOT/"depthtrack").glob("*.py"))+list((ROOT/"scripts").glob("*.py"))
    manifest=dict(project="DepthTrack",protocol="depthtrack-v1",generated_utc=datetime.now(timezone.utc).isoformat(),
        python=platform.python_version(),platform=platform.system(),
        dependencies={p:importlib.metadata.version(p) for p in ("numpy","opencv-python-headless","matplotlib")},
        calibration_sha256=file_hash(calibration_path),dataset_manifest_sha256=file_hash(ROOT/"docs"/"DATASET_MANIFEST.json"),
        configuration=asdict(base),warning_threshold=threshold,split=SPLITS,runs=len(rows),
        cached_runs=sum(r["cached"] for r in rows),elapsed_seconds=time.perf_counter()-start,
        source_sha256={p.relative_to(ROOT).as_posix():file_hash(p) for p in sorted(source_files)},
        output_sha256={name:file_hash(out/name) for name in ("metrics.csv","metrics.json","data_quality.json","replay.json")},
        limitations=["Four sequences from one indoor benchmark; not independent domains",
                     "No confidence intervals across correlated frames or repeated corruption seeds",
                     "Tracking failure outputs missing poses; held-last is an evaluation-only penalty",
                     "No scale alignment, loop closure or relocalization",
                     "Quality diagnostic is contemporaneous, not a calibrated probability or proven early warning",
                     "Cached runs retain their original measured tracking times"])
    save_json(out/"experiment.json",manifest)
    from .report import render
    render(out,rows,replays,manifest)
    return manifest

