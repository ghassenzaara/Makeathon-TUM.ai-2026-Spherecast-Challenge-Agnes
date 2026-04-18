# main.py -- Agnes CLI Entry Point
# Interactive command-line interface for the Agnes AI Supply Chain Manager.

import sys
import json
import agnes_core

try:
    from colorama import init, Fore, Style
    init()
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    # Stub out colorama if not installed
    class _Stub:
        def __getattr__(self, name):
            return ""
    Fore = _Stub()
    Style = _Stub()


# --- Demo queries ---
DEMO_QUERIES = [
    "Identify the top 5 raw material consolidation opportunities across all companies. Focus on ingredients used by the most companies.",
    "Which raw materials have single-source risk (only 1 approved supplier)? List the top 10 highest-risk ones.",
    "Can Prinova USA replace PureBulk for all vitamin-related raw materials? Analyze compliance implications.",
]


def print_banner():
    """Prints the Agnes startup banner."""
    banner = f"""
{Fore.CYAN}+==============================================================+
|                                                              |
|      A   GGGG  N   N  EEEE  SSSS                            |
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
  {Fore.GREEN}/demo{Style.RESET_ALL}     -- Run 3 pre-built demo queries
  {Fore.GREEN}/fast{Style.RESET_ALL}     -- Toggle fast mode (skip web scraping)
  {Fore.GREEN}/scrape{Style.RESET_ALL}   -- Toggle web scraping on/off
  {Fore.GREEN}/help{Style.RESET_ALL}     -- Show this help
  {Fore.GREEN}/quit{Style.RESET_ALL}     -- Exit Agnes
"""
    print(banner)


def display_recommendation(result: dict) -> None:
    """Pretty-prints a structured recommendation to the terminal."""

    # Check for parse failure
    if "raw_response" in result and "parse_error" in result:
        print(f"\n{Fore.RED}[WARN] Could not parse structured JSON. Raw response:{Style.RESET_ALL}")
        print(result["raw_response"][:2000])
        return

    # -- Header --
    overall_conf = result.get("overall_confidence", 0)
    conf_color = Fore.GREEN if overall_conf >= 0.7 else Fore.YELLOW if overall_conf >= 0.4 else Fore.RED
    print(f"\n{Fore.CYAN}{'=' * 70}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}  AGNES RECOMMENDATION{Style.RESET_ALL}  |  Confidence: {conf_color}{overall_conf:.0%}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'=' * 70}{Style.RESET_ALL}")

    # -- Executive Summary --
    summary = result.get("consolidation_summary", "No summary available.")
    print(f"\n{Fore.WHITE}[SUMMARY]{Style.RESET_ALL}")
    print(f"   {summary}")

    # -- Substitution Groups --
    groups = result.get("substitution_groups", [])
    if groups:
        print(f"\n{Fore.WHITE}SUBSTITUTION GROUPS ({len(groups)} found){Style.RESET_ALL}")
        for i, group in enumerate(groups, 1):
            conf = group.get("confidence_score", 0)
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

            # Evidence
            evidence = group.get("evidence", [])
            if evidence:
                print(f"  Evidence:")
                for e in evidence[:5]:
                    print(f"    - {e}")

            # Risks
            risks = group.get("risks", [])
            if risks:
                print(f"  {Fore.RED}Risks:{Style.RESET_ALL}")
                for r in risks:
                    print(f"    [!] {r}")

    # -- Data Gaps --
    gaps = result.get("data_gaps", [])
    if gaps:
        print(f"\n{Fore.YELLOW}DATA GAPS{Style.RESET_ALL}")
        for gap in gaps:
            print(f"   - {gap}")

    # -- Scraper Status --
    scraper_status = result.get("scraper_status", {})
    if scraper_status:
        success = sum(1 for s in scraper_status.values() if s.get("status") == "success")
        total = len(scraper_status)
        print(f"\n{Fore.WHITE}SCRAPER: {success}/{total} suppliers scraped successfully{Style.RESET_ALL}")

    # -- Meta --
    meta = result.get("_meta", {})
    if meta:
        print(f"\n{Fore.WHITE}Model: {meta.get('model', '?')} | "
              f"Prompt: ~{meta.get('prompt_tokens_est', 0):,} tokens | "
              f"Time: {meta.get('response_time_s', 0)}s{Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}{'=' * 70}{Style.RESET_ALL}\n")


def run_demo(skip_scraping: bool):
    """Runs the 3 canned demo queries."""
    print(f"\n{Fore.YELLOW}Running Agnes Demo (3 queries)...{Style.RESET_ALL}\n")
    for i, query in enumerate(DEMO_QUERIES, 1):
        print(f"{Fore.CYAN}--- Demo Query {i}/3 ---{Style.RESET_ALL}")
        print(f"  \"{query}\"\n")
        try:
            result = agnes_core.ask_agnes(query, skip_scraping=skip_scraping)
            display_recommendation(result)
        except Exception as e:
            print(f"{Fore.RED}  [ERROR] {e}{Style.RESET_ALL}\n")


def main():
    """Interactive CLI loop for Agnes."""
    print_banner()

    # Pre-load context at startup
    try:
        print(f"{Fore.YELLOW}Loading supply chain data...{Style.RESET_ALL}")
        ctx = agnes_core.load_context()
        company_count = ctx.count("Company:")
        print(f"{Fore.GREEN}[OK] Loaded {len(ctx):,} chars ({company_count} product profiles){Style.RESET_ALL}\n")
    except (FileNotFoundError, ValueError) as e:
        print(f"{Fore.RED}[ERROR] {e}{Style.RESET_ALL}")
        sys.exit(1)

    skip_scraping = False

    # Check for --demo or --fast CLI flags
    if "--demo" in sys.argv:
        skip_scraping = "--fast" in sys.argv
        run_demo(skip_scraping)
        return

    if "--fast" in sys.argv:
        skip_scraping = True
        print(f"{Fore.YELLOW}Fast mode: web scraping disabled{Style.RESET_ALL}\n")

    # Interactive loop
    while True:
        try:
            query = input(f"{Fore.GREEN}Agnes> {Style.RESET_ALL}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Fore.CYAN}Goodbye!{Style.RESET_ALL}")
            break

        if not query:
            continue

        # Handle commands
        if query.lower() in ("/quit", "/exit", "/q"):
            print(f"{Fore.CYAN}Goodbye!{Style.RESET_ALL}")
            break
        elif query.lower() == "/help":
            print_banner()
            continue
        elif query.lower() == "/demo":
            run_demo(skip_scraping)
            continue
        elif query.lower() in ("/fast", "/scrape"):
            skip_scraping = not skip_scraping
            status = "OFF (fast mode)" if skip_scraping else "ON"
            print(f"{Fore.YELLOW}  Web scraping: {status}{Style.RESET_ALL}\n")
            continue
        elif query.lower() == "/cache":
            import scraper as s
            cache = s.get_cached_results()
            print(f"  Cached scrape results: {len(cache)} suppliers")
            for name, data in cache.items():
                print(f"    {name}: {data['status']} -- {data.get('certifications_found', [])}")
            print()
            continue

        # Process the query
        print()
        try:
            result = agnes_core.ask_agnes(query, skip_scraping=skip_scraping)
            display_recommendation(result)
        except Exception as e:
            print(f"{Fore.RED}  [ERROR] {e}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
