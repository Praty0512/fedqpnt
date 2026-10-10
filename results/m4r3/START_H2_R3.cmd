@echo off
rem Double-click to start (or resume) the H2/H4 re-run on core-freeze-6 (live seeds 10090-10099; tau calibration on tuning seeds 580-599).
rem Memory: one fleet = 1 server + 5 node processes (~3-4 GB). Do NOT run together with the 4-worker phase 1; start it after phase 1 (or with phase 2 only if >= 3.5 GB RAM stay free).
cd /d C:\Users\DELL\Downloads\FEDQPNT
start "m4r3-h2" /min cmd /c results\m4r3\h2_r3_chain.cmd
echo Started H2/H4 chain in a minimised window "m4r3-h2". Do NOT close it. You can close this one.
pause
