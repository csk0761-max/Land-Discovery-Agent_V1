import time
from agent import agent_evaluate_parcel

start = time.time()
print("Starting agent evaluation...")
report = agent_evaluate_parcel(34.0522, -118.2437, 100, custom_prompt="")
end = time.time()

print(f"\nExecution took {end - start:.2f} seconds.")
