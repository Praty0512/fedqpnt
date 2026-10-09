"""Summarise results/diag_r2/matrix_<variant>__*.json: median over tuning seeds per (scenario, grade, method, variant)."""
import glob, json, os, numpy as np
from collections import defaultdict
D = defaultdict(lambda: defaultdict(list))
for f in sorted(glob.glob('results/diag_r2/matrix_*__*.json')):
    v = os.path.basename(f).split('__')[0].replace('matrix_', '')
    for k, r in json.load(open(f)).items():
        if k.startswith('_'): continue
        scn, g, m, s = k.split('|')
        D[(scn, g, m, v)]['seeds'].append(int(s))
        for key, val in r.items():
            D[(scn, g, m, v)][key].append(np.nan if val is None else float(val))
cols = ['rmse_h_att', 'rmse_v_att', 'rmse_h_post', 'max_h_post', 't_det', 't_rec', 'mean_w_gnss_att', 'fpr', 'far_per_hour', 'rmse_h_pre']
print('scenario|grade|method|variant|n|' + '|'.join(cols))
for k in sorted(D):
    d = D[k]
    print('|'.join(k) + f"|{len(d['seeds'])}|" + '|'.join(f"{np.nanmedian(d[c]):.4g}" if c in d and not np.all(np.isnan(d[c])) else 'nan' for c in cols))
