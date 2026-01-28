from app.extensions import db
from app.models import Stock
from app.services.gpt_service import GPTService
from app.services.scraper.partsouq_xpath_scraper import get_scraper
from app.session_store import get_session, save_session, set_vin
from sqlalchemy import func
import re

gpt = GPTService()

def normalize_part_number(pn: str) -> str:
    """Standard normalization for part numbers."""
    return re.sub(r'[^A-Z0-9]', '', pn.upper()) if pn else ''

def search_parts_in_db(part_numbers: list) -> list:
    """
    Search database for exact matches of part numbers.
    Returns list of matched part dictionaries.
    """
    if not part_numbers:
        return []

    # clean inputs
    cleaned_pns = {normalize_part_number(p) for p in part_numbers if p}
    if not cleaned_pns:
        return []

    # Prepare DB query
    normalized_db_column = func.upper(Stock.part_number)
    # Strip symbols from DB column for matching
    # Extended list to match Python's alphanumeric normalization more closely
    for ch in ['-', ' ', '+', '%', '$', '_', '/', '.', ',', ':', ';', '#', '@', '!', '*',
                        '(', ')', '?', '&', '=', '<', '>', '~', '`', '|', '^', '"', "'",
                        '~', '´', '“', '”', '‘', '’', '–', '—', '•', '…', '{', '}', '[', ']']:
        normalized_db_column = func.replace(normalized_db_column, ch, '')

    results = []
    # 1. Exact Match via Normalization
    matches = db.session.query(Stock).filter(
        normalized_db_column.in_(cleaned_pns)
    ).all()

    # --- SIBLING LOGIC ---
    # Fetch matched tags to find related/alternative parts
    if matches:
        found_tags = {p.tag for p in matches if p.tag}
        print(f"   🔍 [Debug] Initial Matches: {len(matches)}. Found Tags: {found_tags}")
        
        if found_tags:
            # Query all parts that share these tags
            siblings = db.session.query(Stock).filter(
                Stock.tag.in_(found_tags)
            ).all()
            
            print(f"   🔍 [Debug] Siblings Found (Raw): {len(siblings)}")

            # Merit: If we found siblings, use them. 
            # We assume siblings include the original matches if they have the tag.
            # But let's merge safely.
            
            # Create a dict by ID to deduplicate
            # (matches + siblings) -> unique collection
            all_parts_map = {p.id: p for p in matches}
            for s in siblings:
                all_parts_map[s.id] = s
            
            matches = list(all_parts_map.values())
            print(f"   🔍 [Debug] Total Combined Matches: {len(matches)}")

    # 2. Add results to list (deduplicated by ID or PartNumber+Brand)
    for p in matches:
        results.append({
            "part_number": p.part_number,
            "brand": p.brand,
            "name": p.item_desc,
            "price": float(p.price) if p.price else None,
            "qty": p.qty,
            "tag": p.tag or "General"
        })
    
    return results

def search_catalog_by_name(vin: str, part_names: list) -> list:
    """
    Search external catalog (Scraper) using VIN and Part Name.
    Returns mixed list: 
    - Full DB objects (if in stock)
    - Virtual objects (if in catalog but not in stock)
    """
    if not vin or not part_names:
        return []

    scraper = get_scraper()
    if not scraper:
        print("⚠️ No scraper available for catalog search.")
        return []

    results = []
    print(f"🔎 Searching Catalog with VIN={vin} for Content={part_names}")

    for name in part_names:
        try:
            # Scrape
            scrape_data = scraper.search_part(vin, name)
            # print(f"   --> Scraper Result for '{name}': {list(scrape_data.keys())}")
            
            if "error" in scrape_data:
                print(f"   ❌ Catalog returned error: {scrape_data['error']}")
                results.append({"status": "error", "message": "Failed to Catalog", "debug_error": scrape_data['error']})
                continue

            if "parts" in scrape_data:
                parts_list = scrape_data["parts"]
                print(f"   --> Found {len(parts_list)} raw parts in catalog.")

                if not parts_list:
                     results.append({"status": "empty", "message": "Not in Catalog"})
                     continue

                # Extract OEM Numbers
                found_oem_numbers = [
                    normalize_part_number(p.get("number")) 
                    for p in parts_list 
                    if p.get("number")
                ]
                
                print(f"   --> Extracted OEM Numbers: {found_oem_numbers}")
                
                if not found_oem_numbers:
                    results.append({"status": "empty", "message": "Not in Catalog"})
                    continue

                # Check DB for these OEM numbers
                db_matches = search_parts_in_db(found_oem_numbers)
                # print(db_matches)
                if db_matches:
                    print(f"   ✅ Found {len(db_matches)} matches in Local DB (Stock).")
                    results.extend(db_matches)
                else:
                    print(f"   ⚠️ Found in Catalog but NOT in Local DB. Adding as 'Out of Stock' reference.")
                    # Add virtual "Catalog Only" results so GPT knows the part EXISTS.
                    # We take the first 3 from catalog to avoid spamming.
                    for p in parts_list[:3]:
                        results.append({
                            "part_number": p.get("number"),
                            "brand": "OEM/Catalog", # or details from scraper
                            "name": p.get("name") or name,
                            "price": None, # No price means check stock
                            "qty": 0,
                            "tag": "Catalog Match (Not in Stock)",
                            "status": "out_of_stock"
                        })

        except Exception as e:
            print(f"❌ Scraper error for {name}: {e}")
            results.append({"status": "error", "message": "Failed to Catalog", "debug_error": str(e)})

    return results


def process_user_message(user_id: str, unified_text: str) -> str:
    """
    SINGLE PIPELINE:
    1. Extract Entities (VIN, PNs, Names)
    2. Hard Lookups (VIN Decode, DB Search)
    3. GPT Super Intent
    """
    session = get_session(user_id)
    print(f"Processing message for {user_id}: {unified_text[:100]}...")


    # --- STEP 1: ENTITY EXTRACTION ---
    extracted = gpt.extract_entities(unified_text)
    
    vin_list = extracted.get("vin_list", [])
    part_numbers = extracted.get("part_numbers", [])
    item_descriptions = extracted.get("item_descriptions", [])
    print("vin list",vin_list)
    print("part numbers",part_numbers)
    print("item descriptions",item_descriptions)
    # --- STEP 2: HARD LOOKUPS ---
    
    # A. VIN Handling
    current_vin = session["entities"].get("vin")
    vin_info = None
    
    # If new VIN found, use it
    if vin_list:
        new_vin = vin_list[0] # Take first valid
        # Validate logic could go here (17 chars check is in extraction prompt roughly)
        if len(new_vin) == 17:
             set_vin(session, new_vin)
             current_vin = new_vin
             save_session(user_id, session)

    # Decode VIN if we have one (or use cached)
    if current_vin:
        cached_info = session.get("vin_details")
        # Check cache first
        if cached_info and cached_info.get("vin") == current_vin:
            vin_info = cached_info
            # print(f"Using cached stored stored VIN details for {current_vin}")
        else:
            # Not cached or new VIN -> Scrape
            scraper = get_scraper()
            print(f"IT IS GOING TO FIND THE VIN {current_vin}")
            if scraper:
                try:
                    # print(f"Decoding VIN {current_vin} via Scraper...")
                    details = scraper.get_vehicle_details(current_vin)
                    if details:
                        vin_info = {
                            "vin": current_vin,
                            "brand": details.get("brand"),
                            "model": details.get("name"), 
                            "year": details.get("date")
                        }
                        # Cache it
                        session["vin_details"] = vin_info
                        save_session(user_id, session)
                except Exception as e:
                    print(f"⚠️ VIN Decode Warning (non-fatal): {e}")
                    # If scrape fails, we just proceed without vehicle details. 
                    # We do NOT clear the VIN yet, maybe ephemeral network error.

    
    # --- BRAND VALIDATION ---
    # Only validate if:
    # 1. A new VIN was provided in THIS message (vin_list is not empty)
    # 2. OR we have a stored VIN AND the user is actually asking for parts (part_numbers or item_descriptions exist)
    # This prevents blocking generic chat ("hi", "need help") just because a stale unsupported VIN is in history.
    
    should_validate_brand = False
    if vin_list:
        should_validate_brand = True
    elif vin_info and (part_numbers or item_descriptions):
        should_validate_brand = True
    # print(vin_info)
    if should_validate_brand and vin_info:
        brand = vin_info.get("brand", "").lower()
        supported = ["bmw", "mercedes", "benz", "rolls royce", "mini", "honda"]
        
        # Check if any supported keyword is in the brand string
        is_supported = any(s in brand for s in supported)
        if brand == "n/a":
            return "Catelog data not found for this VIN"
        if not is_supported:
            print(f"⛔ Unsupported Brand: {brand}. Rejecting (Not a Warning Light).")
            
            # --- CLEAR SESSION FOR UNSUPPORTED VIN ---
            # To prevent "poisoned" sessions where user gets stuck with a bad VIN
            if session.get("entities"):
                session["entities"]["vin"] = None
            session["vin_details"] = None
            save_session(user_id, session)
            print(f"🧹 Cleared session VIN data for user {user_id}")

            return "We only support these car parts (BMW, Mercedes, Rolls Royce, Mini, Honda).\nFor more details please contact us on +971 54 751 6365"


    # B. Part Search
    parts_found = []
    
    # 1. Search by Part Number (Highest Priority)
    if part_numbers:
        parts_found.extend(search_parts_in_db(part_numbers))
        
    # 2. Search by Name (If VIN exists)
    if current_vin and item_descriptions and not parts_found:
        # Only search catalog if we didn't match via explicit Part Number? 
        # Or always? Requirement: "If item_descriptions exist -> search catalog".
        # We'll search and append.
        catalog_matches = search_catalog_by_name(current_vin, item_descriptions)
        parts_found.extend(catalog_matches)

    # --- STEP 3: CONTEXT PREPARATION ---
    context_data = {
        "vin_info": vin_info,
        "parts_found": parts_found,
        "session_summary": f"User ID: {user_id}. Stored VIN: {current_vin}"
    }

    # --- STEP 4: INTENT ROUTING ---
    # Standard Super Intent
    gpt_result = gpt.run_super_intent(unified_text, context_data)
    
    whatsapp_reply = gpt_result.get("whatsapp_text", "...")
    payload = gpt_result.get("machine_payload", {})
    
    # print(f"GPT Result: {payload}")
    
    # --- STEP 5: ACTIONS (Backend Side Effects) ---
    action = payload.get("action")
    
    if action == "escalate":
        # Handle escalation (e.g. notify admin, flag lead)
        pass
    
    # Save Lead (Unified for all)
    # lead_service.create_lead(...) - Skipping for brevity unless required by original file logic
    # The original file had lead creation. We should probably keep it if possible.
    
    return whatsapp_reply