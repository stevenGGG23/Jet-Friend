#!/usr/bin/env python3
import os
import sys
import subprocess
import time

def kill_servers():
    """Kill existing servers on common ports"""
    for port in [5000, 5001, 5002, 5003]:
        try:
            result = subprocess.run(['lsof', '-ti', f':{port}'], 
                                 capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        subprocess.run(['kill', '-9', pid], timeout=2)
                        print(f"🔥 Killed process {pid} on port {port}")
                    except:
                        pass
        except:
            pass

def start_server():
    """Start the JetFriend server"""
    try:
        print("🧹 Cleaning up old processes...")
        kill_servers()
        time.sleep(1)
        
        print("🚀 Starting JetFriend server...")
        
        # Set port to 5002
        os.environ['PORT'] = '5002'
        
        # Import and run server
        import simple_server_2api
        print("✅ Server module imported successfully")
        
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    start_server()
