"""Measure cold-start time of RESIVO.exe over 3 runs."""

import os
import subprocess
import time
from pathlib import Path

exe_path = Path("dist/RESIVO/RESIVO.exe").resolve()
log_path = Path(os.environ["APPDATA"]) / "RESIVO" / "logs" / "app.log"

print(f"Testing EXE: {exe_path}")
print(f"Log path: {log_path}")

runs = []
for run_idx in range(1, 4):
    # Get current log size / line count
    start_pos = log_path.stat().st_size if log_path.exists() else 0
    t0 = time.perf_counter()

    proc = subprocess.Popen([str(exe_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    logged_time = None
    wall_time = None
    
    # Wait until log has new line
    for _ in range(100): # up to 10 seconds
        time.sleep(0.05)
        if log_path.exists() and log_path.stat().st_size > start_pos:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(start_pos)
                new_lines = f.readlines()
                for line in new_lines:
                    if "Logging started" in line or "Installed PostgREST" in line:
                        wall_time = time.perf_counter() - t0
                        logged_time = wall_time
                        break
        if logged_time is not None:
            break
            
    # Terminate process
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass

    print(f"Run {run_idx}: cold-start wall-clock = {wall_time:.3f} s" if wall_time else f"Run {run_idx}: timed out")
    if wall_time:
        runs.append(wall_time)
    time.sleep(0.5)

if runs:
    avg = sum(runs) / len(runs)
    print(f"Baseline Average cold-start: {avg:.3f} s over {len(runs)} runs")
