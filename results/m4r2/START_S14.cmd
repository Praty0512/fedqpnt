@echo off
rem Run the 4-hour stability scenario S14 ONE AT A TIME (each run needs several GB of RAM).
rem Start this only AFTER the m4r2-phase1 window has finished. Safe to re-run: finished runs are skipped.
cd /d C:\Users\DELL\Downloads\FEDQPNT
start "m4r2-s14" /min cmd /c ""C:\Users\DELL\AppData\Local\Programs\Python\Python313\python.exe" scripts\m4_campaign.py --phase 1 --only S14 --take-reserved --workers 1 --weights results/m1/detector_weights_sup_v4.npz >> results\m4r2\phase1_s14.log 2>&1"
echo Started S14 in a minimised window "m4r2-s14". Do NOT close it. You can close this one.
pause
