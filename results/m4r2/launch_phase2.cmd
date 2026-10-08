@echo off
cd /d C:\Users\DELL\Downloads\FEDQPNT
if "%M4R2_WEIGHTS%"=="" (echo M4R2_WEIGHTS not set & exit /b 2)
"C:\Users\DELL\AppData\Local\Programs\Python\Python313\python.exe" scripts\m4_campaign.py --phase 2 --weights %M4R2_WEIGHTS% >> results\m4r2\phase2.log 2>&1
