"""Create a small credited RGB/feature/trajectory replay from measured desk data."""

import csv
import gzip
from pathlib import Path
import sys

import cv2
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from depthtrack.dataset import load_sequence
from depthtrack.features import Features


def main():
    out=ROOT/"reports"/"figures";out.mkdir(parents=True,exist_ok=True)
    _,frames,_,_=load_sequence(ROOT/"data/raw","desk")
    features=Features(ROOT/"data/features/desk.npz")
    with gzip.open(ROOT/"reports/traces/desk__keyframe__clean__42.csv.gz","rt",encoding="utf-8") as stream:
        rows=list(csv.DictReader(stream))
    positions=np.array([[float(r[k]) if r[k] else np.nan for k in ("x","y","gt_x","gt_y")] for r in rows])
    all_xy=np.concatenate((positions[:,:2],positions[:,2:]))
    lo=np.nanmin(all_xy,axis=0);hi=np.nanmax(all_xy,axis=0)
    scale=min(270/max(.1,hi[0]-lo[0]),190/max(.1,hi[1]-lo[1]))
    def project(point):
        p=(point-(lo+hi)/2)*scale
        return int(480+p[0]),int(135-p[1])
    images=[];durations=[]
    selected=list(range(0,len(rows),8))
    for index in selected:
        row=rows[index]
        rgb=cv2.imread(str(frames[int(row["frame"])][1]))
        preview=cv2.resize(rgb,(320,240))
        points=features.frame(int(row["frame"]))["uv"][::12]/2
        for p in points:cv2.circle(preview,tuple(np.rint(p).astype(int)),2,(100,240,150),-1)
        canvas=np.full((290,640,3),(35,24,13),dtype=np.uint8)
        canvas[30:270,:320]=preview
        for columns,color in (((2,3),(180,180,180)),((0,1),(190,220,80))):
            last=None
            for point in positions[:index+1,list(columns)]:
                if not np.isfinite(point).all():last=None;continue
                p=project(point)
                if last is not None:cv2.line(canvas,last,p,color,1,cv2.LINE_AA)
                last=p
            if last is not None:cv2.circle(canvas,last,4,color,-1)
        label=f"desk | t={float(row['elapsed_s']):.1f}s | {row['status']} | quality {float(row['quality']):.2f}"
        cv2.putText(canvas,label,(8,20),cv2.FONT_HERSHEY_SIMPLEX,.47,(240,240,240),1,cv2.LINE_AA)
        cv2.putText(canvas,"ORB points (not all inliers) | estimate / reference",(8,285),cv2.FONT_HERSHEY_SIMPLEX,.40,(220,220,220),1,cv2.LINE_AA)
        image=Image.fromarray(cv2.cvtColor(canvas,cv2.COLOR_BGR2RGB))
        if index==selected[len(selected)//2]:image.save(out/"demo-preview.png")
        images.append(image.quantize(colors=96))
        next_index=min(index+8,len(rows)-1)
        durations.append(max(50,int(1000*(float(rows[next_index]["elapsed_s"])-float(row["elapsed_s"])))))
    images[0].save(out/"desk-demo.gif",save_all=True,append_images=images[1:],duration=durations,loop=0,disposal=2)
    print(f"Created credited desk replay: {len(images)} frames, {(out/'desk-demo.gif').stat().st_size/1e6:.2f} MB")


if __name__=="__main__":main()
