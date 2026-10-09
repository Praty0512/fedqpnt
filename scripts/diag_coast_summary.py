"""Summarise results/diag_r2/coast/*.txt (diag_coast.py outputs): median err_h and NEES6 vs coast time, per (grade, variant)."""
import os, re, glob, numpy as np
from collections import defaultdict
D = defaultdict(lambda: defaultdict(list))
for f in glob.glob('results/diag_r2/coast/*.txt'):
    name = os.path.basename(f)[:-4]
    v = name.split('_')[0]; g = '_'.join(name.split('_')[1:-1])
    for line in open(f):
        m = re.match(r't=\s*([\d.]+) \(T0\+\s*(\d+)\) FILTER err_h=\s*([\d.]+).*?NEES6=\s*([\d.]+)', line)
        if m:
            D[(g, v)][int(m.group(2))].append((float(m.group(3)), float(m.group(4))))
for k in sorted(D):
    print(k)
    for dt in sorted(D[k]):
        a = np.array(D[k][dt])
        print(f"  T0+{dt:3d}: err_h median={np.median(a[:,0]):8.1f} (n={len(a)}) NEES6 median={np.median(a[:,1]):9.1f} max={a[:,1].max():9.1f}")
