# import requests
# from lxml import html
# import urllib.parse
# from typing import Dict, Optional
# from dotenv import load_dotenv
# import os
# # ================= CONFIG =================
# load_dotenv()

# BASE_URL = "https://partsouq.com"
# SCRAPER_API_BASE = "http://api.scraperapi.com"


# SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY")

# HEADERS = {
#     "User-Agent": (
#         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#         "AppleWebKit/537.36 (KHTML, like Gecko) "
#         "Chrome/91.0.4472.124 Safari/537.36"
#     )
# }

# # ================= SCRAPER CLASS =================

# class PartSouqXPathScraper:

#     def __init__(self):
#         self.session = requests.Session()
#         self.session.headers.update(HEADERS)

#     # ------------------------------
#     # Core fetch
#     # ------------------------------
#     def _fetch_xpath(self, url: str):
#         payload = {
#             "api_key": SCRAPER_API_KEY,
#             "url": url,
#             "render": "false",          # important: avoid JS rendering delays
#             "keep_headers": "true",     # ensure headers are forwarded
#         }

#         try:
#             resp = self.session.get(
#                 SCRAPER_API_BASE,
#                 params=payload,
#                 headers=HEADERS,         # ✅ THIS IS THE FIX
#                 timeout=25
#             )

#             if resp.status_code != 200 or not resp.content:
#                 print(f"[!] Failed fetch {resp.status_code}: {url}")
#                 return None

#             return html.fromstring(resp.content)

#         except Exception as e:
#             print(f"[!] Network error fetching {url}: {e}")
#             return None


#     # ------------------------------
#     # Token extraction
#     # ------------------------------
#     def _get_session_tokens(self, tree) -> Optional[Dict[str, str]]:
#         link = tree.xpath("//a[contains(@href, 'ssd=')]/@href")
#         if not link:
#             return None

#         parsed = urllib.parse.urlparse(link[0])
#         params = urllib.parse.parse_qs(parsed.query)

#         return {
#             "c": params.get("c", [""])[0],
#             "ssd": params.get("ssd", [""])[0],
#             "vid": params.get("vid", [""])[0],
#         }

#     # ------------------------------
#     # Table extraction
#     # ------------------------------
#     def _extract_parts_table(self, tree, query_words) -> list:
#         rows = tree.xpath(
#             "//table[contains(@class, 'table-hover') or contains(@class, 'pop-vin')]//tr[position()>1]"
#         )

#         results = []
#         for row in rows:
#             try:
#                 num_node = row.xpath(
#                     ".//td[contains(@class, 'oem')]//a/text() | .//td[1]//a/text() | .//td[1]/text()"
#                 )
#                 name_node = row.xpath(".//td[2]/text()")

#                 if not num_node or not name_node:
#                     continue

#                 num = num_node[0].strip()
#                 name = name_node[0].strip()

#                 if not any(c.isdigit() for c in num):
#                     continue

#                 name_lower = name.lower()
#                 query_combined = "".join(query_words)

#                 if (
#                     query_combined in name_lower
#                     or any(q in name_lower for q in query_words)
#                 ):
#                     results.append({
#                         "number": num,
#                         "name": name
#                     })
#             except Exception:
#                 continue

#         return results

#     # ------------------------------
#     # Strategy 1: Category Tree
#     # ------------------------------
#     def _search_groups(self, tokens, vin, part_name) -> list:
#         groups_url = (
#             f"{BASE_URL}/en/catalog/genuine/groups?"
#             f"c={tokens['c']}&"
#             f"ssd={urllib.parse.quote(tokens['ssd'])}&"
#             f"vid={tokens['vid']}&"
#             f"q={vin}"
#         )

#         tree = self._fetch_xpath(groups_url)
#         if tree is None:
#             return []

#         keywords = part_name.lower().split()
#         links = tree.xpath("//table[contains(@class, 'tree')]//td//a")

#         for link in links:
#             cat_name = link.text_content().strip().lower()
#             if all(k in cat_name for k in keywords):
#                 href = link.get("href")
#                 if not href:
#                     continue

#                 diag_tree = self._fetch_xpath(BASE_URL + href)
#                 if diag_tree is not None:
#                     results = self._extract_parts_table(diag_tree, keywords)
#                     if results:
#                         return results

#         return []

#     # ------------------------------
#     # Strategy 2: Deep Search (CRITICAL)
#     # ------------------------------
#     def _search_deep(self, tokens, part_name) -> list:
#         keywords = part_name.lower().split()
#         q = urllib.parse.quote(part_name)

#         search_url = (
#             f"{BASE_URL}/en/catalog/genuine/search?"
#             f"s={q}&"
#             f"c={tokens['c']}&"
#             f"ssd={urllib.parse.quote(tokens['ssd'])}&"
#             f"vid={tokens['vid']}&"
#             f"gid=&cid=&"
#             f"q={q}"
#         )

#         tree = self._fetch_xpath(search_url)
#         if tree is None:
#             return []

#         # Direct table
#         results = self._extract_parts_table(tree, keywords)
#         if results:
#             return results

#         # Fallback: diagrams
#         links = tree.xpath(
#             "(//div[@class='caption']//a | //td//a[contains(@href, 'gid=')])[position() <= 3]"
#         )

#         for link in links:
#             href = link.get("href")
#             if not href:
#                 continue

#             diag_tree = self._fetch_xpath(BASE_URL + href)
#             if len(diag_tree) > 0:
#                 results = self._extract_parts_table(diag_tree, keywords)
#                 if results:
#                     return results

#         return []

#     #Get Vehicle Details
#     def get_vehicle_details(self, vin: str) -> Optional[Dict[str, str]]:
#         """
#         Fetches vehicle metadata (Brand, Name, Model, Date) from the search page.
#         """
#         search_url = f"{BASE_URL}/search?q={vin}"
#         tree = self._fetch_xpath(search_url)

#         if tree is None:
#             return None

#         try:
#             def _safe_text(xpath_query):
#                 nodes = tree.xpath(xpath_query)
#                 return nodes[0].text_content().strip() if nodes else "N/A"

#             brand = _safe_text("//td[@data-title='Brand']")
#             name = _safe_text("//td[@data-title='Name']")
#             # model = _safe_text("//td[@data-title='Model']")

#             # Date can sometimes be 'Date' or 'Vehicle Date'
#             date = _safe_text("//td[@data-title='Date'] | //td[@data-title='Vehicle Date'] | //td[@data-title='Manufactured']")

#             return {
#                 "brand": brand,
#                 "name": name,
#                 # "model": model,
#                 "date": date
#             }
#         except Exception as e:
#             print(f"[!] Error extracting vehicle details: {e}")
#             return None

#     # ------------------------------
#     # PUBLIC API (THIS IS WHAT YOU CALL)
#     # ------------------------------
#     def search_part(self, vin: str, part_name: str) -> Dict:
#         tree_init = self._fetch_xpath(f"{BASE_URL}/search?q={vin}")
#         if tree_init is None:

#             return {"error": "VIN search failed"}

#         tokens = self._get_session_tokens(tree_init)
#         if not tokens:
#             return {"error": "Session token extraction failed"}

#         # Strategy 1
#         results = self._search_groups(tokens, vin, part_name)
#         if results:
#             return {
#                 "vin": vin,
#                 "query": part_name,
#                 "parts": results
#             }

#         # Strategy 2
#         results = self._search_deep(tokens, part_name)
#         if results:
#             return {
#                 "vin": vin,
#                 "query": part_name,
#                 "parts": results
#             }

#         return {"error": "Part not found"}

# # ================= SINGLETON =================

# _scraper: Optional[PartSouqXPathScraper] = None

# def get_scraper() -> PartSouqXPathScraper:
#     global _scraper
#     if _scraper is None:
#         _scraper = PartSouqXPathScraper()
#     return _scraper
import requests
from lxml import html
import urllib.parse
from typing import Dict, Optional, List
from dotenv import load_dotenv
import os
import time

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

    def __init__(self, max_retries: int = 5, retry_delay: int = 2):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.base_url = BASE_URL # Store base URL for consistency
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    # ------------------------------
    # Core fetch
    # ------------------------------
    # def _fetch_xpath(self, url: str):
    #     payload = {
    #         "api_key": SCRAPER_API_KEY,
    #         "url": url,
    #         "render": "false",
    #         "keep_headers": "true",
    #     }

    #     try:
    #         print(f"[*] Fetching: {url} ...")
    #         resp = self.session.get(
    #             SCRAPER_API_BASE,
    #             params=payload,
    #             headers=HEADERS,
    #             timeout=60
    #         )

    #         if resp.status_code != 200 or not resp.content:
    #             print(f"[!] Failed fetch {resp.status_code}: {url}")
    #             return None

    #         return html.fromstring(resp.content)

    #     except Exception as e:
    #         print(f"[!] Network error fetching {url}: {e}")
    #         return None

    def _fetch_xpath(self, url: str):
        payload = {
            "api_key": SCRAPER_API_KEY,
            "url": url,
            "render": "false",
            "keep_headers": "true",
        }
        for attempt in range(1, self.max_retries + 1):
            try:
                print(f"[*] Fetching (Attempt {attempt}/{self.max_retries}): {url}")
                resp = self.session.get(
                    SCRAPER_API_BASE,
                    params=payload,
                    headers=HEADERS,
                    timeout=60
                )
                if resp.status_code == 200 and resp.content:
                    return html.fromstring(resp.content)
                print(f"[!] Failed fetch {resp.status_code} on attempt {attempt}")
            except Exception as e:
                print(f"[!] Network error on attempt {attempt}: {e}")
            if attempt < self.max_retries:
                time.sleep(self.retry_delay)
        print(f"[!] All {self.max_retries} attempts failed for: {url}")
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
    # Vehicle Details Extraction
    # ------------------------------
    def get_vehicle_details(self, vin: str) -> Optional[Dict[str, str]]:
        search_url = f"{self.base_url}/en/search/all?q={vin}"
        tree = self._fetch_xpath(search_url)
        
        if tree is None: 
            return None

        try:
            def _safe_text(xpath_query):
                nodes = tree.xpath(xpath_query)
                return nodes[0].text_content().strip() if nodes else "N/A"

            brand = _safe_text("//td[@data-title='Brand']")
            name  = _safe_text("//td[@data-title='Name']")
            model = _safe_text("//td[@data-title='Model']")
            date = _safe_text("//td[@data-title='Date'] | //td[@data-title='Vehicle Date'] | //td[@data-title='Manufactured']")

            return {
                "brand": brand,
                "name": name,
                "model": model,
                "date": date
            }
        except Exception as e:
            print(f"[!] Error extracting vehicle details: {e}")
            return None

    # ------------------------------
    # Grouped Parts Extraction (The Logic from your new script)
    # ------------------------------
    def _extract_grouped_parts(self, tree) -> List[Dict]:
        """
        Scans the page for 'Unit Blocks' to group parts by their diagram title.
        Matches the logic of finding ALL parts in search results.
        """
        grouped_results = []
        
        # 1. Find all "Unit" containers
        # On search pages: 'unit-with-sr'
        # On catalog pages: often just 'col-md-4' or specific containers.
        # We try to be generic or specific depending on the context.
        # The user provided code uses `unit-with-sr`.
        unit_blocks = tree.xpath("//div[contains(@class, 'unit-with-sr')]")
        if not unit_blocks:
             # Fallback for catalog pages (if they differ? usually catalog pages just have links, not expanded parts)
             pass
             
        print(f"   (Found {len(unit_blocks)} unit diagrams)")

        for block in unit_blocks:
            # 2. Extract Unit Title
            title_node = block.xpath(".//div[@class='caption']//h5//a/text()")
            if not title_node:
                title_node = block.xpath(".//h3/text()")
            
            unit_title = title_node[0].strip() if title_node else "Unknown Unit"
            
            # 3. Extract Parts Table
            rows = block.xpath(".//table//tr[position()>1]") # Skip header
            
            unit_parts = []
            for row in rows:
                try:
                    cols = row.xpath(".//td")
                    # Expecting [Icon, Number, Name, Code] (4 cols) or similar
                    if len(cols) < 4: continue
                    
                    # Col 1: Number
                    part_num = cols[1].text_content().strip()
                    # Col 2: Name
                    part_name = cols[2].text_content().strip()
                    # Col 3: Code
                    part_code = cols[3].text_content().strip()

                    # Basic Validation
                    if not any(c.isdigit() for c in part_num): continue

                    # Clean up name (remove extra spaces)
                    clean_name = " ".join(part_name.split())

                    unit_parts.append({
                        "number": part_num,
                        "name": clean_name,
                        "code": part_code
                    })
                except:
                    continue
            
            if unit_parts:
                grouped_results.append({
                    "title": unit_title,
                    "parts": unit_parts
                })

        return grouped_results

    # ------------------------------
    # Main Search Function (Updated to use deep search by default)
    # ------------------------------
    def search_part(self, vin: str, part_name: str) -> Dict:
        # 1. Init Session
        tree_init = self._fetch_xpath(f"{self.base_url}/en/search/all?q={vin}")
        if tree_init is None:
            return {"error": "VIN search failed"}

        tokens = self._get_session_tokens(tree_init)
        if not tokens:
            return {"error": "Session token extraction failed"}

        # 2. Construct Deep Search URL (using 's=' parameter)
        q_encoded = urllib.parse.quote(part_name)
        search_url = (
            f"{self.base_url}/en/catalog/genuine/search?"
            f"s={q_encoded}&"  # The actual search string
            f"c={tokens['c']}&"
            f"ssd={urllib.parse.quote(tokens['ssd'])}&"
            f"vid={tokens['vid']}&"
            f"gid=&cid=&"
            f"q={q_encoded}"
        )

        tree_search = self._fetch_xpath(search_url)
        if tree_search is None:
             return {"error": "Search failed"}

        # 3. Extract Results
        grouped_results = self._extract_grouped_parts(tree_search)
        
        # Flatten for compatibility with message_processor
        all_parts = []
        for group in grouped_results:
            group_title = group.get("title", "")
            for p in group.get("parts", []):
                # Store category context separately for GPT filtering
                if group_title:
                   p["category"] = group_title
                all_parts.append(p)
        
        if all_parts:
            return {
                "vin": vin,
                "query": part_name,
                "parts": all_parts
            }

        return {"error": "Part not found"}

    # ------------------------------
    # Catalog Crawling / Full Scrape
    # ------------------------------
    def get_all_parts(self, vin: str) -> Dict:
        """
        Crawls the entire catalog for a VIN:
        1. Search VIN to get session tokens.
        2. Get Top Level Groups (Engine, Body, etc.).
        3. For each group, get Subgroups/Units.
        4. For each Unit, extract all parts.
        """
        print(f"[*] Starting full crawl for VIN: {vin}")
        
        # 1. Init Session
        tree_init = self._fetch_xpath(f"{self.base_url}/en/search/all?q={vin}")
        if tree_init is None:
            return {"error": "VIN search failed"}

        tokens = self._get_session_tokens(tree_init)
        if not tokens:
            return {"error": "Session token extraction failed"}

        # 2. Get Top Level Groups
        groups = self._get_catalog_groups(tokens, vin)
        print(f"[*] Found {len(groups)} top-level groups.")

        full_catalog = {}

        for grp_name, grp_url in groups.items():
            print(f"   -> Crawling Group: {grp_name}...")
            group_data = []
            
            # 3. Get Units in Group
            units = self._get_units_in_group(grp_url)
            print(f"      Found {len(units)} units in {grp_name}.")

            for unit_name, unit_url in units.items():
                print(f"      -> Fetching parts for unit: {unit_name}")
                parts = self._fetch_parts_from_unit_page(unit_url)
                if parts:
                    group_data.append({
                        "unit_name": unit_name,
                        "url": unit_url,
                        "parts": parts
                    })
                # Be nice to the server (even with ScraperAPI)
                # time.sleep(0.5) 

            full_catalog[grp_name] = group_data
            
        return {
            "vin": vin,
            "catalog": full_catalog
        }

    def _get_catalog_groups(self, tokens: Dict, vin: str) -> Dict[str, str]:
        """
        Returns { "Engine": "url", "Body": "url", ... }
        """
        groups_url = (
            f"{self.base_url}/en/catalog/genuine/groups?"
            f"c={tokens['c']}&"
            f"ssd={urllib.parse.quote(tokens['ssd'])}&"
            f"vid={tokens['vid']}&"
            f"q={vin}"
        )
        
        tree = self._fetch_xpath(groups_url)
        if tree is None:
            return {}

        groups = {}
        # Select all links in the tree table
        links = tree.xpath("//div[@class='catalog-groups']//a | //table[contains(@class, 'tree')]//td//a")
        
        for link in links:
            name = link.text_content().strip()
            href = link.get("href")
            if name and href:
                groups[name] = self.base_url + href if not href.startswith("http") else href
        
        return groups

    def _get_units_in_group(self, group_url: str) -> Dict[str, str]:
        """
        Returns { "Cylinder Head": "url", ... } of the diagrams inside a group.
        """
        tree = self._fetch_xpath(group_url)
        if tree is None:
            return {}

        units = {}
        # Typically grid of images with links
        # Try finding 'caption' or links with specific pattern
        links = tree.xpath("//div[@class='caption']//a | //div[contains(@class, 'unit')]//a")
        
        for link in links:
            name_node = link.xpath("normalize-space(text())")
            # If text is empty (maybe image link), try title attr or child?
            # Usually caption has text.
            name = str(name_node).strip()
            href = link.get("href")
            
            # Simple dedupe or filter
            if href and "gid=" in href:
                # Sometimes duplicate links (image + text), prefer text
                if not name: 
                    # Try finding a sibling header?
                    # Fallback: use usage
                    name = "Unit " + href.split("gid=")[-1]
                
                units[name] = self.base_url + href if not href.startswith("http") else href

        return units

    def _fetch_parts_from_unit_page(self, unit_url: str) -> List[Dict]:
        """
        Visits a specific Leaf Unit page and extracts the big table of parts.
        """
        tree = self._fetch_xpath(unit_url)
        if tree is None:
            return []

        parts = []
        # Standard table extraction
        rows = tree.xpath("//table//tr[position()>1]") 
        
        for row in rows:
            try:
                # Usually: [Number, Name, Code, Qty, etc.]
                cols = row.xpath(".//td")
                if len(cols) < 3: continue
                
                # Try to fuzzy match columns as they change
                # Expect Number in Col 1 or 'oem' class
                part_num_node = row.xpath(".//td[@class='oem']//text() | .//td[2]//text()")
                # If checking specifically col 2 for num? 
                # Let's try simpler:
                # Often: Col 0 = index/checkbox, Col 1 = Number, Col 2 = Name
                
                part_num = cols[1].text_content().strip()
                part_name = cols[2].text_content().strip()
                part_code = cols[3].text_content().strip() if len(cols) > 3 else ""
                
                if not part_num: continue

                parts.append({
                    "number": part_num,
                    "name": " ".join(part_name.split()),
                    "code": part_code
                })
            except:
                continue
                
        return parts

# ================= SINGLETON =================

_scraper: Optional[PartSouqXPathScraper] = None

def get_scraper() -> PartSouqXPathScraper:
    global _scraper
    if _scraper is None:
        _scraper = PartSouqXPathScraper()
    return _scraper

if __name__ == "__main__":
    # Test
    scraper = get_scraper()
    
    # 1. Test Details
    # print(scraper.get_vehicle_details("WBAFR71020C725456"))
    
    # 2. Test Search
    res = scraper.search_part("WBAFR71020C725456", "water pump")
    # print(res)
    if "parts" in res:
        print(f"\nFound {len(res['parts'])} parts for 'water pump':")
        for p in res["parts"][:5]:  # Print first 5
            print(f"{p['number']} | {p['name']} | {p['code']}")