import os
import sys

sys.path.insert(0, os.getcwd())
import time

from src.reasoning.utils.llm_client import LLMClient

client = LLMClient()
print(f"Provider: {client.provider}")
print(f"Active Profile: {client.active_profile}")

start = time.time()
response = client.generate("Hi, say 'Ready' if you are working.")
end = time.time()

print(f"Response: {response.text}")
print(f"Latency: {end - start:.2f}s")
