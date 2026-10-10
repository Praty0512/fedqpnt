import json,glob,math,sys
from pathlib import Path
import numpy as np
R=Path("results/minimatrix_f6")
def med(root,rid,m,k):
    v=[]
    for f in glob.glob(str(root/rid/m/"seed_*.json")):
        r=json.load(open(f))
        if r["status"]=="ok": v.append(r["metrics"].get(k,np.nan))
    return (float(np.nanmedian(v)) if v and not all(math.isnan(x) for x in v) else float("nan")), len(v)
K=["rmse_h_att","rmse_h_post","max_h_att","rmse_h_pre","fpr","mean_w_gnss_att","t_rec"]
f=lambda x:f"{x:.3g}"
print("| rid | variant | n | "+" | ".join(K)+" |"); print("|---|---|---|"+"---|"*len(K))
for g in ("industrial_mems","tactical"):
  for cell in ("S1","S2-low","S2-med","S2-DM","S3","S4","S6","S13","S11","S7-p10"):
    rid=f"{cell}@{g}"
    for lab,root,m in (("C2 off (f6)",R,"fedqpnt_local"),("C2 on",R/"c2on","fedqpnt_local"),("undefended",R,"undefended"),("baseline_a",R,"baseline_a")):
        vals=[med(root,rid,m,k) for k in K]
        if vals[0][1]==0: continue
        print(f"| {rid} | {lab} | {vals[0][1]} | "+" | ".join(f(v[0]) for v in vals)+" |")
print()
for g in ("industrial_mems","tactical"):
  for cell in ("QUIET-0.3","QUIET-0.1"):
    rid=f"{cell}@{g}"
    for lab,root,m in (("C2 off",R/"c2off_quiet","fedqpnt_local"),("C2 on",R/"c2on","fedqpnt_local"),("undefended",R/"c2off_quiet","undefended"),("baseline_a",R/"c2off_quiet","baseline_a")):
        vals=[med(root,rid,m,k) for k in K]
        print(f"| {rid} | {lab} | {vals[0][1]} | "+" | ".join(f(v[0]) for v in vals)+" |")
