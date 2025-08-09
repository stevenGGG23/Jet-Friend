#!/usr/bin/env python3
import os
import signal
import subprocess
import time

def kill_python_servers():
    """Kill any existing Python servers on ports 5000-5010"""
    try:
        # Find and kill processes using these ports
        for port in range(5000, 5011):
            try:
                result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        try:
                            os.kill(int(pid), signal.SIGTERM)
                            print(f"🔥 Killed process {pid} using port {port}")
                            time.sleep(0.1)
                        except:
                            pass
            except:
                pass
    except:
        pass

if __name__ == "__main__":
    print("🧹 Cleaning up old server processes...")
    kill_python_servers()
    time.sleep(1)
    
    print("🚀 Starting fresh server...")
    # Import and run the new server
    exec(open('simple_server_2api.py').read())
