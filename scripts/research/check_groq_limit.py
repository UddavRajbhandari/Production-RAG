"""
Groq API Rate Limit Checker
Check when Groq API quota will reset.
"""

import os
import sys
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.getcwd())

# Load .env
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import requests


def check_groq_limit() -> None:
    """Check Groq API rate limit status."""
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        print("[ERROR] GROQ_API_KEY not found in .env")
        return

    print("=" * 50)
    print("Groq API Rate Limit Checker")
    print("=" * 50)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Method 1: Check models endpoint (always available)
    print("\n[1] Checking models endpoint...")
    try:
        resp = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            print("    [OK] Models endpoint available")
    except Exception as e:
        print(f"    [ERR] {e}")

    # Method 2: Try actual chat completion (tests rate limit)
    print("\n[2] Testing chat completion (small request)...")
    try:
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5,
        }
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )

        if resp.status_code == 200:
            print("    [OK] API AVAILABLE - No rate limit!")
            print(f"    Response time: {resp.elapsed.total_seconds():.2f}s")
        elif resp.status_code == 429:
            error = resp.json()
            msg = error.get("error", {}).get("message", "")

            # Extract time from message
            import re

            match = re.search(r"try again in ([\d.]+)", msg)
            if match:
                wait_seconds = float(match.group(1))
                reset_time = datetime.now() + timedelta(seconds=wait_seconds)

                print("\n    [STATUS] RATE LIMIT EXHAUSTED")
                print(f"    Wait time: {wait_seconds / 60:.1f} minutes")
                print(f"    Resets at: {reset_time.strftime('%H:%M:%S')}")
                print("    (Approximate reset: midnight UTC)")
            else:
                print(f"    [STATUS] Rate limited: {msg}")
        else:
            print(f"    [STATUS] Unexpected: {resp.status_code} - {resp.text[:100]}")

    except requests.exceptions.Timeout:
        print("    [ERROR] Request timed out")
    except Exception as e:
        print(f"    [ERROR] {e}")

    print("\n" + "=" * 50)
    print("Quick Reference:")
    print("  - Free tier resets at midnight UTC")
    print("  - Current limit: 100,000 tokens/day")
    print("  - Model: llama-3.3-70b-versatile")
    print("=" * 50)


def main() -> None:
    check_groq_limit()


if __name__ == "__main__":
    main()
