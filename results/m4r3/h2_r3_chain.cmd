@echo off
rem H2/H4 round-3 chain (H2_PREREG Amendment 3): driver (60 fleets: h2+h4+control x 10 seeds x 2 arms) -> closed-loop tau calibration -> prereg analysis.
rem Each stage is resumable (finished runs are skipped). Fleets run strictly one at a time.
cd /d C:\Users\DELL\Downloads\FEDQPNT
set PY="C:\Users\DELL\AppData\Local\Programs\Python\Python313\python.exe"
%PY% -u scripts\h2_abrupt_h2h4_driver.py --parts h2,h4,control --live-seeds 10090-10099 --final --theta0 results/fleet/theta0_noabrupt_v3.npz --runs-dir results/fleet/h2_abrupt_runs_freeze6 --out results/fleet/h2_abrupt_freeze6.json --provenance-out results/fleet/h2_abrupt_provenance_freeze6.json >> results\m4r3\h2_driver.log 2>&1
%PY% -u scripts\h2_abrupt_calibrate_closedloop.py --live-seeds 10090-10099 --runs-dir results/fleet/h2_abrupt_runs_freeze6 --out-dir results/fleet/h2_abrupt_clean_closedloop_freeze6 --workers 2 >> results\m4r3\h2_calibrate.log 2>&1
%PY% -u scripts\h2_abrupt_prereg_analysis.py --tau-mode closedloop --live-seeds 10090-10099 --runs-dir results/fleet/h2_abrupt_runs_freeze6 --clean-dir results/fleet/h2_abrupt_clean_closedloop_freeze6 --out results/fleet/h2_abrupt_prereg_results_freeze6.json >> results\m4r3\h2_analysis.log 2>&1
