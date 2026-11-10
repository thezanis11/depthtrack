"""Streaming ORB extraction; compact caches never contain ground truth."""

import json
from pathlib import Path
import time

import cv2
import numpy as np

from .dataset import file_hash, load_sequence
from .geometry import backproject

RECIPE = {"version": 1, "nfeatures": 1600, "scaleFactor": 1.2, "nlevels": 8,
          "depth_scale": 5000., "depth_min": .3, "depth_max": 6., "depth_edge_m": .08,
          "lag_seconds": .1, "rgb_depth_tolerance_s": .02}


def sample_depth(uv, depth):
    if depth.dtype != np.uint16 or depth.shape != (480,640):
        raise ValueError("Expected TUM uint16 640x480 depth")
    xy = np.rint(uv).astype(int)
    xy[:,0] = np.clip(xy[:,0],1,638)
    xy[:,1] = np.clip(xy[:,1],1,478)
    z = depth[xy[:,1],xy[:,0]].astype(float)/5000.
    valid = (z >= RECIPE["depth_min"]) & (z <= RECIPE["depth_max"])
    neighborhood = np.stack([depth[xy[:,1]+dy,xy[:,0]+dx] for dy in (-1,0,1) for dx in (-1,0,1)]).astype(float)/5000.
    spread = neighborhood.max(axis=0)-neighborhood.min(axis=0)
    strict = valid & (neighborhood.min(axis=0)>0) & (spread < RECIPE["depth_edge_m"])
    return backproject(uv,z).astype(np.float32), valid, strict


def extract(data, sequence, cache_dir="data/features"):
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True,exist_ok=True)
    path = cache_dir/f"{sequence}.npz"
    metadata_path = cache_dir/f"{sequence}.json"
    root,frames,rgb,depth = load_sequence(data,sequence)
    indices = {name:file_hash(root/name) for name in ("rgb.txt","depth.txt")}
    if path.exists() and metadata_path.exists():
        record = json.loads(metadata_path.read_text())
        if record["recipe"] == RECIPE and record["indices_sha256"] == indices and record["opencv"] == cv2.__version__:
            if file_hash(path) != record["cache_sha256"]:
                raise ValueError("Feature cache checksum mismatch")
            return path
    cv2.setNumThreads(1)
    orb = cv2.ORB_create(nfeatures=RECIPE["nfeatures"])
    depth_times = np.array([r[0] for r in depth])
    columns = {key:[] for key in ("uv","desc","xyz","valid","strict","xyz_lag","valid_lag","strict_lag")}
    times,offsets = [],[0]
    start = time.perf_counter()
    extraction_ms=[]
    for i,(timestamp,color_path,depth_time,depth_path) in enumerate(frames):
        tick=time.perf_counter()
        gray=cv2.imread(str(color_path),cv2.IMREAD_GRAYSCALE)
        depth_image=cv2.imread(str(depth_path),cv2.IMREAD_UNCHANGED)
        if gray is None or gray.shape != (480,640) or depth_image is None:
            raise ValueError("Missing or invalid frame")
        keypoints,descriptors=orb.detectAndCompute(gray,None)
        uv=np.array([point.pt for point in keypoints],dtype=np.float32).reshape(-1,2)
        if descriptors is None:
            descriptors=np.empty((0,32),dtype=np.uint8)
        xyz,valid,strict=sample_depth(uv,depth_image)
        j=int(np.argmin(abs(depth_times-(timestamp-.1))))
        if abs(depth_times[j]-(timestamp-.1)) < .02:
            lag_image=cv2.imread(str(root/depth[j][1][0]),cv2.IMREAD_UNCHANGED)
            xyz_lag,valid_lag,strict_lag=sample_depth(uv,lag_image)
        else:
            xyz_lag=np.zeros_like(xyz);valid_lag=np.zeros_like(valid);strict_lag=np.zeros_like(strict)
        for key,value in dict(uv=uv,desc=descriptors,xyz=xyz,valid=valid,strict=strict,
                              xyz_lag=xyz_lag,valid_lag=valid_lag,strict_lag=strict_lag).items():
            columns[key].append(value)
        offsets.append(offsets[-1]+len(uv));times.append(timestamp)
        extraction_ms.append((time.perf_counter()-tick)*1000)
        if i%250==0:
            print(f"{sequence}: features {i}/{len(frames)}",flush=True)
    np.savez_compressed(path,times=np.array(times),offsets=np.array(offsets),
                        **{k:np.concatenate(v) for k,v in columns.items()})
    record=dict(sequence=sequence,recipe=RECIPE,opencv=cv2.__version__,indices_sha256=indices,
                cache_sha256=file_hash(path),rgb_frames=len(rgb),depth_frames=len(depth),
                matched_frames=len(frames),unmatched_rgb=len(rgb)-len(frames),
                max_association_error_ms=max(abs(t-d)*1000 for t,_,d,_ in frames),
                features=int(offsets[-1]),elapsed_seconds=time.perf_counter()-start,
                extraction_median_ms=float(np.median(extraction_ms)),
                extraction_p95_ms=float(np.quantile(extraction_ms,.95)))
    metadata_path.write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(f"{sequence}: {len(frames)} frames, {record['elapsed_seconds']:.1f}s, cache {path.stat().st_size/1e6:.1f}MB",flush=True)
    return path


class Features:
    def __init__(self,path):
        with np.load(path,allow_pickle=False) as archive:
            self.arrays={key:archive[key] for key in archive.files}
        self.times=self.arrays["times"]

    def frame(self,index,*,lag=False,mask_fraction=0.,seed=42):
        start,end=self.arrays["offsets"][index:index+2]
        suffix="_lag" if lag else ""
        result={key:self.arrays[key][start:end] for key in ("uv","desc")}
        result.update({key:self.arrays[key+suffix][start:end] for key in ("xyz","valid","strict")})
        if mask_fraction:
            keep=np.random.default_rng(seed+int(index)).random(end-start)>=mask_fraction
            result["valid"]=result["valid"] & keep
            result["strict"]=result["strict"] & keep
        return result
