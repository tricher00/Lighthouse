#!/usr/bin/env python3
"""
Stop Lighthouse Server
Finds and kills the Python process running the Lighthouse server.
"""
import subprocess
import sys
from pathlib import Path

def load_port_from_env():
    """Load PORT from .env file."""
    env_file = Path(__file__).parent / ".env"
    port = 8000  # Default
    
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                if line.strip().startswith('PORT='):
                    try:
                        port = int(line.split('=')[1].strip())
                    except (ValueError, IndexError):
                        pass
    return port

def find_python_processes():
    """Find all Python processes with full command lines."""
    try:
        result = subprocess.run(
            ['wmic', 'process', 'where', "name like '%python%'", 'get', 
             'ProcessId,CommandLine', '/value'],
            capture_output=True,
            text=True,
            shell=True
        )
        
        processes = []
        current_cmdline = None
        current_pid = None
        
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line.startswith('CommandLine='):
                current_cmdline = line[12:]  # Remove 'CommandLine='
            elif line.startswith('ProcessId='):
                try:
                    current_pid = int(line[10:])  # Remove 'ProcessId='
                except ValueError:
                    current_pid = None
            
            # When we have both, add to list and reset
            if current_cmdline is not None and current_pid is not None:
                processes.append((current_pid, current_cmdline))
                current_cmdline = None
                current_pid = None
        
        return processes
    except Exception as e:
        print(f"Error finding processes: {e}")
        return []

def is_lighthouse_process(cmdline):
    """Check if a command line is a Lighthouse server process."""
    cmdline_lower = cmdline.lower()
    
    # Indicators that this is the Lighthouse server or its children
    indicators = [
        'main.py',              # Direct run of main.py
        'lighthouse',           # Lighthouse in path
        'uvicorn',              # Uvicorn server
        'multiprocessing',      # Multiprocessing child (uvicorn reload workers)
    ]
    
    # Exclude our own stop.py process
    if 'stop.py' in cmdline_lower:
        return False
    
    return any(indicator in cmdline_lower for indicator in indicators)

def kill_process(pid):
    """Kill a process by PID."""
    result = subprocess.run(
        ['taskkill', '/F', '/T', '/PID', str(pid)],
        capture_output=True,
        text=True
    )
    return result.returncode == 0

def main():
    print("Stopping Lighthouse server...")
    
    port = load_port_from_env()
    print(f"Looking for Lighthouse/Python processes...")
    
    processes = find_python_processes()
    
    if not processes:
        print("[OK] No Python processes found")
        return 0
    
    # Find Lighthouse-related processes
    lighthouse_pids = []
    
    print(f"\nScanning {len(processes)} Python process(es):")
    for pid, cmdline in processes:
        is_lh = is_lighthouse_process(cmdline)
        if is_lh:
            # Truncate for display
            display_cmd = cmdline[:70] + "..." if len(cmdline) > 70 else cmdline
            print(f"  [TARGET] PID {pid}: {display_cmd}")
            lighthouse_pids.append(pid)
    
    if not lighthouse_pids:
        print("  (none found)")
        print("\n[OK] No Lighthouse server processes running")
        return 0
    
    print(f"\nStopping {len(lighthouse_pids)} process(es)...")
    
    success_count = 0
    for pid in lighthouse_pids:
        print(f"  - Killing PID {pid}...", end=' ')
        if kill_process(pid):
            print("[OK]")
            success_count += 1
        else:
            print("[FAIL]")
    
    if success_count > 0:
        print(f"\n[OK] Lighthouse server stopped!")
        return 0
    else:
        print(f"\n[FAIL] Failed to stop server - may need Administrator privileges")
        return 1

if __name__ == "__main__":
    sys.exit(main())
