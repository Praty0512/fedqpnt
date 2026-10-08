#!/bin/bash
# Waiter: phase 1 (4 workers) and phase 2 (1 fleet) are already running (launch_all.cmd).
# When phase 1 logs DONE: start a 2nd phase-2 instance (--reverse) if free RAM >= 3.5 GB; re-check every 10 min for 2 h.
cd /c/Users/DELL/Downloads/FEDQPNT
L=results/m4r2/autoscale.log
echo "$(date) waiter started" >> $L
until grep -q "^DONE" results/m4r2/phase1.log 2>/dev/null; do sleep 60; done
echo "$(date) phase1 DONE detected" >> $L
grep -q "^DONE" results/m4r2/phase2.log 2>/dev/null && { echo "$(date) phase2 already DONE; nothing to scale" >> $L; exit 0; }
for i in $(seq 1 13); do
  free=$(powershell -NoProfile -c "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1024)")
  echo "$(date) free RAM MB: $free" >> $L
  if [ "$free" -ge 3584 ]; then
    start_cmd="results\m4r2\launch_phase2_rev.cmd"
    nohup cmd //c "$start_cmd" >/dev/null 2>&1 &
    echo "$(date) launched phase2 --reverse" >> $L; exit 0
  fi
  sleep 600
done
echo "$(date) gave up on phase2 --reverse (RAM)" >> $L
