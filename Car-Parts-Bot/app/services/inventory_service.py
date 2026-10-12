import re
import json
import requests
from flask import current_app
from app.redis_client import redis_client

VALID_TIERS = {"IND"}

def normalize_part_number(pn: str) -> str:
    """
    Standard normalization for automotive part numbers.
    Removes spaces, hyphens, and non-alphanumeric characters, returning uppercase string.
    Example: '34 11 6-785-669' -> '34116785669'
    """
    if not pn:
        return ""
    return re.sub(r'[^A-Z0-9]', '', str(pn).upper())

class InventoryService:
    """
    Service client for the ecommerce inventory REST API on carpartsai.ae:
    - POST /api/public/inventory: Batch lookup by part numbers
    - GET  /api/public/inventory: Multi-token query or part-name search
    Always enforces the Individual (IND) pricing tier.
    """

    def _get_base_url(self) -> str:
        try:
            return current_app.config.get("ECOMMERCE_API_BASE_URL") or current_app.config.get("LOVABLE_API_BASE_URL", "https://carpartsai.ae")
        except Exception:
            return "https://carpartsai.ae"

    def _get_api_key(self) -> str:
        try:
            return current_app.config.get("CHATBOT_API_KEY", "")
        except Exception:
            return ""

    def _get_headers(self) -> dict:
        api_key = self._get_api_key()
        return {
            "x-chatbot-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def _validate_tier(self, tier: str = "IND") -> str:
        # Dynamic automatic tier detection removed: Always enforce Individual (IND) tier
        return "IND"

    def lookup_batch(self, part_numbers: list, tier: str = "IND", limit: int = 100) -> dict:
        """
        Batch lookup parts by part numbers using POST /api/public/inventory.
        Returns dict with:
          success: bool
          count: int
          items: list[dict] (formatted for bot)
          map: dict[str, dict] (normalized_pn -> formatted_item)
          missing_pns: list[str] (part numbers not found)
        """
        tier = self._validate_tier(tier)
        if not part_numbers:
            return {"success": True, "count": 0, "items": [], "map": {}, "missing_pns": []}

        # Clean and deduplicate part numbers
        clean_pns = []
        seen_norm = set()
        for p in part_numbers:
            norm = normalize_part_number(p)
            if norm and norm not in seen_norm:
                seen_norm.add(norm)
                clean_pns.append(str(p).strip())

        if not clean_pns:
            return {"success": True, "count": 0, "items": [], "map": {}, "missing_pns": []}

        # Check Redis Cache
        cache_key = f"inv:batch:{tier}:" + ":".join(sorted(seen_norm))
        try:
            cached = redis_client.get(cache_key)
            if cached:
                print(f"[InventoryService] Loaded batch lookup ({len(clean_pns)} PNs) from Redis.")
                return json.loads(cached)
        except Exception:
            pass

        base_url = self._get_base_url()
        url = f"{base_url}/api/public/inventory"
        payload = {
            "part_numbers": clean_pns,
            "tier": tier,
            "limit": limit
        }

        print(f"[InventoryService] POST {url} for {len(clean_pns)} PNs (tier={tier})...")
        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=12
            )

            if response.status_code == 200:
                data = response.json()
                raw_items = data.get("items", [])
                formatted_items = [self.format_inventory_item(item, tier) for item in raw_items]

                # Build quick lookup map by normalized part number and OEM number
                items_map = {}
                found_norms = set()
                for item in formatted_items:
                    pn_norm = normalize_part_number(item.get("part_number", ""))
                    oem_norm = normalize_part_number(item.get("oem_number", ""))
                    if pn_norm:
                        items_map[pn_norm] = item
                        found_norms.add(pn_norm)
                    if oem_norm:
                        items_map[oem_norm] = item
                        found_norms.add(oem_norm)

                missing_pns = [p for p in clean_pns if normalize_part_number(p) not in found_norms]

                result = {
                    "success": True,
                    "count": len(formatted_items),
                    "items": formatted_items,
                    "map": items_map,
                    "missing_pns": missing_pns
                }

                # Cache in Redis for 45 seconds (fast response, real-time stock)
                try:
                    redis_client.setex(cache_key, 45, json.dumps(result))
                except Exception:
                    pass

                return result

            else:
                error_body = response.text[:300] if response.text else ""
                print(f"[InventoryService] Batch lookup HTTP {response.status_code}: {error_body}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "count": 0,
                    "items": [],
                    "map": {},
                    "missing_pns": clean_pns
                }

        except Exception as e:
            print(f"[InventoryService] Batch lookup network error: {e}")
            return {
                "success": False,
                "error": str(e),
                "count": 0,
                "items": [],
                "map": {},
                "missing_pns": clean_pns
            }

    def search_query(self, q: str, brand: str | None = None, tier: str = "IND", limit: int = 20) -> dict:
        """
        Mixed query or part-name search using GET /api/public/inventory.
        Returns dict with:
          success: bool
          query: str
          is_mixed_query: bool
          count: int
          items: list[dict] (formatted for bot)
        """
        tier = self._validate_tier(tier)
        q = (q or "").strip()
        if not q:
            return {"success": True, "query": "", "count": 0, "items": []}

        # Check Redis Cache
        cache_key = f"inv:query:{tier}:{brand or ''}:{q.lower()}"
        try:
            cached = redis_client.get(cache_key)
            if cached:
                print(f"[InventoryService] Loaded query search '{q}' from Redis.")
                return json.loads(cached)
        except Exception:
            pass

        base_url = self._get_base_url()
        url = f"{base_url}/api/public/inventory"
        params = {
            "q": q,
            "tier": tier,
            "limit": limit
        }
        if brand:
            params["brand"] = brand

        print(f"[InventoryService] GET {url} with q='{q}', brand={brand}, tier={tier}...")
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=12
            )

            if response.status_code == 200:
                data = response.json()
                raw_items = data.get("items", [])
                formatted_items = [self.format_inventory_item(item, tier) for item in raw_items]

                result = {
                    "success": True,
                    "query": data.get("query", q),
                    "is_mixed_query": data.get("is_mixed_query", False),
                    "count": len(formatted_items),
                    "items": formatted_items
                }

                # Cache in Redis for 45 seconds
                try:
                    redis_client.setex(cache_key, 45, json.dumps(result))
                except Exception:
                    pass

                return result

            else:
                error_body = response.text[:300] if response.text else ""
                print(f"[InventoryService] Query search HTTP {response.status_code}: {error_body}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "query": q,
                    "count": 0,
                    "items": []
                }

        except Exception as e:
            print(f"[InventoryService] Query search network error: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": q,
                "count": 0,
                "items": []
            }

    def format_inventory_item(self, item: dict, tier: str = "IND") -> dict:
        """
        Formats an item from /api/public/inventory into the dictionary structure
        expected by message_processor and gpt_service.
        """
        stock_val = 0
        try:
            stock_val = max(0, int(item.get("stock") or 0))
        except (ValueError, TypeError):
            stock_val = 0

        price_val = None
        # Always use Individual price (ind_price), fallback to price if not set
        raw_price = item.get("ind_price") if item.get("ind_price") is not None else item.get("price")
        if raw_price is not None:
            try:
                price_val = float(raw_price)
            except (ValueError, TypeError):
                price_val = None

        part_num = item.get("part_number") or item.get("oem_number") or ""
        brand_name = item.get("manufacturer") or item.get("brand") or "OEM"

        return {
            "part_number": part_num,
            "oem_number": item.get("oem_number"),
            "brand": brand_name,
            "name": item.get("name") or "Car Part",
            "price": price_val,
            "currency": item.get("currency") or "AED",
            "qty": stock_val,
            "stock": stock_val,
            "tag": item.get("category_tag") or "General",
            "status": "in_stock" if stock_val > 0 else "out_of_stock",
            "tier_applied": "IND",
            "ind_price": price_val,
            "image_url": item.get("image_url"),
            "all_images": item.get("all_images", []),
            "source": "ecommerce_inventory"
        }

inventory_service = InventoryService()
