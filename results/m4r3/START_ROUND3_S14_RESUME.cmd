@echo off
rem Resume S14 after a pause: releases the RESERVED placeholders and runs the rest one at a time.
rem Start only when the m4r3-s14 window has closed.
cd /d C:\Users\DELL\Downloads\FEDQPNT
start "m4r3-s14" /min cmd /c ""C:\Users\DELL\AppData\Local\Programs\Python\Python313\python.exe" scripts\m4_campaign.py --phase 1 --only S14 --take-reserved --workers 1 --weights results/m1/detector_weights_sup_v5.npz >> results\m4r3\phase1_s14.log 2>&1"
echo Resumed S14 in a minimised window "m4r3-s14". Do NOT close it. You can close this one.
pause
