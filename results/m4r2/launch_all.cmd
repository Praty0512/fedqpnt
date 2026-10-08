@echo off
rem usage: launch_all.cmd <weights.npz>   -- starts phase 1 (4 workers), phase 2 (1 fleet) and the autoscale waiter, all detached
if "%~1"=="" (echo usage: launch_all.cmd weights.npz & exit /b 2)
set M4R2_WEIGHTS=%~1
cd /d C:\Users\DELL\Downloads\FEDQPNT
echo %date% %time% launch_all weights=%M4R2_WEIGHTS% >> results\m4r2\autoscale.log
start "m4r2-phase1" /min cmd /c results\m4r2\launch_phase1.cmd
start "m4r2-phase2" /min cmd /c results\m4r2\launch_phase2.cmd
start "m4r2-autoscale" /min cmd /c results\m4r2\launch_autoscale.cmd
