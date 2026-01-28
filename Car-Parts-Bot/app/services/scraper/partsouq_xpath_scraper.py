import requests
from lxml import html
import urllib.parse
from typing import Dict, Optional
from dotenv import load_dotenv
import os
# ================= CONFIG =================
load_dotenv()

BASE_URL = "https://partsouq.com"
SCRAPER_API_BASE = "http://api.scraperapi.com"


SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )
}

# ================= SCRAPER CLASS =================

class PartSouqXPathScraper:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    # ------------------------------
    # Core fetch
    # ------------------------------
    def _fetch_xpath(self, url: str):
        payload = {
            "api_key": SCRAPER_API_KEY,
            "url": url,
            "render": "false",          # important: avoid JS rendering delays
            "keep_headers": "true",     # ensure headers are forwarded
        }

        try:
            resp = self.session.get(
                SCRAPER_API_BASE,
                params=payload,
                headers=HEADERS,         # ✅ THIS IS THE FIX
                timeout=25
            )

            if resp.status_code != 200 or not resp.content:
                print(f"[!] Failed fetch {resp.status_code}: {url}")
                return None

            return html.fromstring(resp.content)

        except Exception as e:
            print(f"[!] Network error fetching {url}: {e}")
            return None


    # ------------------------------
    # Token extraction
    # ------------------------------
    def _get_session_tokens(self, tree) -> Optional[Dict[str, str]]:
        link = tree.xpath("//a[contains(@href, 'ssd=')]/@href")
        if not link:
            return None

        parsed = urllib.parse.urlparse(link[0])
        params = urllib.parse.parse_qs(parsed.query)

        return {
            "c": params.get("c", [""])[0],
            "ssd": params.get("ssd", [""])[0],
            "vid": params.get("vid", [""])[0],
        }

    # ------------------------------
    # Table extraction
    # ------------------------------
    def _extract_parts_table(self, tree, query_words) -> list:
        rows = tree.xpath(
            "//table[contains(@class, 'table-hover') or contains(@class, 'pop-vin')]//tr[position()>1]"
        )

        results = []
        for row in rows:
            try:
                num_node = row.xpath(
                    ".//td[contains(@class, 'oem')]//a/text() | .//td[1]//a/text() | .//td[1]/text()"
                )
                name_node = row.xpath(".//td[2]/text()")

                if not num_node or not name_node:
                    continue

                num = num_node[0].strip()
                name = name_node[0].strip()

                if not any(c.isdigit() for c in num):
                    continue

                name_lower = name.lower()
                query_combined = "".join(query_words)

                if (
                    query_combined in name_lower
                    or any(q in name_lower for q in query_words)
                ):
                    results.append({
                        "number": num,
                        "name": name
                    })
            except Exception:
                continue

        return results

    # ------------------------------
    # Strategy 1: Category Tree
    # ------------------------------
    def _search_groups(self, tokens, vin, part_name) -> list:
        groups_url = (
            f"{BASE_URL}/en/catalog/genuine/groups?"
            f"c={tokens['c']}&"
            f"ssd={urllib.parse.quote(tokens['ssd'])}&"
            f"vid={tokens['vid']}&"
            f"q={vin}"
        )

        tree = self._fetch_xpath(groups_url)
        if tree is None:
            return []

        keywords = part_name.lower().split()
        links = tree.xpath("//table[contains(@class, 'tree')]//td//a")

        for link in links:
            cat_name = link.text_content().strip().lower()
            if all(k in cat_name for k in keywords):
                href = link.get("href")
                if not href:
                    continue

                diag_tree = self._fetch_xpath(BASE_URL + href)
                if diag_tree is not None:
                    results = self._extract_parts_table(diag_tree, keywords)
                    if results:
                        return results

        return []

    # ------------------------------
    # Strategy 2: Deep Search (CRITICAL)
    # ------------------------------
    def _search_deep(self, tokens, part_name) -> list:
        keywords = part_name.lower().split()
        q = urllib.parse.quote(part_name)

        search_url = (
            f"{BASE_URL}/en/catalog/genuine/search?"
            f"s={q}&"
            f"c={tokens['c']}&"
            f"ssd={urllib.parse.quote(tokens['ssd'])}&"
            f"vid={tokens['vid']}&"
            f"gid=&cid=&"
            f"q={q}"
        )

        tree = self._fetch_xpath(search_url)
        if tree is None:
            return []

        # Direct table
        results = self._extract_parts_table(tree, keywords)
        if results:
            return results

        # Fallback: diagrams
        links = tree.xpath(
            "(//div[@class='caption']//a | //td//a[contains(@href, 'gid=')])[position() <= 3]"
        )

        for link in links:
            href = link.get("href")
            if not href:
                continue

            diag_tree = self._fetch_xpath(BASE_URL + href)
            if len(diag_tree) > 0:
                results = self._extract_parts_table(diag_tree, keywords)
                if results:
                    return results

        return []

    #Get Vehicle Details
    def get_vehicle_details(self, vin: str) -> Optional[Dict[str, str]]:
        """
        Fetches vehicle metadata (Brand, Name, Model, Date) from the search page.
        """
        search_url = f"{BASE_URL}/search?q={vin}"
        tree = self._fetch_xpath(search_url)

        if tree is None:
            return None

        try:
            def _safe_text(xpath_query):
                nodes = tree.xpath(xpath_query)
                return nodes[0].text_content().strip() if nodes else "N/A"

            brand = _safe_text("//td[@data-title='Brand']")
            name = _safe_text("//td[@data-title='Name']")
            # model = _safe_text("//td[@data-title='Model']")

            # Date can sometimes be 'Date' or 'Vehicle Date'
            date = _safe_text("//td[@data-title='Date'] | //td[@data-title='Vehicle Date'] | //td[@data-title='Manufactured']")

            return {
                "brand": brand,
                "name": name,
                # "model": model,
                "date": date
            }
        except Exception as e:
            print(f"[!] Error extracting vehicle details: {e}")
            return None

    # ------------------------------
    # PUBLIC API (THIS IS WHAT YOU CALL)
    # ------------------------------
    def search_part(self, vin: str, part_name: str) -> Dict:
        tree_init = self._fetch_xpath(f"{BASE_URL}/search?q={vin}")
        if tree_init is None:

            return {"error": "VIN search failed"}

        tokens = self._get_session_tokens(tree_init)
        if not tokens:
            return {"error": "Session token extraction failed"}

        # Strategy 1
        results = self._search_groups(tokens, vin, part_name)
        if results:
            return {
                "vin": vin,
                "query": part_name,
                "parts": results
            }

        # Strategy 2
        results = self._search_deep(tokens, part_name)
        if results:
            return {
                "vin": vin,
                "query": part_name,
                "parts": results
            }

        return {"error": "Part not found"}

# ================= SINGLETON =================

_scraper: Optional[PartSouqXPathScraper] = None

def get_scraper() -> PartSouqXPathScraper:
    global _scraper
    if _scraper is None:
        _scraper = PartSouqXPathScraper()
    return _scraper
