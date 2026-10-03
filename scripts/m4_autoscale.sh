#!/bin/bash
cd /c/Users/DELL/Downloads/FEDQPNT
PY=/c/Users/DELL/AppData/Local/Programs/Python/Python313/python.exe
L=results/m4/autoscale.log
echo "$(date) waiter started" >> $L
until grep -q "^DONE" results/m4/phase1.log; do sleep 60; done
echo "$(date) phase1 DONE detected" >> $L
nohup $PY scripts/m4_campaign.py --phase 1b --workers 2 --reverse >> results/m4/phase1b_rev.log 2>&1 &
echo "$(date) launched 1b --reverse (2 workers)" >> $L
for i in $(seq 1 13); do
  free=$(powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1024)")
  echo "$(date) free RAM MB: $free" >> $L
  if [ "$free" -ge 3584 ]; then
    nohup $PY scripts/m4_campaign.py --phase 2 --reverse >> results/m4/phase2_rev.log 2>&1 &
    echo "$(date) launched phase2 --reverse" >> $L; exit 0
  fi
  sleep 600
done
echo "$(date) gave up on phase2 --reverse (RAM)" >> $L
