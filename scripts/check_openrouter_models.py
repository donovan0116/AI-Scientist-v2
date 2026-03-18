#!/usr/bin/env python3
"""
Check OpenRouter model IDs used in launch_scientist_bfts.py.
- Without OPENROUTER_API_KEY: only checks if model IDs exist in OpenRouter list.
- With OPENROUTER_API_KEY: also sends a minimal chat request to verify access.
Usage: python scripts/check_openrouter_models.py
       OPENROUTER_API_KEY=sk-or-... python scripts/check_openrouter_models.py
"""
import json
import os
import sys
import urllib.request


def get_models_list():
    """Fetch available models from OpenRouter (public endpoint, no key required)."""
    try:
        req = urllib.request.Request("https://openrouter.ai/api/v1/models")
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.load(r)
        return data.get("data", [])
    except Exception as e:
        print(f"Failed to fetch models list: {e}")
        return []


def test_chat(model_id: str, api_key: str) -> tuple[bool, str]:
    """Send a minimal chat completion to OpenRouter. Returns (success, message)."""
    try:
        import openai
        client = openai.OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
        r = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": "Say OK in one word."}],
            max_tokens=10,
        )
        if r.choices and r.choices[0].message.content:
            return True, (r.choices[0].message.content or "").strip()
        return True, "(empty response)"
    except Exception as e:
        return False, str(e)


def main():
    models = get_models_list()
    known_ids = {m.get("id", "").strip() for m in models if m.get("id")}

    # Model IDs used in your launch command (without openrouter/ prefix)
    to_check = [
        "openai/o3-mini",
        "openai/gpt-4o-2024-11-20",
    ]

    print("OpenRouter model validity (from https://openrouter.ai/api/v1/models)")
    print("=" * 60)
    for mid in to_check:
        exists = mid in known_ids
        status = "valid" if exists else "NOT FOUND"
        print(f"  {mid}  ->  {status}")
    print()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("Set OPENROUTER_API_KEY to also test a real chat request.")
        return
    print("Live chat test (OPENROUTER_API_KEY set):")
    for mid in to_check:
        if mid not in known_ids:
            continue
        ok, msg = test_chat(mid, api_key)
        if ok:
            print(f"  {mid}  ->  OK ({msg[:40]})")
        else:
            print(f"  {mid}  ->  FAIL: {msg[:80]}")


if __name__ == "__main__":
    main()
