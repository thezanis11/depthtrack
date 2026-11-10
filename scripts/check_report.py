"""Verify committed source/data/output identities and derived trajectory rows."""

import csv
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out=ROOT/"reports"
    manifest=json.loads((out/"experiment.json").read_text())
    for group,base in (("source_sha256",ROOT),("output_sha256",out)):
        for relative,expected in manifest[group].items():
            if digest(base/relative)!=expected:raise ValueError(f"Integrity mismatch: {relative}")
    if digest(out/"calibration.json")!=manifest["calibration_sha256"]:
        raise ValueError("Calibration mismatch")
    if digest(ROOT/"docs/DATASET_MANIFEST.json")!=manifest["dataset_manifest_sha256"]:
        raise ValueError("Dataset provenance mismatch")
    rows=json.loads((out/"metrics.json").read_text())
    if len(rows)!=manifest["runs"] or len(rows)!=44:raise ValueError("Unexpected full campaign size")
    for row in rows:
        path=out/row["trace"]
        if digest(path)!=row["trace_sha256"]:raise ValueError("Trace checksum mismatch")
        with gzip.open(path,"rt",encoding="utf-8") as stream:trace=list(csv.DictReader(stream))
        if len(trace)!=row["frames"]:raise ValueError("Trace row count mismatch")
        if sum(bool(r["x"]) for r in trace)!=row["tracked_frames"]:raise ValueError("Tracked pose count mismatch")
    page=(out/"index.html").read_text(encoding="utf-8")
    HTMLParser().feed(page)
    if any(marker in page for marker in ("const trials=REPLAY","<tbody>TABLE","GENERATED")):
        raise ValueError("Unexpanded report marker")
    for file in ("figures/benchmark.png","figures/trajectories.png","RESULTS_FR.md","diagnostic_tracked_only.csv"):
        if not (out/file).is_file():raise ValueError(f"Missing deliverable {file}")
    print("Source, data provenance, calibration, result and trace integrity verified")


if __name__=="__main__":main()
