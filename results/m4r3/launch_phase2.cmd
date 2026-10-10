@echo off
cd /d C:\Users\DELL\Downloads\FEDQPNT
"C:\Users\DELL\AppData\Local\Programs\Python\Python313\python.exe" scripts\m4_campaign.py --phase 2 --weights results/m1/detector_weights_sup_v5.npz >> results\m4r3\phase2.log 2>&1
