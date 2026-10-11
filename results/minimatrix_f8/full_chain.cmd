@echo off
cd /d C:\Users\DELL\Downloads\FEDQPNT
set PY="C:\Users\DELL\AppData\Local\Programs\Python\Python313\python.exe"
set W=results/m1/detector_weights_sup_v5.npz
%PY% -u scripts\minimatrix.py --phase 1 --seeds 530-532 --root results/minimatrix_f8 --workers 4 --skip S14 --weights %W% >> results\minimatrix_f8\full_runA.log 2>&1
%PY% -u scripts\minimatrix.py --phase 2 --seeds 530-531 --root results/minimatrix_f8 --weights %W% >> results\minimatrix_f8\full_fleet.log 2>&1
%PY% -u scripts\minimatrix.py --phase 1 --seeds 530 --root results/minimatrix_f8 --workers 1 --only S14 --weights %W% >> results\minimatrix_f8\full_S14.log 2>&1
echo CHAIN DONE >> results\minimatrix_f8\full_runA.log
