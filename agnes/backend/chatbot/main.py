# main.py — Agnes Chatbot CLI entry point.
# Replaces the legacy root-level main.py.
# Run from the repo root: python agnes/backend/chatbot/main.py

import sys
import json
import agnes_core

try:
    from colorama import init, Fore, Style
    init()
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    class _Stub:
        def __getattr__(self, name):
            return ""
    Fore = _Stub()
    Style = _Stub()


DEMO_QUERIES = [
    "Identify the top 5 raw material consolidation opportunities across all companies. Focus on ingredients used by the most companies.",
    "Which raw materials have single-source risk (only 1 approved supplier)? List the top 10 highest-risk ones.",
    "Can Prinova USA replace PureBulk for all vitamin-related raw materials? Analyze compliance implications.",
]


def print_banner():
    banner = f"""
{Fore.CYAN}+==============================================================+
|                                                              |
|      A   GGGG  N   N  EEEE  SSSS                             |
|     A A  G     NN  N  E     S                                |
|    AAAAA G GGG N N N  EEE    SSS                             |
|    A   A G   G N  NN  E        S                             |
|    A   A  GGG  N   N  EEEE SSSS                              |
|                                                              |
|    AI Supply Chain Manager -- Spherecast Makeathon 2026      |
|                                                              |
+==============================================================+{Style.RESET_ALL}

{Fore.YELLOW}Commands:{Style.RESET_ALL}
  Type your question and press Enter
  {Fore.GREEN}/demo{Style.RESET_ALL}      -- Run 3 pre-built demo queries
  {Fore.GREEN}/rebuild{Style.RESET_ALL}   -- Rebuild the Phase 4 retrieval index from DB
  {Fore.GREEN}/help{Style.RESET_ALL}      -- Show this help
  {Fore.GREEN}/quit{Style.RESET_ALL}      -- Exit Agnes
"""
    print(banner)


def display_recommendation(result: dict) -> None:
    """Pretty-prints a structured recommendation to the terminal."""

    if "raw_response" in result and "parse_error" in result:
        print(f"\n{Fore.RED}[WARN] Could not parse structured JSON. Raw response:{Style.RESET_ALL}")
        print(result["raw_response"][:2000])
        return

    overall_conf = result.get("overall_confidence", 0)
    # Normalize: LLM sometimes copies the 0-100 backend value verbatim instead of 0-1
    if overall_conf > 1:
        overall_conf = overall_conf / 100
    conf_color = Fore.GREEN if overall_conf >= 0.7 else Fore.YELLOW if overall_conf >= 0.4 else Fore.RED

    print(f"\n{Fore.CYAN}{'=' * 70}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}  AGNES RECOMMENDATION{Style.RESET_ALL}  |  Confidence: {conf_color}{overall_conf:.0%}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'=' * 70}{Style.RESET_ALL}")

    summary = result.get("consolidation_summary", "No summary available.")
    print(f"\n{Fore.WHITE}[SUMMARY]{Style.RESET_ALL}")
    print(f"   {summary}")

    groups = result.get("substitution_groups", [])
    if groups:
        print(f"\n{Fore.WHITE}SUBSTITUTION GROUPS ({len(groups)} found){Style.RESET_ALL}")
        for i, group in enumerate(groups, 1):
            conf = group.get("confidence_score", 0)
            # Normalize: LLM sometimes copies the 0-100 backend value verbatim instead of 0-1
            if conf > 1:
                conf = conf / 100
            conf_color = Fore.GREEN if conf >= 0.7 else Fore.YELLOW if conf >= 0.4 else Fore.RED

            print(f"\n  {Fore.CYAN}--- Group {i}: {group.get('canonical_ingredient', 'Unknown')} ---{Style.RESET_ALL}")
            print(f"  Confidence: {conf_color}{conf:.0%}{Style.RESET_ALL}")

            companies = group.get("companies_using", [])
            if companies:
                print(f"  Companies:  {', '.join(companies[:8])}{'...' if len(companies) > 8 else ''} ({len(companies)} total)")

            products = group.get("products_affected", [])
            if products:
                print(f"  Products:   {len(products)} affected")

            current = group.get("current_suppliers", [])
            if current:
                print(f"  Current:    {', '.join(current)}")

            recommended = group.get("recommended_supplier", "")
            if recommended:
                print(f"  {Fore.GREEN}Recommend:  -> {recommended}{Style.RESET_ALL}")

            reasoning = group.get("reasoning", "")
            if reasoning:
                print(f"  Reasoning:  {reasoning[:200]}{'...' if len(reasoning) > 200 else ''}")

            impact = group.get("estimated_impact", "")
            if impact:
                print(f"  {Fore.YELLOW}Impact:     {impact}{Style.RESET_ALL}")

            evidence = group.get("evidence", [])
            if evidence:
                print(f"  Evidence:")
                for e in evidence[:5]:
                    if isinstance(e, dict):
                        snippet = e.get("snippet", "")
                        src     = e.get("source_id", "")
                        print(f"    [{src}] {snippet[:120]}")
                    else:
                        print(f"    - {e}")

            risks = group.get("risks", [])
            if risks:
                print(f"  {Fore.RED}Risks:{Style.RESET_ALL}")
                for r in risks:
                    if isinstance(r, dict):
                        print(f"    {Fore.RED}[!] {r.get('factor', 'Unknown Risk')}{Style.RESET_ALL}")
                        impact = r.get("impact", "")
                        if impact:
                            print(f"        Impact:     {impact}")
                        mitigation = r.get("mitigation", "")
                        if mitigation:
                            print(f"        Mitigation: {Fore.YELLOW}{mitigation}{Style.RESET_ALL}")
                    else:
                        print(f"    {Fore.RED}[!] {r}{Style.RESET_ALL}")

    gaps = result.get("data_gaps", [])
    if gaps:
        print(f"\n{Fore.YELLOW}DATA GAPS{Style.RESET_ALL}")
        for gap in gaps:
            print(f"   - {gap}")

    meta = result.get("_meta", {})
    if meta:
        fallback = " | fallback-scrape" if meta.get("fallback_scrape_triggered") else ""
        print(
            f"\n{Fore.WHITE}Model: {meta.get('model', '?')} | "
            f"Retrieved: {meta.get('proposals_retrieved', 0)} proposals, "
            f"{meta.get('evidence_retrieved', 0)} evidence | "
            f"Backend: {meta.get('index_backend', '?')}{fallback} | "
            f"Prompt: ~{meta.get('prompt_tokens_est', 0):,} tokens | "
            f"Time: {meta.get('response_time_s', 0)}s{Style.RESET_ALL}"
        )

    print(f"\n{Fore.CYAN}{'=' * 70}{Style.RESET_ALL}\n")


def run_demo():
    print(f"\n{Fore.YELLOW}Running Agnes Demo (3 queries)...{Style.RESET_ALL}\n")
    for i, query in enumerate(DEMO_QUERIES, 1):
        print(f"{Fore.CYAN}--- Demo Query {i}/3 ---{Style.RESET_ALL}")
        print(f"  \"{query}\"\n")
        try:
            result = agnes_core.ask_agnes(query)
            display_recommendation(result)
        except Exception as e:
            print(f"{Fore.RED}  [ERROR] {e}{Style.RESET_ALL}\n")


def main():
    print_banner()

    # Pre-load the Phase 4 index at startup
    try:
        print(f"{Fore.YELLOW}Loading Phase 4 retrieval index...{Style.RESET_ALL}")
        agnes_core._get_index()
        print(f"{Fore.GREEN}[OK] Index ready{Style.RESET_ALL}\n")
    except RuntimeError as e:
        print(f"{Fore.RED}[ERROR] {e}{Style.RESET_ALL}")
        sys.exit(1)

    if "--demo" in sys.argv:
        run_demo()
        return

    while True:
        try:
            query = input(f"{Fore.GREEN}Agnes> {Style.RESET_ALL}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Fore.CYAN}Goodbye!{Style.RESET_ALL}")
            break

        if not query:
            continue

        if query.lower() in ("/quit", "/exit", "/q"):
            print(f"{Fore.CYAN}Goodbye!{Style.RESET_ALL}")
            break
        elif query.lower() == "/help":
            print_banner()
            continue
        elif query.lower() == "/demo":
            run_demo()
            continue
        elif query.lower() == "/rebuild":
            print(f"{Fore.YELLOW}  Rebuilding Phase 4 index from database...{Style.RESET_ALL}")
            agnes_core._INDEX = None
            try:
                agnes_core._get_index(force_rebuild=True)
                print(f"{Fore.GREEN}  [OK] Index rebuilt.{Style.RESET_ALL}\n")
            except RuntimeError as e:
                print(f"{Fore.RED}  [ERROR] {e}{Style.RESET_ALL}\n")
            continue

        print()
        try:
            result = agnes_core.ask_agnes(query)
            display_recommendation(result)
        except Exception as e:
            print(f"{Fore.RED}  [ERROR] {e}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
