# scraper.py — External Compliance Data Scraper for Agnes
# Lightweight, resilient web scraper focused on extracting compliance signals.

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import warnings
import time

# ─── Session-level cache: {supplier_name: scrape_result_dict} ───
_SCRAPE_CACHE: dict = {}

# ─── User-Agent rotation pool ───
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (compatible; AgnesBot/1.0; supply-chain-research)",
]
_ua_index = 0

# ─── Known supplier URL patterns (all 40 from the dataset) ───
SUPPLIER_URLS: dict[str, str] = {
    "ADM":                              "https://www.adm.com",
    "AIDP":                             "https://www.aidp-inc.com",
    "Actus Nutrition":                  "https://actusnutrition.com",
    "American Botanicals":              "https://americanbotanicals.com",
    "Ashland":                          "https://www.ashland.com",
    "Balchem":                          "https://balchem.com",
    "BulkSupplements":                  "https://www.bulksupplements.com",
    "Cambrex":                          "https://www.cambrex.com",
    "Capsuline":                        "https://capsuline.com",
    "Cargill":                          "https://www.cargill.com",
    "Colorcon":                         "https://www.colorcon.com",
    "Custom Probiotics":                "https://www.customprobiotics.com",
    "Darling Ingredients / Rousselot":  "https://www.rousselot.com",
    "FutureCeuticals":                  "https://www.futureceuticals.com",
    "Gold Coast Ingredients":           "https://goldcoastinc.com",
    "IFF":                              "https://www.iff.com",
    "Icelandirect":                     "https://icelandirect.com",
    "Ingredion":                        "https://www.ingredion.com",
    "Jost Chemical":                    "https://www.jostchemical.com",
    "Koster Keunen":                    "https://www.kosterkeunen.com",
    "Magtein / ThreoTech LLC":          "https://www.magtein.com",
    "Makers Nutrition":                 "https://www.makersnutrition.com",
    "Mueggenburg USA":                  "https://www.mueggenburg.com",
    "Nutra Blend":                      "https://www.nutrablend.com",
    "Nutra Food Ingredients":           "https://www.nutrafoodingredients.com",
    "Nutri Avenue":                     "https://www.nutriavenue.com",
    "Prinova USA":                      "https://www.prinovagroup.com",
    "PureBulk":                         "https://purebulk.com",
    "Sawgrass Nutra Labs":              "https://www.sawgrassnutralabs.com",
    "Sensient":                         "https://www.sensient.com",
    "Source-Omega LLC":                 "https://www.source-omega.com",
    "Specialty Enzymes & Probiotics":   "https://www.specialtyenzymes.com",
    "Spectrum Chemical":                "https://www.spectrumchemical.com",
    "Stauber":                          "https://www.stauber.com",
    "Strahl & Pitsch":                  "https://www.spwax.com",
    "TCI America":                      "https://www.tcichemicals.com",
    "Trace Minerals":                   "https://www.traceminerals.com",
    "Univar Solutions":                 "https://www.univarsolutions.com",
    "Virginia Dare":                    "https://www.virginiadare.com",
    "Vitaquest":                        "https://www.vitaquest.com",
}

# ─── Compliance keywords to search for on pages ───
COMPLIANCE_SIGNALS = [
    "organic", "usda organic", "non-gmo", "non gmo", "nongmo",
    "kosher", "halal", "gluten-free", "gluten free",
    "vegan", "vegetarian", "allergen-free", "allergen free",
    "gmp", "cgmp", "fda", "iso 9001", "iso 22000",
    "nsf", "usp", "certificate", "certified",
    "soy-free", "soy free", "dairy-free", "dairy free",
    "nut-free", "nut free", "brc", "sqf", "haccp",
    "fda registered", "gras",
]

# Map raw signal keywords → clean certification labels
_SIGNAL_TO_LABEL = {
    "organic":          "Organic",
    "usda organic":     "USDA Organic",
    "non-gmo":          "Non-GMO",
    "non gmo":          "Non-GMO",
    "nongmo":           "Non-GMO",
    "kosher":           "Kosher",
    "halal":            "Halal",
    "gluten-free":      "Gluten-Free",
    "gluten free":      "Gluten-Free",
    "vegan":            "Vegan",
    "vegetarian":       "Vegetarian",
    "gmp":              "GMP",
    "cgmp":             "cGMP",
    "fda":              "FDA",
    "fda registered":   "FDA Registered",
    "iso 9001":         "ISO 9001",
    "iso 22000":        "ISO 22000",
    "nsf":              "NSF",
    "usp":              "USP",
    "brc":              "BRC",
    "sqf":              "SQF",
    "haccp":            "HACCP",
    "gras":             "GRAS",
    "soy-free":         "Soy-Free",
    "soy free":         "Soy-Free",
    "dairy-free":       "Dairy-Free",
    "dairy free":       "Dairy-Free",
    "nut-free":         "Nut-Free",
    "nut free":         "Nut-Free",
}


def _get_next_ua() -> str:
    """Rotates through user-agent strings."""
    global _ua_index
    ua = _USER_AGENTS[_ua_index % len(_USER_AGENTS)]
    _ua_index += 1
    return ua


def _fetch_page(url: str, timeout: int = 10) -> dict:
    """
    Fetches a URL with proper headers and comprehensive error handling.
    
    Returns: {"response": Response|None, "status": str, "error": str|None}
    """
    headers = {
        "User-Agent": _get_next_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        
        if resp.status_code == 200:
            return {"response": resp, "status": "success", "error": None}
        elif resp.status_code == 404:
            return {"response": None, "status": "not_found", "error": f"HTTP 404 for {url}"}
        elif resp.status_code == 403:
            # Try once more with a different UA
            headers["User-Agent"] = _get_next_ua()
            resp2 = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            if resp2.status_code == 200:
                return {"response": resp2, "status": "success", "error": None}
            return {"response": None, "status": "blocked", "error": f"HTTP 403 — bot-blocked at {url}"}
        elif resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 5))
            retry_after = min(retry_after, 10)  # Cap at 10s for hackathon speed
            time.sleep(retry_after)
            resp2 = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            if resp2.status_code == 200:
                return {"response": resp2, "status": "success", "error": None}
            return {"response": None, "status": "failed", "error": f"HTTP 429 — rate limited at {url}"}
        else:
            return {"response": None, "status": "failed", "error": f"HTTP {resp.status_code} for {url}"}
    
    except requests.exceptions.Timeout:
        return {"response": None, "status": "failed", "error": f"Timeout after {timeout}s for {url}"}
    except requests.exceptions.SSLError:
        # Retry without SSL verification
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                resp = requests.get(url, headers=headers, timeout=timeout, verify=False, allow_redirects=True)
            if resp.status_code == 200:
                return {"response": resp, "status": "success", "error": "SSL error bypassed (verify=False)"}
        except Exception:
            pass
        return {"response": None, "status": "failed", "error": f"SSL error for {url}"}
    except requests.exceptions.ConnectionError:
        return {"response": None, "status": "failed", "error": f"Connection refused by {url}"}
    except Exception as e:
        return {"response": None, "status": "failed", "error": f"Unexpected error: {str(e)[:200]}"}


def _extract_compliance_signals(soup: BeautifulSoup) -> dict:
    """
    Scans a parsed HTML page for compliance-related keywords.
    Searches: page title, meta tags, headings, paragraph text, list items.
    
    Returns: {
        "certifications_found": ["Organic", "Non-GMO", ...],
        "compliance_signals": {"organic": True, "kosher": False, ...},
        "relevant_snippet": str
    }
    """
    # Collect all searchable text
    text_parts = []
    
    # Title
    if soup.title and soup.title.string:
        text_parts.append(soup.title.string)
    
    # Meta description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        text_parts.append(meta_desc["content"])
    
    # Headings
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        if tag.string:
            text_parts.append(tag.string)
    
    # Paragraphs and list items (first 200 to avoid slowdowns on huge pages)
    for tag in soup.find_all(["p", "li", "span", "div"], limit=200):
        text = tag.get_text(strip=True)
        if text and len(text) > 5:
            text_parts.append(text)
    
    full_text = " ".join(text_parts).lower()
    
    # Scan for compliance signals
    signals = {}
    certs_found = set()
    
    for signal in COMPLIANCE_SIGNALS:
        found = signal.lower() in full_text
        signals[signal] = found
        if found and signal in _SIGNAL_TO_LABEL:
            certs_found.add(_SIGNAL_TO_LABEL[signal])
    
    # Extract a relevant snippet (find the first chunk mentioning any certification)
    snippet = ""
    for part in text_parts:
        part_lower = part.lower()
        for signal in COMPLIANCE_SIGNALS:
            if signal in part_lower:
                snippet = part[:500]
                break
        if snippet:
            break
    
    return {
        "certifications_found": sorted(list(certs_found)),
        "compliance_signals": signals,
        "relevant_snippet": snippet,
    }


def scrape_supplier(supplier_name: str) -> dict:
    """
    Scrapes a supplier's website for compliance information.
    Returns a structured dict of findings.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Check cache first
    if supplier_name in _SCRAPE_CACHE:
        return _SCRAPE_CACHE[supplier_name]
    
    # Check if we know the URL
    if supplier_name not in SUPPLIER_URLS:
        result = {
            "supplier": supplier_name,
            "url": "UNKNOWN",
            "status": "not_found",
            "certifications_found": [],
            "compliance_signals": {},
            "raw_text_snippet": "",
            "scrape_timestamp": timestamp,
            "error": f"No URL configured for supplier: {supplier_name}",
        }
        _SCRAPE_CACHE[supplier_name] = result
        return result
    
    url = SUPPLIER_URLS[supplier_name]
    
    # Fetch the page
    fetch_result = _fetch_page(url)
    
    if fetch_result["status"] != "success" or fetch_result["response"] is None:
        result = {
            "supplier": supplier_name,
            "url": url,
            "status": fetch_result["status"],
            "certifications_found": [],
            "compliance_signals": {},
            "raw_text_snippet": "",
            "scrape_timestamp": timestamp,
            "error": fetch_result["error"],
        }
        _SCRAPE_CACHE[supplier_name] = result
        return result
    
    response = fetch_result["response"]
    
    # Parse HTML
    try:
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        result = {
            "supplier": supplier_name,
            "url": url,
            "status": "failed",
            "certifications_found": [],
            "compliance_signals": {},
            "raw_text_snippet": "",
            "scrape_timestamp": timestamp,
            "error": f"HTML parse error: {str(e)[:200]}",
        }
        _SCRAPE_CACHE[supplier_name] = result
        return result
    
    # Check for empty/garbage HTML
    page_text = soup.get_text(strip=True)
    if len(page_text) < 100:
        result = {
            "supplier": supplier_name,
            "url": url,
            "status": "failed",
            "certifications_found": [],
            "compliance_signals": {},
            "raw_text_snippet": "",
            "scrape_timestamp": timestamp,
            "error": "Empty or garbage HTML (< 100 chars of text)",
        }
        _SCRAPE_CACHE[supplier_name] = result
        return result
    
    # Extract compliance signals
    signals = _extract_compliance_signals(soup)
    
    result = {
        "supplier": supplier_name,
        "url": url,
        "status": "success",
        "certifications_found": signals["certifications_found"],
        "compliance_signals": signals["compliance_signals"],
        "raw_text_snippet": signals["relevant_snippet"][:500],
        "scrape_timestamp": timestamp,
        "error": fetch_result.get("error"),  # May contain SSL warning
    }
    
    _SCRAPE_CACHE[supplier_name] = result
    return result


def scrape_multiple(supplier_names: list[str]) -> dict:
    """
    Batch scrapes multiple suppliers. Uses cache to avoid re-fetching.
    Returns: {supplier_name: scrape_result_dict, ...}
    """
    results = {}
    for name in supplier_names:
        results[name] = scrape_supplier(name)
    return results


def format_for_prompt(scrape_results: dict) -> str:
    """
    Formats scrape results into a human-readable string suitable for the LLM prompt.
    """
    if not scrape_results:
        return "No external supplier data was scraped for this query."
    
    lines = []
    for supplier_name, data in scrape_results.items():
        status = data.get("status", "unknown")
        if status == "success":
            certs = ", ".join(data.get("certifications_found", [])) or "None detected"
            snippet = data.get("raw_text_snippet", "")[:300]
            lines.append(
                f"Supplier: {supplier_name} (URL: {data.get('url', 'N/A')})\n"
                f"  Status: Scraped successfully\n"
                f"  Certifications detected: {certs}\n"
                f"  Relevant excerpt: \"{snippet}\"\n"
            )
        else:
            error = data.get("error", "Unknown error")
            lines.append(
                f"Supplier: {supplier_name} (URL: {data.get('url', 'N/A')})\n"
                f"  Status: SCRAPE FAILED — {status}\n"
                f"  Error: {error}\n"
                f"  Note: Compliance data UNVERIFIED for this supplier.\n"
            )
    
    return "\n".join(lines)


def get_cached_results() -> dict:
    """Returns the current session cache for debugging."""
    return dict(_SCRAPE_CACHE)


def clear_cache() -> None:
    """Clears the scrape cache."""
    global _SCRAPE_CACHE
    _SCRAPE_CACHE = {}


# ─── Quick test when run directly ───
if __name__ == "__main__":
    print("=== Scraper Self-Test ===\n")
    test_suppliers = ["Prinova USA", "PureBulk", "Ingredion"]
    for name in test_suppliers:
        print(f"Scraping {name}...")
        result = scrape_supplier(name)
        print(f"  Status: {result['status']}")
        print(f"  Certs:  {result['certifications_found']}")
        if result.get("error"):
            print(f"  Error:  {result['error']}")
        print()
    
    print("=== Formatted for Prompt ===")
    all_results = scrape_multiple(test_suppliers)
    print(format_for_prompt(all_results))
