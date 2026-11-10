"""Measured scientific figures and a self-contained trajectory replay."""

import html
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def number(value,digits=3):
    return "—" if value is None else f"{value:.{digits}f}"


def render(out,rows,replays,manifest):
    out=Path(out);figures=out/"figures";figures.mkdir(exist_ok=True)
    sequences=list(dict.fromkeys(row["sequence"] for row in rows))
    palette={"stationary":"#8793a8","frame":"#e5a04b","keyframe":"#147d92","no_refine":"#9367ad","no_depth_filter":"#749c50"}
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout="constrained")
    methods=list(palette)
    for offset,method in enumerate(methods):
        values=[next(r for r in rows if r["sequence"]==s and r["method"]==method and r["case"]=="clean") for s in sequences]
        x=np.arange(len(sequences))+(offset-2)*.15
        axes[0].bar(x,[r["held_last_ate_rmse_m"] or 1e-6 for r in values],.14,label=method,color=palette[method])
        axes[1].bar(x,[100*r["tracked_fraction"] for r in values],.14,color=palette[method])
    axes[0].set_yscale("log");axes[0].set_ylabel("Held-last ATE RMSE [m], log scale")
    axes[0].set_title("Initial-pose alignment, no scale correction")
    axes[1].set_ylabel("Frames with an estimated pose [%]");axes[1].set_ylim(0,105)
    axes[1].set_title("Coverage must accompany trajectory error")
    for ax in axes:ax.set_xticks(range(len(sequences)),sequences);ax.grid(axis="y",alpha=.2);ax.set_axisbelow(True)
    handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc="outside lower center",ncol=5)
    fig.savefig(figures/"benchmark.png",dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,len(sequences),figsize=(4*len(sequences),4),layout="constrained",squeeze=False)
    for ax,sequence in zip(axes[0],sequences):
        for method in ("frame","keyframe"):
            replay=next(r for r in replays if r["sequence"]==sequence and r["method"]==method and r["case"]=="clean")
            a=np.array([[np.nan if v is None else v for v in r[:9]] for r in replay["samples"]],float)
            if method=="frame":ax.plot(a[:,4],a[:,5],"k--",label="reference",linewidth=1.3)
            ax.plot(a[:,1],a[:,2],color=palette[method],label=method,linewidth=1)
        ax.set(title=sequence,xlabel="World x [m]",ylabel="World y [m]");ax.set_aspect("equal",adjustable="datalim");ax.grid(alpha=.2)
    axes[0,0].legend();fig.savefig(figures/"trajectories.png",dpi=160);plt.close(fig)
    table=[]
    for row in rows:
        table.append('<tr>'+''.join(f'<td>{html.escape(str(value))}</td>' for value in
            (row["sequence"],row["split"],row["method"],row["case"],row["seed"],
             number(100*row["tracked_fraction"],1),number(row["held_last_ate_rmse_m"]),
             number(row["rpe_05s_translation_rmse_m"]),number(row["rpe_05s_rotation_rmse_deg"]),
             number(row["tracking_p95_ms"],1)))+'</tr>')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DepthTrack — RGB-D odometry</title><style>
*{box-sizing:border-box}body{margin:0;color:#e9f0fa;background:#0c1523;font:16px/1.6 system-ui,sans-serif}main{max-width:1180px;margin:auto;padding:40px 24px}h1{font-size:clamp(38px,7vw,68px);margin:6px 0}h2{margin-top:38px}.tag{color:#61d6c5;letter-spacing:2px;text-transform:uppercase;font-size:13px}.lead{color:#b3c2d9;max-width:820px;font-size:19px}.notice{background:#25242c;border-left:4px solid #e5a04b;padding:15px 20px}select,input,button{background:#19283e;color:#fff;padding:10px;border:1px solid #59708f;border-radius:6px;font:inherit}select{max-width:100%}button{cursor:pointer}input[type=range]{width:100%}.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap}canvas{width:100%;height:390px;background:#142137;border-radius:12px;margin-top:16px}img{width:100%;height:auto;background:#fff;border-radius:8px}a{color:#9bd7ff}.scroll{overflow:auto}table{border-collapse:collapse;font-size:13px;width:100%}td,th{padding:10px;border-bottom:1px solid #324158;text-align:left}th{color:#a5bad8}#status{min-height:3em;color:#b9cbe2}.foot{font-size:14px;color:#a3b5cc}code{color:#9bd7ff}
</style><main><div class="tag">Geometry • estimation • failure analysis</div><h1>DepthTrack</h1>
<p class="lead">Estimate camera motion from real color and depth observations. Compare metric drift, missing poses and the limits of an online quality diagnostic.</p>
<p class="notice">TUM RGB-D indoor sequences. Parameters selected on xyz/rpy; desk/floor are evaluation sequences. Synthetic perturbations are labeled separately. No GPU, learned model, loop closure or scale correction.</p>
<h2>Measured trajectory replay</h2><p>Top-down world x/y projection. Cyan: estimate; dashed gray: motion-capture reference. Missing tracking remains a gap. This is a replay of exported measurements, not a live robot.</p>
<div class="controls"><label>Trial <select id="trial"></select></label><button id="play">Play</button></div>
<canvas id="view" width="1100" height="390" aria-label="Measured trajectory replay"></canvas><label>Time <input id="time" type="range" min="0" value="0" step="1"></label><div id="status"></div>
<h2>Accuracy and coverage together</h2><img src="figures/benchmark.png" alt="Clean sequence trajectory error and tracking coverage">
<p>Held-last error is an evaluation-only penalty: during missing tracking it holds the last known position. The tracker itself outputs no pose. The stationary baseline always emits the same pose, so 100% output coverage is not evidence of successful tracking.</p>
<img src="figures/trajectories.png" alt="Estimated and reference trajectories for each sequence">
<h2>All measured trials</h2><div class="scroll"><table><thead><tr><th>Sequence</th><th>Split</th><th>Method</th><th>Condition</th><th>Seed</th><th>Coverage %</th><th>Held ATE m</th><th>0.5s RPE m</th><th>0.5s RPE deg</th><th>Tracking p95 ms</th></tr></thead><tbody>TABLE</tbody></table></div>
<h2>Read the limitations</h2><p>The quality score measures current geometric support. It is not a probability and does not establish advance warning of future failure. The warning threshold uses only clean validation tracking. Precision/recall and trivial diagnostic baselines are in the exported metrics.</p>
<p>Frames and repeated corruptions are correlated: no frame-level confidence intervals are used. Tracking times exclude image reading and feature extraction; both stages are measured separately. Four indoor sequences do not establish road, drone or cross-camera performance.</p>
<h2>Reproduce and learn</h2><p><code>python -m depthtrack.cli benchmark</code></p><p><a href="metrics.csv">Metrics</a> · <a href="data_quality.json">Data quality</a> · <a href="experiment.json">Manifest</a> · <a href="../docs/GUIDE_FR.md">French guide</a></p>
<p class="foot">Real data: Sturm et al., “A Benchmark for the Evaluation of RGB-D SLAM Systems”, IROS 2012, TUM RGB-D, CC BY 4.0. Derived trajectories and figures by DepthTrack. GENERATED</p></main>
<script>const trials=REPLAY;const select=document.getElementById('trial'),slider=document.getElementById('time'),canvas=document.getElementById('view'),ctx=canvas.getContext('2d');let timer=null;
trials.forEach((t,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`${t.sequence} / ${t.method} / ${t.case} / seed ${t.seed}`;select.appendChild(o)});
function draw(){const t=trials[+select.value],a=t.samples,n=+slider.value;slider.max=a.length-1;const points=a.flatMap(r=>[[r[1],r[2]],[r[4],r[5]]]).filter(p=>p[0]!==null&&p[1]!==null);if(!points.length)return;const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]),loX=Math.min(...xs),hiX=Math.max(...xs),loY=Math.min(...ys),hiY=Math.max(...ys),scale=Math.min(1000/Math.max(.1,hiX-loX),300/Math.max(.1,hiY-loY)),project=(x,y)=>[550+(x-(loX+hiX)/2)*scale,195-(y-(loY+hiY)/2)*scale];ctx.clearRect(0,0,1100,390);
function line(x,y,color,dash){ctx.strokeStyle=color;ctx.lineWidth=2;ctx.setLineDash(dash);ctx.beginPath();let pen=false;for(let i=0;i<=n;i++){const r=a[i];if(r[x]===null||r[y]===null){pen=false;continue}const p=project(r[x],r[y]);if(pen)ctx.lineTo(...p);else ctx.moveTo(...p);pen=true}ctx.stroke();ctx.setLineDash([])}line(4,5,'#a7b3c5',[5,5]);line(1,2,'#61d6c5',[]);const r=a[n];if(r[1]!==null){const p=project(r[1],r[2]);ctx.fillStyle=r[10]?'#e5a04b':'#61d6c5';ctx.beginPath();ctx.arc(...p,6,0,7);ctx.fill()}ctx.fillStyle='#a7b3c5';ctx.font='15px system-ui';ctx.fillText('World x/y projection • metres • metric scale preserved',20,28);document.getElementById('status').textContent=`t = ${r[0].toFixed(2)} s | ${r[9]} | quality ${r[7].toFixed(3)} | position error ${r[8]===null?'unavailable':r[8].toFixed(3)+' m'} | ${r[10]?'warning':'no warning'}`}
select.addEventListener('change',()=>{slider.value=0;draw()});slider.addEventListener('input',draw);document.getElementById('play').addEventListener('click',()=>{if(timer){clearInterval(timer);timer=null;document.getElementById('play').textContent='Play'}else{document.getElementById('play').textContent='Pause';timer=setInterval(()=>{slider.value=(+slider.value+1)%(trials[+select.value].samples.length);draw()},50)}});draw();</script></html>'''
    page=page.replace("TABLE","".join(table)).replace("GENERATED",html.escape(manifest["generated_utc"]))
    page=page.replace("REPLAY",json.dumps(replays,separators=(",",":"),allow_nan=False).replace("<","\\u003c"))
    (out/"index.html").write_text(page,encoding="utf-8",newline="\n")
