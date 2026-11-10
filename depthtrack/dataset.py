"""Timestamp association and ground truth are separate from the tracker."""

import hashlib
import json
from pathlib import Path

import numpy as np

from .geometry import interpolate_pose

SEQUENCES = ("xyz", "rpy", "desk", "floor")
SPLITS = {"xyz": "development", "rpy": "validation", "desk": "test", "floor": "test"}


def index_file(path, numeric=False):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cells = line.split()
        timestamp = float(cells[0])
        if not np.isfinite(timestamp) or (rows and timestamp <= rows[-1][0]):
            raise ValueError("Non-monotonic or invalid index timestamps")
        values = [float(c) for c in cells[1:]] if numeric else cells[1:]
        if numeric and (len(values) != 7 or not np.isfinite(values).all()):
            raise ValueError("Invalid ground-truth record")
        if not numeric and (len(values) != 1 or Path(values[0]).is_absolute() or ".." in Path(values[0]).parts):
            raise ValueError("Invalid image path")
        rows.append((timestamp, values))
    if not rows:
        raise ValueError("Empty index")
    return rows


def associate(rgb, depth, tolerance=.02):
    """Greedy globally closest one-to-one matches, then chronological order."""
    depth_times = np.array([r[0] for r in depth])
    candidates = []
    for i, row in enumerate(rgb):
        left, right = np.searchsorted(depth_times, [row[0]-tolerance, row[0]+tolerance], side="left")
        for j in range(left, right):
            candidates.append((abs(row[0]-depth[j][0]), i, j))
    used_rgb, used_depth, pairs = set(), set(), []
    for delta, i, j in sorted(candidates):
        if i not in used_rgb and j not in used_depth:
            pairs.append((i, j))
            used_rgb.add(i)
            used_depth.add(j)
    return sorted(pairs)


def load_sequence(data, sequence):
    if sequence not in SEQUENCES:
        raise ValueError(sequence)
    root = Path(data) / f"rgbd_dataset_freiburg1_{sequence}"
    rgb, depth = index_file(root / "rgb.txt"), index_file(root / "depth.txt")
    pairs = associate(rgb, depth)
    frames = [(rgb[i][0], root/rgb[i][1][0], depth[j][0], root/depth[j][1][0]) for i,j in pairs]
    return root, frames, rgb, depth


def ground_truth(root, times, max_gap=.1):
    rows = index_file(Path(root)/"groundtruth.txt", numeric=True)
    timestamps = np.array([r[0] for r in rows])
    output = np.full((len(times), 4, 4), np.nan)
    for i, timestamp in enumerate(times):
        j = np.searchsorted(timestamps, timestamp)
        if j == 0 or j == len(rows) or timestamps[j]-timestamps[j-1] > max_gap:
            continue
        output[i] = interpolate_pose(rows[j-1][0], rows[j-1][1], rows[j][0], rows[j][1], timestamp)
    return output


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()

