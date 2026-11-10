"""Broad regression bounds on the development sequence, not benchmark claims."""

import json
from pathlib import Path
import sys

folder=Path(sys.argv[1] if len(sys.argv)>1 else "data/real-smoke")
rows=json.loads((folder/"metrics.json").read_text())
row=next(r for r in rows if r["sequence"]=="xyz" and r["method"]=="keyframe" and r["case"]=="clean")
if row["frames"]<700 or row["tracked_fraction"]<.9:
    raise SystemExit("Real-data smoke lost expected input or tracking coverage")
if row["held_last_ate_rmse_m"] is None or row["held_last_ate_rmse_m"]>.35:
    raise SystemExit("Real-data smoke exceeds broad development position-error bound")
if row["rpe_05s_rotation_rmse_deg"] is None or row["rpe_05s_rotation_rmse_deg"]>8.:
    raise SystemExit("Real-data smoke exceeds broad development rotation-error bound")
print("Real xyz sequence passes broad coverage and metric regression bounds")
