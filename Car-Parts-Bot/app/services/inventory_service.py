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
            val = current_app.config.get("ECOMMERCE_API_BASE_URL") or current_app.config.get("LOVABLE_API_BASE_URL")
            if val:
                return val
        except Exception:
            pass
        import os
        return os.getenv("ECOMMERCE_API_BASE_URL") or os.getenv("LOVABLE_API_BASE_URL") or "https://carpartsai.ae"

    def _get_api_key(self) -> str:
        try:
            val = current_app.config.get("CHATBOT_API_KEY", "")
            if val:
                return val
        except Exception:
            pass
        import os
        return os.getenv("CHATBOT_API_KEY", "")

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
                cached_data = json.loads(cached)
                if cached_data.get("items"):
                    print(f"[InventoryService] Loaded batch lookup ({len(clean_pns)} PNs) from Redis.")
                    return cached_data
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

                # Fallback for missing part numbers: Query GET /api/public/inventory?q={pn}
                if missing_pns:
                    for mpn in list(missing_pns):
                        try:
                            fallback_res = self._direct_get_query(mpn, tier=tier, limit=10)
                            if fallback_res:
                                mpn_norm = normalize_part_number(mpn)
                                matched_items = []
                                for f_item in fallback_res:
                                    f_pn_norm = normalize_part_number(f_item.get("part_number", ""))
                                    f_oem_norm = normalize_part_number(f_item.get("oem_number", ""))
                                    f_raw_norm = normalize_part_number(f_item.get("raw_part_number", ""))
                                    f_tag_norm = normalize_part_number(f_item.get("tag", ""))
                                    f_name_norm = normalize_part_number(f_item.get("name", ""))

                                    is_match = (
                                        (f_pn_norm and (mpn_norm in f_pn_norm or f_pn_norm in mpn_norm)) or
                                        (f_oem_norm and (mpn_norm in f_oem_norm or f_oem_norm in mpn_norm)) or
                                        (f_raw_norm and (mpn_norm in f_raw_norm or f_raw_norm in mpn_norm)) or
                                        (f_tag_norm and (mpn_norm in f_tag_norm or f_tag_norm in mpn_norm)) or
                                        (f_name_norm and (mpn_norm in f_name_norm or f_name_norm in mpn_norm))
                                    )
                                    if is_match:
                                        matched_items.append(f_item)

                                # If no strict substring matched, accept items returned by API for this query
                                if not matched_items and fallback_res:
                                    matched_items = fallback_res[:5]

                                if matched_items:
                                    # Sort in-stock first, lowest price first
                                    matched_items.sort(key=lambda x: (
                                        0 if int(x.get("stock") or 0) > 0 else 1,
                                        float(x.get("price") or 999999) if x.get("price") is not None else 999999
                                    ))
                                    for m_item in matched_items:
                                        if m_item not in formatted_items:
                                            formatted_items.append(m_item)
                                        m_pn_norm = normalize_part_number(m_item.get("part_number", ""))
                                        items_map[mpn_norm] = m_item
                                        if m_pn_norm:
                                            items_map[m_pn_norm] = m_item
                                    if mpn in missing_pns:
                                        missing_pns.remove(mpn)
                        except Exception as e:
                            print(f"[InventoryService] Fallback query error for '{mpn}': {e}")

                result = {
                    "success": True,
                    "count": len(formatted_items),
                    "items": formatted_items,
                    "map": items_map,
                    "missing_pns": missing_pns
                }

                # Cache in Redis for 45 seconds only when items were found
                if formatted_items:
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

    def _generate_query_variations(self, q: str) -> list[str]:
        variations = [q.strip()]
        lower_q = q.strip().lower()
        irregulars = {
            "brakes": "brake",
            "pads": "pad",
            "filters": "filter",
            "plugs": "plug",
            "wipers": "wiper",
            "blades": "blade",
            "discs": "disc",
            "rotors": "rotor",
            "shocks": "shock",
            "struts": "strut",
            "valves": "valve",
            "belts": "belt",
            "hoses": "hose",
            "lights": "light",
            "bulbs": "bulb",
            "mirrors": "mirror",
            "bearings": "bearing",
            "gaskets": "gasket",
            "sensors": "sensor",
            "pumps": "pump",
            "coils": "coil",
            "calipers": "caliper",
        }
        words = lower_q.split()
        singular_words = []
        has_change = False
        for w in words:
            if w in irregulars:
                singular_words.append(irregulars[w])
                has_change = True
            elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
                singular_words.append(w[:-1])
                has_change = True
            else:
                singular_words.append(w)

        if has_change:
            singular_phrase = " ".join(singular_words)
            if singular_phrase not in variations:
                variations.append(singular_phrase)

        # 2. Position-stripped variations (e.g. "rear shock absorber" -> "shock absorber", "front brake pad" -> "brake pad")
        pos_regex = r'\b(front|rear|left|right|upper|lower|inner|outer)\b'
        stripped_pos = re.sub(pos_regex, '', lower_q, flags=re.I).strip()
        stripped_pos = re.sub(r'\s+', ' ', stripped_pos)
        if stripped_pos and stripped_pos != lower_q:
            if stripped_pos not in variations:
                variations.append(stripped_pos)
            stripped_singulars = []
            for w in stripped_pos.split():
                if w in irregulars:
                    stripped_singulars.append(irregulars[w])
                elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
                    stripped_singulars.append(w[:-1])
                else:
                    stripped_singulars.append(w)
            stripped_singular_phrase = " ".join(stripped_singulars)
            if stripped_singular_phrase not in variations:
                variations.append(stripped_singular_phrase)

        return variations

    def _direct_get_query(self, q: str, brand: str | None = None, tier: str = "IND", limit: int = 20) -> list:
        base_url = self._get_base_url()
        url = f"{base_url}/api/public/inventory"
        params = {"q": q, "tier": tier, "limit": limit}
        if brand:
            params["brand"] = brand
        try:
            resp = requests.get(url, headers=self._get_headers(), params=params, timeout=10)
            if resp.status_code == 200:
                raw_items = resp.json().get("items", [])
                return [self.format_inventory_item(item, tier) for item in raw_items]
        except Exception:
            pass
        return []

    def search_query(self, q: str, brand: str | None = None, tier: str = "IND", limit: int = 20) -> dict:
        """
        Mixed query or part-name search using GET /api/public/inventory.
        Supports automatic singular/plural variations and position stripping.
        Strictly respects brand filter when provided to avoid cross-brand mismatch.
        Prioritizes in-stock items sorted lowest price first.
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

        variations = self._generate_query_variations(q)
        found_items = []
        matched_query = q

        # Search variations with brand filter
        for var_q in variations:
            print(f"[InventoryService] GET /api/public/inventory with q='{var_q}', brand={brand}, tier={tier}...")
            items = self._direct_get_query(var_q, brand=brand, tier=tier, limit=limit)
            if items:
                in_stock_items = [it for it in items if int(it.get("stock") or 0) > 0]
                if in_stock_items:
                    found_items = in_stock_items
                    matched_query = var_q
                    break
                elif not found_items:
                    # Keep as fallback only if no subsequent variation has in-stock items
                    found_items = items
                    matched_query = var_q

        # If brand was NOT specified at all, query without brand
        if not found_items and not brand:
            for var_q in variations:
                items = self._direct_get_query(var_q, brand=None, tier=tier, limit=limit)
                if items:
                    found_items = items
                    matched_query = var_q
                    break

        # Sort: In-stock first, then lowest price first (following prompt rules)
        if found_items:
            found_items.sort(key=lambda x: (
                0 if int(x.get("stock") or 0) > 0 else 1,
                float(x.get("price") or 999999) if x.get("price") is not None else 999999
            ))

        result = {
            "success": True,
            "query": matched_query,
            "is_mixed_query": False,
            "count": len(found_items),
            "items": found_items
        }

        # Cache in Redis for 45 seconds
        if found_items:
            try:
                redis_client.setex(cache_key, 45, json.dumps(result))
            except Exception:
                pass

        return result

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

        raw_pn = item.get("part_number") or item.get("oem_number") or ""
        clean_part_num = raw_pn
        if "," in clean_part_num:
            parts_split = [p.strip() for p in clean_part_num.split(",") if p.strip()]
            if parts_split:
                clean_part_num = parts_split[0]

        brand_name = item.get("manufacturer") or item.get("brand") or "OEM"

        return {
            "part_number": clean_part_num,
            "raw_part_number": raw_pn,
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
