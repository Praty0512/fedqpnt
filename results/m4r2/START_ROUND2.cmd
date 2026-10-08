@echo off
rem Double-click to start (or resume) the round-2 test campaign.
rem Safe to run again after any interruption: finished runs are skipped.
rem Run it only when no m4r2 windows are open.
cd /d C:\Users\DELL\Downloads\FEDQPNT
call results\m4r2\launch_all.cmd results/m1/detector_weights_sup_v4.npz
echo.
echo Round-2 campaign started in three minimised windows (m4r2-phase1, m4r2-phase2, m4r2-autoscale).
echo Do NOT close those windows. You can close this one.
pause
