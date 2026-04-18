# agnes_core.py — The Brain of Agnes
# Core reasoning engine: orchestrates context loading, scraping, prompt assembly,
# LLM API calls, and response parsing.

import os
import re
import json
import time
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI

from prompts import AGNES_SYSTEM_PROMPT, QUERY_TEMPLATE
import scraper

# ─── Load environment ───
load_dotenv()

# ─── Module-level state ───
_CONTEXT_CACHE: Optional[str] = None
_CLIENT: Optional[OpenAI] = None
_ALL_SUPPLIERS: Optional[list[str]] = None

# ─── Configuration ───
MODEL_NAME = "gpt-4o-mini"  # 128K context window, fits our ~35K prompt easily
TEMPERATURE = 0.1
MAX_OUTPUT_TOKENS = 8192
MAX_RETRIES = 2
CONTEXT_FILE = "ai_context.txt"


def _get_client() -> OpenAI:
    """Lazily initializes and returns the OpenAI client."""
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY not found in environment.\n"
            "Set it in your .env file."
        )
    _CLIENT = OpenAI(api_key=api_key)
    print("  [AUTH] Connected via OpenAI API key")
    return _CLIENT


def load_context(filepath: str = CONTEXT_FILE) -> str:
    """
    Reads and caches the full ai_context.txt file.
    Called once at startup. Subsequent calls return the cached string.
    """
    global _CONTEXT_CACHE
    if _CONTEXT_CACHE is not None:
        return _CONTEXT_CACHE

    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"Context file not found: {filepath}\n"
            f"Run clean_data.py first to generate it from db.sqlite."
        )

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Sanity check: must have at least 10 product blocks
    company_count = content.count("Company:")
    if company_count < 10:
        raise ValueError(
            f"Context file appears corrupted: only {company_count} 'Company:' blocks found "
            f"(expected 100+). Re-run clean_data.py."
        )

    _CONTEXT_CACHE = content
    return _CONTEXT_CACHE


def _extract_all_suppliers(context: str) -> list[str]:
    """Extracts all unique supplier names from the context file."""
    global _ALL_SUPPLIERS
    if _ALL_SUPPLIERS is not None:
        return _ALL_SUPPLIERS

    suppliers = set()
    for match in re.findall(r'Approved Suppliers: \[([^\]]+)\]', context):
        for s in match.split(", "):
            s = s.strip()
            if s and s != "UNKNOWN_SUPPLIER":
                suppliers.add(s)

    _ALL_SUPPLIERS = sorted(list(suppliers))
    return _ALL_SUPPLIERS


def extract_relevant_suppliers(query: str, context: str) -> list[str]:
    """
    Identifies supplier names from ai_context.txt that are relevant to the query.
    Uses keyword matching against the full supplier list.

    If the query is broad (e.g., "top consolidation opportunities"), returns all suppliers.
    If the query mentions specific suppliers, returns only those.
    """
    all_suppliers = _extract_all_suppliers(context)
    query_lower = query.lower()

    # Check if query mentions specific suppliers
    mentioned = []
    for supplier in all_suppliers:
        if supplier.lower() in query_lower:
            mentioned.append(supplier)

    # If specific suppliers mentioned, return them
    if mentioned:
        return mentioned

    # For broad queries, we return a curated top list to avoid scraping all 40
    # (which would be slow). We pick the most common ones.
    top_suppliers = [
        "Prinova USA", "PureBulk", "Ingredion", "Jost Chemical",
        "Ashland", "Colorcon", "Cargill", "ADM",
        "Gold Coast Ingredients", "AIDP",
    ]
    return [s for s in top_suppliers if s in all_suppliers]


def build_mega_prompt(context: str, external_data: dict, user_query: str) -> str:
    """Assembles the complete prompt from all three truth sources."""
    external_str = scraper.format_for_prompt(external_data)
    return QUERY_TEMPLATE.format(
        context=context,
        external_data=external_str,
        query=user_query,
    )


def call_llm(prompt: str, system_prompt: str) -> str:
    """
    Makes a single call to the LLM with retry logic.
    Uses OpenAI GPT-4o-mini (128K context window).
    """
    client = _get_client()

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_OUTPUT_TOKENS,
            )

            text = response.choices[0].message.content
            if text and text.strip():
                return text
            raise ValueError("Empty response from LLM")

        except Exception as e:
            error_str = str(e).lower()
            error_type = type(e).__name__
            print(f"  [DEBUG] Exception type: {error_type}, message: {str(e)[:200]}")

            is_rate_limit = any(kw in error_str for kw in [
                "rate_limit", "429", "rate", "quota", "too many requests"
            ])

            if is_rate_limit:
                wait_time = (2 ** attempt) * 5
                print(f"  [WAIT] Rate limited. Retrying in {wait_time}s... (attempt {attempt + 1}/{MAX_RETRIES + 1})")
                time.sleep(wait_time)
                continue
            elif attempt < MAX_RETRIES:
                print(f"  [WARN] LLM error ({error_type}): {str(e)[:150]}. Retrying... (attempt {attempt + 1}/{MAX_RETRIES + 1})")
                time.sleep(2)
                continue
            else:
                raise RuntimeError(f"LLM API failed after {MAX_RETRIES + 1} attempts ({error_type}): {e}")

    raise RuntimeError("LLM API failed: exhausted all retries")


def parse_response(raw_response: str) -> dict:
    """
    Extracts and validates JSON from Gemini's response.
    Handles markdown code fences, partial JSON, and common formatting issues.
    """
    text = raw_response.strip()

    # Attempt 1: Direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt 2: Strip markdown code fences
    fence_pattern = r'```(?:json)?\s*\n?(.*?)\n?\s*```'
    match = re.search(fence_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Attempt 3: Find the first { ... } block
    brace_start = text.find('{')
    brace_end = text.rfind('}')
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start:brace_end + 1])
        except json.JSONDecodeError:
            pass

    # Attempt 4: Try fixing common issues (trailing commas)
    if brace_start != -1 and brace_end != -1:
        candidate = text[brace_start:brace_end + 1]
        # Remove trailing commas before } or ]
        candidate = re.sub(r',\s*([}\]])', r'\1', candidate)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # All attempts failed
    raise ValueError(
        f"Could not parse JSON from Gemini response.\n"
        f"First 500 chars: {text[:500]}"
    )


def ask_agnes(query: str, skip_scraping: bool = False) -> dict:
    """
    PUBLIC API — The single entry point for asking Agnes a question.
    Orchestrates: load → extract → scrape → prompt → call → parse.

    Args:
        query: Natural language question about the supply chain.
        skip_scraping: If True, skips the web scraping step (for faster testing).

    Returns: Structured recommendation dict.
    """
    # Step 1: Load context
    print("  [1/6] Loading supply chain context...")
    context = load_context()

    # Step 2: Extract relevant suppliers
    print("  [2/6] Identifying relevant suppliers...")
    suppliers = extract_relevant_suppliers(query, context)
    print(f"     Found {len(suppliers)} relevant suppliers: {', '.join(suppliers[:5])}{'...' if len(suppliers) > 5 else ''}")

    # Step 3: Scrape external data (conditional)
    scrape_results = {}
    if not skip_scraping and suppliers:
        print(f"  [3/6] Scraping compliance data for {len(suppliers)} suppliers...")
        scrape_results = scraper.scrape_multiple(suppliers)
        success_count = sum(1 for r in scrape_results.values() if r["status"] == "success")
        print(f"     Scraped {success_count}/{len(suppliers)} successfully")
    elif skip_scraping:
        print("  [3/6] Skipping web scraping (--fast mode)")

    # Step 4: Build prompt
    print("  [4/6] Assembling prompt for Gemini...")
    mega_prompt = build_mega_prompt(context, scrape_results, query)
    prompt_tokens_est = len(mega_prompt) // 4  # Rough estimate: 1 token ≈ 4 chars
    print(f"     Estimated prompt size: ~{prompt_tokens_est:,} tokens")

    # Step 5: Call Gemini
    print(f"  [5/6] Calling {MODEL_NAME}...")
    t_start = time.time()
    raw_response = call_llm(mega_prompt, AGNES_SYSTEM_PROMPT)
    t_elapsed = time.time() - t_start
    print(f"     Response received in {t_elapsed:.1f}s ({len(raw_response):,} chars)")

    # Step 6: Parse response
    print("  [6/6] Parsing recommendation...")
    try:
        result = parse_response(raw_response)
    except ValueError as e:
        print(f"  [ERROR] JSON parsing failed. Returning raw response.")
        result = {
            "raw_response": raw_response,
            "parse_error": str(e),
            "substitution_groups": [],
            "consolidation_summary": "Failed to parse structured response. See raw_response.",
            "overall_confidence": 0.0,
            "data_gaps": ["Response parsing failed"],
        }

    # Attach metadata
    result["query"] = query
    result["scraper_status"] = {
        name: {"status": data["status"], "certs": data.get("certifications_found", [])}
        for name, data in scrape_results.items()
    }
    result["_meta"] = {
        "model": MODEL_NAME,
        "prompt_tokens_est": prompt_tokens_est,
        "response_time_s": round(t_elapsed, 1),
        "suppliers_scraped": len(scrape_results),
    }

    return result


# ─── Quick test when run directly ───
if __name__ == "__main__":
    print("=== Agnes Core Self-Test ===\n")
    print("Testing context loading...")
    ctx = load_context()
    print(f"  Loaded {len(ctx):,} chars, {ctx.count('Company:')} company blocks\n")

    suppliers = _extract_all_suppliers(ctx)
    print(f"  {len(suppliers)} unique suppliers in dataset\n")

    print("Testing a query (fast mode, no scraping)...")
    result = ask_agnes(
        "What are the top 3 supplier consolidation opportunities?",
        skip_scraping=True
    )
    print(f"\n  Result keys: {list(result.keys())}")
    if "consolidation_summary" in result:
        print(f"  Summary: {result['consolidation_summary'][:200]}...")
    print("\n[OK] Self-test complete!")
