import re
import json
import requests
from flask import current_app
from app.redis_client import redis_client
from app.services.inventory_service import normalize_part_number

VIN_REGEX = re.compile(r'^[A-HJ-NPR-Z0-9]{17}$', re.IGNORECASE)

class CatalogService:
    """
    Client for the vehicle catalog microservice:
    Base URL: https://api.carparts.koncpt-ai.tech
    - POST /api/vin/lookup: Decodes 17-char VINs to Brand, Model, Model Number, Year, Engine
    - GET  /api/vin/catalog?model_number=...&brand=...: Retrieves vehicle schematics and OEM parts
    """

    def _get_base_url(self) -> str:
        try:
            return current_app.config.get("CATALOG_API_BASE_URL", "https://api.carparts.koncpt-ai.tech")
        except Exception:
            return "https://api.carparts.koncpt-ai.tech"

    def is_likely_vin(self, vin: str) -> bool:
        if not vin:
            return False
        clean = re.sub(r'[^A-Z0-9]', '', str(vin).upper())
        return bool(VIN_REGEX.match(clean))

    def decode_vin(self, vin_raw: str) -> dict | None:
        """
        Decodes a 17-character VIN using the catalog microservice primary endpoint.
        Falls back to NHTSA API if primary returns no details or error.
        Returns dict with vin, brand, model, model_number, year, engine, details.
        """
        if not vin_raw:
            return None
        vin = re.sub(r'[^A-Z0-9]', '', str(vin_raw).upper())
        if not self.is_likely_vin(vin):
            return None

        # Check Redis Cache (cache for 24 hours)
        cache_key = f"catalog:vin:{vin}"
        try:
            cached = redis_client.get(cache_key)
            if cached:
                print(f"[CatalogService] Loaded VIN decode '{vin}' from Redis.")
                return json.loads(cached)
        except Exception:
            pass

        base_url = self._get_base_url()
        primary_endpoint = f"{base_url}/api/vin/lookup"
        decoded = None

        # 1. Primary: carparts microservice /api/vin/lookup
        try:
            print(f"[CatalogService] Decoding VIN {vin} via {primary_endpoint}...")
            res = requests.post(
                primary_endpoint,
                headers={"Content-Type": "application/json"},
                json={"vin": vin},
                timeout=15
            )

            if res.status_code == 200:
                data = res.json()
                if not data.get("Error") and not data.get("message") and (data.get("Brand NAME") or data.get("make") or data.get("Model Name") or data.get("model")):
                    brand = data.get("Brand NAME") or data.get("make") or data.get("Brand")
                    model = data.get("Model Name") or data.get("model")
                    model_num = data.get("Model Number") or data.get("model_number") or data.get("Model")
                    year = data.get("Manufacturer Year") or data.get("year")
                    engine = data.get("Engine") or data.get("engine")

                    decoded = {
                        "vin": vin,
                        "brand": brand,
                        "model": model,
                        "model_number": model_num,
                        "year": year,
                        "engine": engine,
                        "series": data.get("Series Description"),
                        "gearbox": data.get("Gearbox"),
                        "region": data.get("Region"),
                        "source": "carparts_microservice",
                        "is_fallback": False,
                        "details": data
                    }
                    print(f"[CatalogService] Decoded VIN {vin}: {brand} {model} ({model_num}) {year}")
        except Exception as e:
            print(f"[CatalogService] Primary VIN lookup failed for {vin}: {e}")

        # 2. Fallback: NHTSA API if primary didn't succeed
        if not decoded or not decoded.get("brand"):
            try:
                print(f"[CatalogService] Trying NHTSA fallback for VIN {vin}...")
                nhtsa_url = f"https://vpic.nhtsa.dot.gov/api/vehicles/decodevinvalues/{vin}?format=json"
                n_res = requests.get(nhtsa_url, timeout=10)
                if n_res.status_code == 200:
                    n_json = n_res.json()
                    results = n_json.get("Results", [])
                    if results:
                        r = results[0]
                        make = r.get("Make") or ""
                        model = r.get("Model") or ""
                        year = r.get("ModelYear") or ""
                        displacement = r.get("DisplacementL")
                        engine = f"{displacement}L" if displacement else None

                        if make or model:
                            decoded = {
                                "vin": vin,
                                "brand": make,
                                "model": model,
                                "model_number": None,
                                "year": year,
                                "engine": engine,
                                "series": None,
                                "source": "nhtsa",
                                "is_fallback": True,
                                "details": r
                            }
                            print(f"[CatalogService] NHTSA decoded VIN {vin}: {make} {model} {year}")
            except Exception as e:
                print(f"[CatalogService] NHTSA fallback failed: {e}")

        # Cache valid result in Redis for 24h
        if decoded and decoded.get("brand") and str(decoded.get("brand")).lower() != "n/a":
            try:
                redis_client.setex(cache_key, 86400, json.dumps(decoded))
            except Exception:
                pass

        return decoded

    def fetch_catalog(self, brand: str, model_number: str) -> dict | None:
        """
        Fetches vehicle schematic diagrams and catalog tree:
        GET /api/vin/catalog?model_number=...&brand=...
        """
        if not brand or not model_number:
            return None

        clean_brand = brand.strip()
        clean_model = model_number.strip()

        # Cache catalog in Redis (1 hour)
        cache_key = f"catalog:tree:{clean_brand.lower()}:{clean_model.lower()}"
        try:
            cached = redis_client.get(cache_key)
            if cached:
                print(f"[CatalogService] Loaded catalog {clean_brand} {clean_model} from Redis.")
                return json.loads(cached)
        except Exception:
            pass

        base_url = self._get_base_url()
        url = f"{base_url}/api/vin/catalog"
        params = {
            "model_number": clean_model,
            "brand": clean_brand
        }

        print(f"[CatalogService] Fetching catalog for {clean_brand} {clean_model}...")
        try:
            res = requests.get(url, params=params, timeout=25)
            if res.status_code == 200:
                data = res.json()
                try:
                    redis_client.setex(cache_key, 3600, json.dumps(data))
                except Exception:
                    pass
                return data
            elif res.status_code == 404:
                print(f"[CatalogService] Catalog not found for {clean_brand} {clean_model} (404)")
                return None
            else:
                print(f"[CatalogService] Catalog HTTP {res.status_code} for {clean_brand} {clean_model}")
                return None
        except Exception as e:
            print(f"[CatalogService] Catalog request failed: {e}")
            return None

    def search_schematics_and_extract_parts(self, vin_info: dict, part_queries: list[str]) -> list[dict]:
        """
        Searches vehicle schematics in the catalog for the specified part descriptions.
        Extracts matching OEM part numbers, names, schematic diagrams, and callouts.
        Returns list of matched part items:
        [
          {
            "number": "11517597715",
            "name": "Water Pump",
            "diagram_name": "Cooling System Water Pump",
            "diagram_code": "11_4080",
            "image_url": "...",
            "callout_number": "1"
          }, ...
        ]
        """
        if not vin_info or not part_queries:
            return []

        brand = vin_info.get("brand") or ""
        model_number = vin_info.get("model_number") or ""

        # If model_number is missing, we cannot load specific diagram tree
        if not model_number or not brand:
            return []

        catalog = self.fetch_catalog(brand, model_number)
        if not catalog or "categories" not in catalog:
            return []

        matched_parts = []
        seen_numbers = set()

        # Clean query tokens
        query_tokens_list = []
        for q in part_queries:
            tokens = [t.lower() for t in re.findall(r'[a-zA-Z0-9]+', q) if len(t) >= 2]
            if tokens:
                query_tokens_list.append((q.lower(), tokens))

        if not query_tokens_list:
            return []

        categories = catalog.get("categories", [])
        for cat in categories:
            diagrams = cat.get("diagrams", [])
            for diag in diagrams:
                diag_name = (diag.get("diagram_name") or "").lower()
                diag_code = diag.get("diagram_code")
                diag_img = diag.get("image_url")
                parts = diag.get("parts", [])

                # Check if diagram name matches any query tokens
                diag_matches = any(
                    any(tok in diag_name for tok in tokens)
                    for (q_str, tokens) in query_tokens_list
                )

                for p in parts:
                    p_name = (p.get("part_name") or "").lower()
                    p_desc = (p.get("description") or "").lower()
                    p_callout = p.get("callout_number")
                    p_num_entries = p.get("part_numbers", [])

                    # Match part by tokens
                    part_matches = False
                    for (q_str, tokens) in query_tokens_list:
                        # Match full phrase or all significant tokens
                        if q_str in p_name or q_str in p_desc:
                            part_matches = True
                            break
                        if all(tok in p_name or tok in p_desc or tok in diag_name for tok in tokens):
                            part_matches = True
                            break

                    if part_matches or diag_matches:
                        for entry in p_num_entries:
                            num = entry.get("part_number") if isinstance(entry, dict) else entry
                            if num:
                                norm = normalize_part_number(str(num))
                                if norm and norm not in seen_numbers:
                                    seen_numbers.add(norm)
                                    matched_parts.append({
                                        "number": str(num).strip(),
                                        "name": p.get("part_name") or "Catalog Part",
                                        "description": p.get("description"),
                                        "diagram_name": diag.get("diagram_name"),
                                        "diagram_code": diag_code,
                                        "image_url": diag_img,
                                        "callout_number": p_callout,
                                        "brand": brand or "OEM"
                                    })

        print(f"[CatalogService] Extracted {len(matched_parts)} candidate OEM parts from schematics for {part_queries}.")
        return matched_parts

catalog_service = CatalogService()
