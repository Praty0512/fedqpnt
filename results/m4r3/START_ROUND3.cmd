@echo off
rem Double-click to start (or resume) the ROUND-3 test campaign (core-freeze-6, seeds 10060-10089), WITHOUT S14.
rem Safe to run again after any interruption: finished runs are skipped.
rem Run it only when no m4r3 windows are open.
rem   m4r3-phase1 : single-node, 4 workers, S14 excluded
rem   m4r3-phase2 : fleet scenarios, 1 fleet at a time
rem S14 (4-hour scenario) is started separately with START_ROUND3_S14.cmd AFTER phase 1 has finished.
cd /d C:\Users\DELL\Downloads\FEDQPNT
start "m4r3-phase1" /min cmd /c results\m4r3\launch_phase1.cmd
start "m4r3-phase2" /min cmd /c results\m4r3\launch_phase2.cmd
echo.
echo Round-3 campaign started in two minimised windows (m4r3-phase1, m4r3-phase2). Do NOT close them. You can close this one.
pause
