@echo off
cd /d C:\Users\DELL\Downloads\FEDQPNT
if "%M4R2_WEIGHTS%"=="" (echo M4R2_WEIGHTS not set & exit /b 2)
"C:\Program Files\Git\bin\bash.exe" C:/Users/DELL/Downloads/FEDQPNT/scripts/m4r2_autoscale.sh
