import os
import sys

with open('.env') as f:
    for line in f:
        if line.strip() and '=' in line:
            key, value = line.strip().split('=', 1)
            os.environ[key] = value

sys.path.insert(0, '/Users/tahilbansal/Projects/FleetMind')

from agent.dispatcher_agent import build_dispatcher_agent

print("=== Testing Agent ===\n")
try:
    agent = build_dispatcher_agent()
    print("✓ Agent built successfully\n")
    
    print("Test 1: Get current routes\n")
    result = agent.invoke({"input": "What routes are currently planned?"})
    print(f"\nResult: {result}\n")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
