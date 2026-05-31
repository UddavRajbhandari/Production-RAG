"""Regenerate .secrets.baseline with proper exclusions."""

import json
import os
import subprocess

result = subprocess.run(
    ["detect-secrets", "scan", "--no-gitignore"],
    capture_output=True,
    text=True,
    cwd=os.getcwd(),
)
data = json.loads(result.stdout)

data["exclude"] = {
    "files": (
        "\.secrets\.baseline|\.git|__pycache__|\.venv|"
        "node_modules|\.next|\.pkl$|\.png$|\.jpg$|"
        "\.docx$|\.xlsx$|my_tenant\.txt"
    ),
}

with open(".secrets.baseline", "w") as f:
    json.dump(data, f, indent=2)

print(f"Generated .secrets.baseline with {len(data.get('results', {}))} secret groups")
