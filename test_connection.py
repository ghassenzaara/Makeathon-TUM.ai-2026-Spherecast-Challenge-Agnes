"""Agnes Integration Diagnostic — Tests each layer independently."""
import os
import sys
from dotenv import load_dotenv
load_dotenv()

print("=" * 60)
print("  AGNES INTEGRATION DIAGNOSTIC")
print("=" * 60)

# ── Test 1: Environment ──
print("\n[1/6] Environment...")
api_key = os.getenv("GEMINI_API_KEY", "")
vertex_key = os.getenv("VERTEX_API_KEY", "")
project_id = os.getenv("GCP_PROJECT_ID", "")
print(f"  GEMINI_API_KEY: {'SET (' + api_key[:8] + '...)' if api_key else 'MISSING'}")
print(f"  VERTEX_API_KEY: {'SET (' + vertex_key[:8] + '...)' if vertex_key else 'MISSING'}")
print(f"  GCP_PROJECT_ID: {project_id or 'MISSING'}")

# ── Test 2: Context File ──
print("\n[2/6] Context file...")
try:
    with open("ai_context.txt", "r", encoding="utf-8") as f:
        ctx = f.read()
    companies = ctx.count("Company:")
    print(f"  OK: {len(ctx):,} chars, {companies} product blocks")
except Exception as e:
    print(f"  FAIL: {e}")

# ── Test 3: DNS Resolution ──
print("\n[3/6] DNS resolution...")
import socket
targets = [
    "generativelanguage.googleapis.com",
    "us-central1-aiplatform.googleapis.com",
    "www.google.com",
]
for host in targets:
    try:
        ip = socket.getaddrinfo(host, 443, socket.AF_INET)[0][4][0]
        print(f"  OK: {host} -> {ip}")
    except Exception as e:
        print(f"  FAIL: {host} -> {e}")

# ── Test 4: HTTP connectivity (requests library) ──
print("\n[4/6] HTTP via requests...")
import requests
test_urls = [
    "https://generativelanguage.googleapis.com/",
    "https://us-central1-aiplatform.googleapis.com/",
]
for url in test_urls:
    try:
        r = requests.get(url, timeout=10)
        print(f"  OK: {url} -> HTTP {r.status_code}")
    except Exception as e:
        print(f"  FAIL: {url} -> {type(e).__name__}: {str(e)[:100]}")

# ── Test 5: HTTP connectivity (httpx library — used by google-genai) ──
print("\n[5/6] HTTP via httpx (used by google-genai SDK)...")
try:
    import httpx
    print(f"  httpx version: {httpx.__version__}")
    for url in test_urls:
        try:
            r = httpx.get(url, timeout=10, follow_redirects=True)
            print(f"  OK: {url} -> HTTP {r.status_code}")
        except Exception as e:
            print(f"  FAIL: {url} -> {type(e).__name__}: {str(e)[:100]}")
except ImportError:
    print("  FAIL: httpx not installed")

# ── Test 6: Gemini API call (small test) ──
print("\n[6/6] Gemini API call (tiny prompt)...")
try:
    from google import genai
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Say hello in one word.",
        config=genai.types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=10,
        ),
    )
    print(f"  OK: Gemini responded: '{response.text.strip()}'")
except Exception as e:
    print(f"  FAIL ({type(e).__name__}): {str(e)[:300]}")

# ── Test 6b: Vertex AI REST call ──
if vertex_key and project_id:
    print("\n[6b] Vertex AI REST API call (tiny prompt)...")
    try:
        url = (
            f"https://us-central1-aiplatform.googleapis.com/v1/"
            f"projects/{project_id}/locations/us-central1/"
            f"publishers/google/models/gemini-2.0-flash:generateContent"
        )
        headers = {"Content-Type": "application/json", "X-Goog-Api-Key": vertex_key}
        payload = {
            "contents": [{"role": "user", "parts": [{"text": "Say hello in one word."}]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 10},
        }
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            print(f"  OK: Vertex AI responded: '{text.strip()}'")
        else:
            print(f"  FAIL: HTTP {r.status_code} -> {r.text[:300]}")
    except Exception as e:
        print(f"  FAIL ({type(e).__name__}): {str(e)[:300]}")

print("\n" + "=" * 60)
print("  DIAGNOSTIC COMPLETE")
print("=" * 60)
