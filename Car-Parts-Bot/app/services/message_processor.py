from app.extensions import db
from app.models import Stock, User, PartSearchLog
from app.services.gpt_service import GPTService
from app.services.scraper.partsouq_xpath_scraper import get_scraper
from app.services.inventory_service import inventory_service, normalize_part_number
from app.services.catalog_service import catalog_service
from app.session_store import get_session, save_session, set_vin, log_failed_vin
from app.services.lead_service import lead_service
from sqlalchemy import func, or_
import re

gpt = GPTService()

# --- CONSTANTS ---
# Live prompt Failure Handling message (carpartsai.ae)
FAILURE_HANDLING_MESSAGE = (
    "Thank you for your message.\n"
    "I am unable to fetch your details accurately at the moment.\n"
    "Our team will contact you soon to assist you further.\n"
    "You may also reach us on WhatsApp at +971504827057."
)

def search_parts_in_db(part_numbers: list, tier: str = "IND") -> list:
    """
    Search ecommerce inventory API (POST /api/public/inventory) for exact matches of part numbers.
    Falls back to local database if ecommerce API is unavailable.
    Returns list of matched part dictionaries with real-time stock and AED pricing.
    """
    if not part_numbers:
        return []

    results = []

    # 1. Primary: E-commerce Inventory API (POST /api/public/inventory)
    try:
        inv_res = inventory_service.lookup_batch(part_numbers, tier=tier)
        if inv_res.get("items"):
            in_stock_items = [it for it in inv_res["items"] if int(it.get("stock") or 0) > 0]
            results.extend(in_stock_items)
            print(f"   [Inventory API] Found {len(in_stock_items)} in-stock parts for {part_numbers} (tier={tier}).")
    except Exception as e:
        print(f"   [Inventory API] Error querying ecommerce inventory: {e}")

    # Check if all part numbers were satisfied by ecommerce API
    found_norm = set()
    for p in results:
        if p.get("part_number"):
            found_norm.add(normalize_part_number(p["part_number"]))
        if p.get("oem_number"):
            found_norm.add(normalize_part_number(p["oem_number"]))
        if p.get("raw_part_number"):
            found_norm.add(normalize_part_number(p["raw_part_number"]))
        if p.get("tag"):
            found_norm.add(normalize_part_number(p["tag"]))

    remaining_pns = []
    for p in part_numbers:
        p_norm = normalize_part_number(p)
        matched = any(p_norm == fn or p_norm in fn or fn in p_norm for fn in found_norm if fn)
        if not matched:
            remaining_pns.append(p)

    # 1B. Direct ecommerce advanced search fallback for any remaining part numbers
    # (uses GET query — same tokenized/fuzzy matching as carpartsai.ae website search bar)
    for rpn in list(remaining_pns):
        try:
            q_res = inventory_service.advanced_search(rpn, tier=tier, limit=5)
            if q_res.get("items"):
                in_stock_adv = [it for it in q_res["items"] if int(it.get("stock") or 0) > 0]
                for it in in_stock_adv:
                    if it not in results:
                        results.append(it)
                if in_stock_adv:
                    rpn_norm = normalize_part_number(rpn)
                    if any(rpn_norm in normalize_part_number(it.get("part_number", "")) or normalize_part_number(it.get("part_number", "")) in rpn_norm for it in in_stock_adv):
                        remaining_pns.remove(rpn)
        except Exception as e:
            print(f"   [Inventory API] Advanced search error for '{rpn}': {e}")

    if not remaining_pns:
        return results

    # 2. Fallback: Local Database for remaining missing part numbers
    try:
        cleaned_pns = {normalize_part_number(p) for p in remaining_pns if p}
        if not cleaned_pns:
            return results

        # Prepare DB query
        normalized_db_column = func.upper(Stock.part_number)
        for ch in ['-', ' ', '+', '%', '$', '_', '/', '.', ',', ':', ';', '#', '@', '!', '*',
                   '(', ')', '?', '&', '=', '<', '>', '~', '`', '|', '^', '"', "'",
                   '~', '´', '“', '”', '‘', '’', '–', '—', '•', '…', '{', '}', '[', ']']:
            normalized_db_column = func.replace(normalized_db_column, ch, '')

        normalized_tag_column = func.upper(Stock.tag)
        for ch in ['-', ' ', '+', '%', '$', '_', '/', '.', ',', ':', ';', '#', '@', '!', '*',
                   '(', ')', '?', '&', '=', '<', '>', '~', '`', '|', '^', '"', "'",
                   '~', '´', '“', '”', '‘', '’', '–', '—', '•', '…', '{', '}', '[', ']']:
            normalized_tag_column = func.replace(normalized_tag_column, ch, '')

        matches = db.session.query(Stock).filter(
            or_(
                normalized_db_column.in_(cleaned_pns),
                normalized_tag_column.in_(cleaned_pns)
            )
        ).all()

        # Sibling logic
        if matches:
            found_tags = {p.tag for p in matches if p.tag}
            if found_tags:
                siblings = db.session.query(Stock).filter(Stock.tag.in_(found_tags)).all()
                all_parts_map = {p.id: p for p in matches}
                for s in siblings:
                    all_parts_map[s.id] = s
                matches = list(all_parts_map.values())

        db_results = []
        for p in matches:
            if p.qty and p.qty > 0:
                db_results.append({
                    "part_number": p.part_number,
                    "brand": p.brand,
                    "name": p.item_desc,
                    "price": float(p.price) if p.price else None,
                    "currency": "AED",
                    "qty": p.qty,
                    "stock": p.qty,
                    "tag": p.tag or "General",
                    "status": "in_stock",
                    "source": "local_db"
                })
        return results + db_results
    except Exception as e:
        print(f"⚠️ [DB Fallback] Database query unavailable: {e}. Returning inventory results.")
        return results

def search_catalog_by_name(vin: str, part_names: list, vin_info: dict = None, tier: str = "IND") -> list:
    """
    Search real-time part numbers, stock, and pricing from the CarParts ecommerce catalogue API (carpartsai.ae).
    Filters parts by vehicle brand (e.g. BMW, Honda) decoded from the VIN.
    Cross-checks with vehicle schematics to extract matching OEM numbers if needed, but ALWAYS
    returns genuine in-stock products with AED prices from the ecommerce catalogue API.
    """
    if not part_names:
        return []

    results = []
    brand = vin_info.get("brand") if vin_info else None
    print(f"🔎 [Ecommerce Catalogue Search] Searching carpartsai.ae for '{part_names}' (VIN={vin}, Brand={brand})")

    # 1. PRIMARY: Query CarParts E-Commerce Catalogue API directly for each requested part name
    seen_ids = set()
    for name in part_names:
        try:
            q_res = inventory_service.search_query(name, brand=brand, tier=tier, limit=10)
            if q_res.get("items"):
                for it in q_res["items"]:
                    it_key = normalize_part_number(it.get("part_number") or it.get("name") or "")
                    if it_key and it_key not in seen_ids:
                        seen_ids.add(it_key)
                        results.append(it)
            else:
                # Retry with alternative synonyms from the live alias group (matching ecommerce rule)
                synonyms = gpt.get_alias_synonyms(name)
                for syn in synonyms[:3]:
                    print(f"   --> Retrying with alias synonym: '{syn}' (brand={brand})")
                    s_res = inventory_service.search_query(syn, brand=brand, tier=tier, limit=10)
                    if s_res.get("items"):
                        for it in s_res["items"]:
                            it_key = normalize_part_number(it.get("part_number") or it.get("name") or "")
                            if it_key and it_key not in seen_ids:
                                seen_ids.add(it_key)
                                results.append(it)
                        break

                # If still no items and part name contains position, try base name with brand
                if not results:
                    base_name = re.sub(r'\b(front|rear|left|right|upper|lower|inner|outer)\b', '', name, flags=re.I).strip()
                    if base_name and base_name.lower() != name.lower():
                        print(f"   --> Retrying with base part name: '{base_name}' (brand={brand})")
                        b_res = inventory_service.search_query(base_name, brand=brand, tier=tier, limit=10)
                        if b_res.get("items"):
                            for it in b_res["items"]:
                                it_key = normalize_part_number(it.get("part_number") or it.get("name") or "")
                                if it_key and it_key not in seen_ids:
                                    seen_ids.add(it_key)
                                    results.append(it)
        except Exception as e:
            print(f"⚠️ [Ecommerce Catalogue API] Search error for '{name}': {e}")

    if results:
        print(f"✅ [Ecommerce Catalogue API] Found {len(results)} matching products from carpartsai.ae.")
        return results

    # 2. SECONDARY: If direct keyword search returned 0 items, check vehicle schematics
    # to extract OEM part numbers, and cross-check those OEM numbers against ecommerce inventory.
    try:
        if not vin_info and vin:
            vin_info = catalog_service.decode_vin(vin)

        if vin_info and vin_info.get("brand") and vin_info.get("model_number"):
            extracted_parts = catalog_service.search_schematics_and_extract_parts(vin_info, part_names)
            if extracted_parts:
                print(f"   --> Found {len(extracted_parts)} raw schematic parts in vehicle catalog.")
                try:
                    parts_list = gpt.filter_parts_by_relevance(extracted_parts, " ".join(part_names))
                except Exception:
                    parts_list = extracted_parts[:8]

                found_oem_numbers = [
                    normalize_part_number(p.get("number"))
                    for p in (parts_list or extracted_parts[:5])
                    if p.get("number")
                ]

                if found_oem_numbers:
                    inv_res = inventory_service.lookup_batch(found_oem_numbers, tier=tier)
                    if inv_res.get("items"):
                        print(f"✅ [Cross-Reference] Found {len(inv_res['items'])} matching ecommerce items for schematic OEM numbers.")
                        for it in inv_res["items"]:
                            it_key = normalize_part_number(it.get("part_number") or it.get("name") or "")
                            if it_key and it_key not in seen_ids:
                                seen_ids.add(it_key)
                                results.append(it)
    except Exception as e:
        print(f"⚠️ [Catalog Cross-Reference] Error: {e}")

    # Return only genuine in-stock products found in ecommerce inventory.
    # Enforce Stock Filtering rule: Quantity > 0, sorted by lowest rate first.
    in_stock_results = [it for it in results if int(it.get("stock") or 0) > 0]
    in_stock_results.sort(key=lambda x: float(x.get("price") or 999999) if x.get("price") is not None else 999999)
    return in_stock_results

def search_db_by_tag(descriptions: list, tier: str = "IND") -> list:
    """
    Search ecommerce inventory or database for Tags matching the extracted item descriptions.
    Input: ["Wiper Blade 22\"", "Oil Filter"]
    """
    if not descriptions:
        return []

    print(f"   🔍 [Tag/Inventory Search] Checking for descriptions: {descriptions} (tier={tier})")
    
    # 1. Primary: Query Ecommerce Inventory API
    try:
        inv_matches = []
        for desc in descriptions:
            q_res = inventory_service.search_query(desc, tier=tier, limit=10)
            if q_res.get("items"):
                inv_matches.extend(q_res["items"])
        if inv_matches:
            return inv_matches
    except Exception as e:
        print(f"   [Tag Search] Inventory query error: {e}")

    unique_matches = {}

    try:
        for desc in descriptions:
            search_term = f"%{desc}%"
            
            matches = db.session.query(Stock).filter(
                 Stock.tag.ilike(search_term)
            ).limit(10).all()
            
            for m in matches:
                if m.id not in unique_matches:
                     unique_matches[m.id] = {
                        "part_number": m.part_number,
                        "brand": m.brand,
                        "name": m.item_desc or m.tag,
                        "price": m.price,
                        "currency": "AED",
                        "qty": m.qty,
                        "stock": m.qty,
                        "tag": m.tag,
                        "status": "in_stock" if m.qty > 0 else "out_of_stock",
                        "source": "localdb_tag"
                    }
    except Exception as e:
        print(f"⚠️ [Tag Search Fallback] Database query unavailable: {e}")

    return list(unique_matches.values())


def process_user_message(user_id: str, unified_text: str) -> str:
    """
    SINGLE PIPELINE:
    1. Extract Entities (VIN, PNs, Names)
    2. Hard Lookups (VIN Decode, DB Search)
    3. GPT Super Intent
    """
    session = get_session(user_id)
    print(f"Processing message for {user_id}: {unified_text[:100]}...")

    # --- MULTILINGUAL TRACKING & SESSION CONTINUITY ---
    detected_lang = "en"
    try:
        detected_lang = gpt.translation_service.detect_language(unified_text)
    except Exception as e:
        print(f"⚠️ Language detection error: {e}")
        detected_lang = "en"

    english_reset_phrases = ["in english", "speak english", "talk english", "english please", "reply in english"]
    if any(p in unified_text.lower() for p in english_reset_phrases):
        session["lang"] = "en"
        save_session(user_id, session)
        user_lang = "en"
    elif detected_lang != "en":
        session["lang"] = detected_lang
        save_session(user_id, session)
        user_lang = detected_lang
    else:
        user_lang = session.get("lang") or "en"

    # --- SHORT-CIRCUIT FOR SYSTEM NOTICES ---
    # E.g. from document_service returning "System Notice: The document has more than 5 pages..."
    if "System Notice:" in unified_text:
        # Extract the notices and return them directly
        import re
        notices = re.findall(r'System Notice:\s*(.*)', unified_text)
        if notices:
            return "\n\n".join(notices)
        return unified_text.strip()

    # --- ENSURE USER RECORD EXISTS ---
    # Disabled User tracking in local DB, now using Lovable API
    vin_search_logs = []

    # --- STEP 1: ENTITY EXTRACTION (ALWAYS RUN FIRST) ---
    extracted = gpt.extract_entities(unified_text)
    
    vin_list = extracted.get("vin_list", [])
    part_numbers = extracted.get("part_numbers", [])
    item_descriptions = extracted.get("item_descriptions", [])
    raw_item_descriptions = extracted.get("raw_item_descriptions", [])
    is_warning_light = extracted.get("is_warning_light", False)
    
    # --- PRICING TIER (ALWAYS INDIVIDUAL PRICE) ---
    # Dynamic tier detection removed: Always show Individual (IND) price to all users.
    user_tier = "IND"
    if session.get("tier") != "IND":
        session["tier"] = "IND"
        save_session(user_id, session)
    
    # --- SIMPLIFIED WORKSHOP LOGIC ---
    preferred_area = None
    lower_msg = unified_text.lower()
    workshop_recommends = ["suggest workshop", "recommend workshop", "find workshop", "suggest garage", "recommend garage", "find garage", "nearby workshop", "nearest workshop"]
    is_workshop_request = any(kw in lower_msg for kw in workshop_recommends) or (
        any(w in lower_msg for w in ["workshop", "garage"]) and any(w in lower_msg for w in ["recommend", "suggest", "find", "near", "location", "address", "where", "best"])
    )
    
    if is_workshop_request:
        print("[Workshop] Workshop Recommendation Request Detected. Setting state: workshop_area")
        session["state"]["awaiting"] = "workshop_area"
        save_session(user_id, session)
    
    elif session.get("state", {}).get("awaiting") == "workshop_area":
        # Capture the area and clear the state
        preferred_area = unified_text.strip()
        print(f"[Workshop] Preferred Area Captured: {preferred_area}")
        session["state"]["awaiting"] = None
        save_session(user_id, session)
    
    # --- LOG SEARCHES FOR PART DEMAND INTELLIGENCE ---
    # Disabled PartSearchLog in local DB, now using Lovable API

    print("vin list",vin_list)
    print("part numbers",part_numbers)
    print("item descriptions",item_descriptions)
    print("is_warning_light : ", is_warning_light)
    # --- STEP 1.5: CLARIFICATION STATE HANDLING ---
    # Check if we were waiting for a clarification response
    current_state = session.get("state", {}).get("awaiting")
    
    # if current_state == "clarification_part":
    #     pending_clarifications = session["state"].get("pending_clarifications", [])
    #     other_items = session["state"].get("clarification_others", [])
        
    #     # Legacy check for single item state (migration safety)
    #     if not pending_clarifications and session["state"].get("clarification_target"):
    #          pending_clarifications = [{"target": session["state"].get("clarification_target"), "valid_options": session["state"].get("validation_options", [])}]

    #     # SAFETY CHECK: 
    #     # If user uploaded a VIN (vin_list not empty) OR text is very long (>50 chars),
    #     # they are likely NOT answering "Upper/Lower" but changing context/uploading document.
    #     # In this case, we ABORT the clarification and process the new input normally.
    #     is_context_switch = bool(vin_list) or len(unified_text) > 200
        
    #     if is_context_switch:
    #         print(f"⚠️ Context Switch Detected during Clarification (VIN found or long text). Aborting.")
    #         # Clear state, proceed with 'extracted' as is
    #         session["state"]["awaiting"] = None
    #         session["state"]["pending_clarifications"] = None
    #         session["state"]["clarification_others"] = None
    #         session["state"]["clarification_target"] = None # Legacy clear
    #         session["state"]["validation_options"] = None # Legacy clear
    #         save_session(user_id, session)
    #         # Flow falls through to normal Step 2 with the NEW extracted entities (e.g. the VIN)
            
    #     elif pending_clarifications:
    #         resolved_items = []
    #         user_text_lower = unified_text.lower()
    #         any_resolved = False
            
    #         # Check EACH pending clarification against the user answer
    #         for pc in pending_clarifications:
    #             target = pc.get("target")
    #             opts = pc.get("valid_options", [])
                
    #             # lenient check
    #             is_match = False
    #             if not opts:
    #                 is_match = True # Fallback if no strict options
    #             elif any(opt in user_text_lower for opt in opts):
    #                 is_match = True
                    
    #             if is_match:
    #                 # Combined: "Upper Coolant Hose". 
    #                 # If multiple options matched (rare), pick first?
    #                 # Or check which option specifically matched?
    #                 matched_option = ""
    #                 if opts:
    #                     for opt in opts:
    #                         if opt in user_text_lower:
    #                             matched_option = opt 
    #                             break
    #                 else:
    #                      matched_option = unified_text

    #                 combined = f"{matched_option} {target}".strip()
    #                 resolved_items.append(combined)
    #                 any_resolved = True
    #             else:
    #                 # User did NOT answer this part. Keep original target.
    #                 resolved_items.append(target)

    #         if any_resolved:
    #             # Add back ANY unrelated items
    #             final_list = resolved_items + other_items
    #             print(f"🔄 Clarification Resolved! New Items: {final_list}")
                
    #             # Clear state
    #             session["state"]["awaiting"] = None
    #             session["state"]["pending_clarifications"] = None
    #             session["state"]["clarification_others"] = None
    #             session["state"]["clarification_target"] = None 
    #             session["state"]["validation_options"] = None
    #             save_session(user_id, session)
                
    #             # MANUAL OVERRIDE of extracted items
    #             item_descriptions = final_list
    #             extracted["item_descriptions"] = item_descriptions
            
    #         else:
    #             # INVALID ANSWER (User said something totally unrelated)
    #             print(f"⚠️ Clarification did not resolved '{unified_text}' does NOT match expected options. Treating as NEW Request.")
    #             # We do NOT combine. We ABORT the clarification.
    #             session["state"]["awaiting"] = None
    #             session["state"]["pending_clarifications"] = None
    #             session["state"]["clarification_others"] = None
    #             session["state"]["clarification_target"] = None
    #             session["state"]["validation_options"] = None
    #             save_session(user_id, session)
    #             # Proceed with whatever Step 1 extracted from "Air Filter"
    
    if current_state == "clarification_part":
        pending_clarifications = session["state"].get("pending_clarifications", [])
        other_items = session["state"].get("clarification_others", [])
        
        # Legacy check for single item state (migration safety)
        if not pending_clarifications and session["state"].get("clarification_target"):
             pending_clarifications = [{"target": session["state"].get("clarification_target"), "valid_options": session["state"].get("validation_options", [])}]

        # SAFETY CHECK: 
        # If user uploaded a VIN (vin_list not empty) OR text is very long (>50 chars),
        # they are likely NOT answering "Upper/Lower" but changing context/uploading document.
        # In this case, we ABORT the clarification and process the new input normally.
        is_context_switch = bool(vin_list) or len(unified_text) > 200
        
        if is_context_switch:
            print(f"⚠️ Context Switch Detected during Clarification (VIN found or long text). Aborting.")
            # Clear state, proceed with 'extracted' as is
            session["state"]["awaiting"] = None
            session["state"]["pending_clarifications"] = None
            session["state"]["clarification_others"] = None
            session["state"]["clarification_target"] = None # Legacy clear
            session["state"]["validation_options"] = None # Legacy clear
            save_session(user_id, session)
            # Flow falls through to normal Step 2 with the NEW extracted entities (e.g. the VIN)
            
        elif pending_clarifications:
            resolved_items = []
            user_text_lower = unified_text.lower()
            any_resolved = False
            
            # Check EACH pending clarification against the user answer
            for pc in pending_clarifications:
                target = pc.get("target")
                opts = pc.get("valid_options", [])
                
                # lenient check
                is_match = False
                if not opts:
                    is_match = True # Fallback if no strict options
                elif any(opt.lower() in user_text_lower for opt in opts):
                    is_match = True
                    
                if is_match:
                    # Combined: "Upper Coolant Hose". 
                    # If multiple options matched (rare), pick first?
                    # Or check which option specifically matched?
                    matched_option = ""
                    if opts:
                        for opt in opts:
                            if opt.lower() in user_text_lower:
                                matched_option = opt 
                                break
                    else:
                         matched_option = unified_text

                    # Cleanly merge target and matched_option without duplicate words (e.g. "Air Filter", not "Air Filter Filter")
                    t_low = target.lower().strip()
                    m_low = matched_option.lower().strip()
                    if t_low in m_low:
                        combined = matched_option
                    elif m_low in t_low:
                        combined = target
                    else:
                        combined = f"{matched_option} {target}".strip()
                    resolved_items.append(combined)
                    any_resolved = True
                else:
                    # User did NOT answer this part. Keep original target.
                    resolved_items.append(target)

            if any_resolved:
                # Add back ANY unrelated items
                final_list = resolved_items + other_items
                print(f"🔄 Clarification Resolved! New Items: {final_list}")
                
                # Clear state
                session["state"]["awaiting"] = None
                session["state"]["pending_clarifications"] = None
                session["state"]["clarification_others"] = None
                session["state"]["clarification_target"] = None 
                session["state"]["validation_options"] = None
                save_session(user_id, session)
                
                # MANUAL OVERRIDE of extracted items
                # Re-normalize the combined items so they respect the alias rules again
                normalized_final_list = gpt._normalize_part_names(final_list)
                print(f"   🔍 [DEBUG] re-normalized after clarification: {normalized_final_list}")
                item_descriptions = normalized_final_list
                extracted["item_descriptions"] = item_descriptions
            
            else:
                # INVALID ANSWER (User said something totally unrelated)
                print(f"⚠️ Clarification did not resolved '{unified_text}' does NOT match expected options. Treating as NEW Request.")
                # We do NOT combine. We ABORT the clarification.
                session["state"]["awaiting"] = None
                session["state"]["pending_clarifications"] = None
                session["state"]["clarification_others"] = None
                session["state"]["clarification_target"] = None
                session["state"]["validation_options"] = None
                save_session(user_id, session)
                # Proceed with whatever Step 1 extracted from "Air Filter"


    # --- STEP 2: HARD LOOKUPS ---
    
    # A. VIN Handling (MOVED UP FOR PERSISTENCE)
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
    print(vin_list)

    # Decode VIN if we have one (or use cached)
    if current_vin:
        # session["vin_details"] = None # TEMPORARY: Clear cache to force re-scrape
        cached_info = session.get("vin_details")
        # Check cache first
        if cached_info and cached_info.get("vin") == current_vin:
            vin_info = cached_info
            print(f"✅ [Cache Hit] Using stored VIN details for {current_vin}: {vin_info}")
        else:
            print(f"🔎 [CatalogService] Decoding VIN {current_vin} via microservice...")
            try:
                decoded = catalog_service.decode_vin(current_vin)
                if decoded and decoded.get("brand") and str(decoded.get("brand")).lower() != "n/a":
                    vin_info = {
                        "vin": current_vin,
                        "brand": decoded.get("brand"),
                        "model": decoded.get("model"),
                        "model_number": decoded.get("model_number"),
                        "year": decoded.get("year"),
                        "engine": decoded.get("engine"),
                        "series": decoded.get("series"),
                        "source": decoded.get("source")
                    }
                    session["vin_details"] = vin_info
                    save_session(user_id, session)
                    print(f"✅ VIN details cached for {current_vin}: {vin_info.get('brand')} {vin_info.get('model')} ({vin_info.get('model_number')})")
                    vin_search_logs.append({"vin": current_vin, "status": "success"})
                else:
                    # Fallback to scraper if catalog microservice did not find details
                    scraper = get_scraper()
                    details = None
                    if scraper:
                        try:
                            details = scraper.get_vehicle_details(current_vin)
                        except Exception as e:
                            print(f"Scraper error: {e}")

                    if details and details.get("brand") and details.get("brand").lower() != "n/a":
                        vin_info = {
                            "vin": current_vin,
                            "brand": details.get("brand"),
                            "model": details.get("name"),
                            "year": details.get("date")
                        }
                        session["vin_details"] = vin_info
                        save_session(user_id, session)
                        print(f"✅ VIN details cached via scraper for {current_vin}")
                        vin_search_logs.append({"vin": current_vin, "status": "success"})
                    else:
                        print(f"⚠️ VIN {current_vin} returned no vehicle details. Clearing vin_info.")
                        vin_info = None
                        vin_search_logs.append({"vin": current_vin, "status": "failure"})
                        
                        try:
                            from datetime import datetime, timezone
                            from app.services.lovable_service import lovable_service
                            ts = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
                            lovable_service.post_chat_logs({
                                "whatsapp_user_id": user_id,
                                "user_message": unified_text,
                                "intent": "system",
                                "bot_response": FAILURE_HANDLING_MESSAGE,
                                "timestamp": ts
                            })
                            lovable_service.post_analytics_events({
                                "whatsapp_user_id": user_id,
                                "event_type": "vin_search",
                                "timestamp": ts,
                                "vin": current_vin if 'current_vin' in locals() else None,
                                "query": unified_text,
                                "part_number": part_numbers[0] if part_numbers else None,
                                "intent": "system",
                                "vin_searches": vin_search_logs,
                                "part_numbers_searched": part_numbers,
                                "item_descriptions_searched": raw_item_descriptions,
                                "parts_found": [],
                                "parts": []
                            })
                        except: pass
                            
                        return FAILURE_HANDLING_MESSAGE
            except Exception as e:
                print(f"⚠️ VIN Decode Warning (non-fatal): {e}")
                vin_search_logs.append({"vin": current_vin, "status": "failure"})
                
                try:
                    from datetime import datetime, timezone
                    from app.services.lovable_service import lovable_service
                    ts = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
                    lovable_service.post_chat_logs({
                        "whatsapp_user_id": user_id,
                        "user_message": unified_text,
                        "intent": "system",
                        "bot_response": FAILURE_HANDLING_MESSAGE,
                        "timestamp": ts
                    })
                    lovable_service.post_analytics_events({
                        "whatsapp_user_id": user_id,
                        "event_type": "vin_search",
                        "timestamp": ts,
                        "vin": current_vin if 'current_vin' in locals() else None,
                        "query": unified_text,
                        "part_number": part_numbers[0] if part_numbers else None,
                        "intent": "system",
                        "vin_searches": vin_search_logs,
                        "part_numbers_searched": part_numbers,
                        "item_descriptions_searched": raw_item_descriptions,
                        "parts_found": [],
                        "parts": []
                    })
                except: pass
                
                return FAILURE_HANDLING_MESSAGE

     # --- AMPIGUITY CHECK (Mid-Step) ---
    # Only if we are NOT already in a clarification loop (which we just handled or cleared)
    if item_descriptions and current_state != "clarification_part" and current_vin:
        # Call GPT to detect ambiguity dynamically
        ambiguity_result = gpt.detect_ambiguity(item_descriptions)
        
        clarifications = ambiguity_result.get("clarifications", []) # Expecting list
        
        if ambiguity_result.get("is_ambiguous") and clarifications:
            # Combine Questions
            questions = []
            pending_clarifications = []
            
            # Identify all targets involved
            # Identify all targets involved using FUZZY MATCHING logic
            # Because GPT might return "tie rod" when the list has "tie rod steering rod"
            
            # 1. Map each clarification back to an index in item_descriptions
            clarification_indices = set()
            
            final_clarifications = []
            
            for c in clarifications:
                 target_gpt = c["target_item"]
                 
                 # Find best match in item_descriptions
                 best_match_idx = -1
                 best_match_len = 0
                 
                 for idx, item in enumerate(item_descriptions):
                     # If GPT target is substring of Item (e.g. 'tie rod' in 'tie rod steering') -> Match
                     # OR Item is substring of Target -> Match
                     if target_gpt.lower() in item.lower() or item.lower() in target_gpt.lower():
                         # Pick the longest match if multiple? usually just first valid is fine.
                         if len(item) > best_match_len:
                             best_match_idx = idx
                             best_match_len = len(item)
                
                 if best_match_idx != -1:
                     clarification_indices.add(best_match_idx)
                     # Update the target to be the REAL item name, not just what GPT said
                     c["target_item"] = item_descriptions[best_match_idx]
                     final_clarifications.append(c)
                 else:
                     print(f"⚠️ Could not map GPT target '{target_gpt}' to any item. Ignoring.")
            
            if not final_clarifications:
                return "Ambiguity detected but could not resolve target items."

            # 2. Identify NOT ambiguous terms (indices not in set)
            other_items = [item for i, item in enumerate(item_descriptions) if i not in clarification_indices]
            
            questions = []
            pending_clarifications = []
            seen_questions = set()  # Deduplicate identical clarification questions

            for c in final_clarifications:
                 target = c.get("target_item")
                 q_text = c.get("question")
                 opts = c.get("valid_options", [])
                 
                 # --- DEDUPLICATION ---
                 # Same question text (e.g. two alias expansions both asking "Front or Rear?")
                 # should only produce ONE question.
                 question_key = q_text.lower().strip()
                 if question_key in seen_questions:
                     # Already have this question — skip duplicate
                     continue
                 seen_questions.add(question_key)

                 # Output: "For the <rule text>" e.g. "For the Brake pads - Front or Rear"
                 opts_str = " or ".join(opts) if opts else ""
                 if opts_str and not any(opt.lower() in q_text.lower() for opt in opts[:2]):
                     full_q = f"For the {target} - {q_text} ({opts_str})"
                 else:
                     full_q = f"For the {target} - {q_text}"
                 questions.append(full_q)
                 pending_clarifications.append({
                     "target": target,
                     "valid_options": opts
                 })
            
            combined_question_text = "\n".join(questions)
            if user_lang != "en":
                try:
                    combined_question_text = gpt.translation_service.from_base_language(combined_question_text, user_lang)
                except Exception as e:
                    print(f"⚠️ Error translating clarification question: {e}")
            print(f"🛑 Ambiguity Detected via GPT. Asking: {combined_question_text}")
            
            # Save State
            session["state"]["awaiting"] = "clarification_part"
            session["state"]["pending_clarifications"] = pending_clarifications
            session["state"]["clarification_others"] = other_items 
            save_session(user_id, session)
            
            # Immediate Return
            return combined_question_text


    # B. Part Search (MOVED UP - INDEPENDENT FLOW)
    parts_found = []
    missing_pns = []
    
    # 1. Search by Part Number (Highest Priority)
    if part_numbers:
        db_results = search_parts_in_db(part_numbers, tier=user_tier)
        in_stock_results = [p for p in db_results if int(p.get("stock") or 0) > 0]
        parts_found.extend(in_stock_results)
        
        # Calculate missing PNs
        found_pns_set = set()
        for p in in_stock_results:
             found_pns_set.add(normalize_part_number(p.get('part_number', '')))
             if p.get('oem_number'):
                 found_pns_set.add(normalize_part_number(p['oem_number']))
             if p.get('tag'):
                 found_pns_set.add(normalize_part_number(p['tag']))
             if p.get('raw_part_number'):
                 found_pns_set.add(normalize_part_number(p['raw_part_number']))

        missing_pns = []
        for pn in part_numbers:
            pn_norm = normalize_part_number(pn)
            matched = any(pn_norm == fn or pn_norm in fn or fn in pn_norm for fn in found_pns_set if fn)
            if not matched:
                missing_pns.append(pn)


    
    # --- STEP 2C: BRAND VALIDATION ---
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
        
        # LOGIC CHANGE: We check support, but if we found PARTS in the DB, we allow it.
        if parts_found:
            is_supported = True
        if brand == "n/a":
            if missing_pns:
                is_supported = True
            else:
                return "At the moment, we are unable to clearly understand or access your requirement.\n Our team will review the details and reach out to you shortly to provide the necessary assistance.😊"
        
        if not is_supported:
            if parts_found:
                print(f"⚠️ Brand {brand} is unsupported, but VALID PARTS were found in DB. Allowing flow to proceed.")
                # We do NOT clear the session here because the user might just be buying a generic part
                # or we have it in stock despite the car model.
            else:
                print(f"⛔ Unsupported Brand: {brand}. Rejecting (Not a Warning Light).")
                
                # --- CLEAR SESSION FOR UNSUPPORTED VIN ---
                # To prevent "poisoned" sessions where user gets stuck with a bad VIN
                if session.get("entities"):
                    session["entities"]["vin"] = None
                session["vin_details"] = None
                save_session(user_id, session)
                print(f"🧹 Cleared session VIN data for user {user_id}")
                u_b = vin_info.get("brand") if vin_info else "unsupported"
                rejection_msg = f"""We do not support {u_b} car parts \n
We supply Genuine and Aftermarket spare parts for the following brands: \n
•  BMW  
•  Mercedes Benz  
•  Rolls Royce  
•  Mini Cooper  
•  Honda  
                \nFor more details please contact us on +971 54 751 6365"""
                if user_lang != "en":
                    try:
                        rejection_msg = gpt.translation_service.from_base_language(rejection_msg, user_lang)
                    except Exception as e:
                        print(f"⚠️ Error translating rejection message: {e}")
                return rejection_msg


    # 2. Search by Name (Catalog Search - Depends on VIN)
    if current_vin and item_descriptions:
        catalog_matches = search_catalog_by_name(current_vin, item_descriptions, vin_info=vin_info, tier=user_tier)
        parts_found.extend(catalog_matches)
    elif not current_vin and item_descriptions and not parts_found and not part_numbers:
        # No VIN: use advanced search (same as website search bar) for each description
        for desc in item_descriptions:
            q_res = inventory_service.advanced_search(desc, tier=user_tier, limit=5)
            if q_res.get("items"):
                parts_found.extend(q_res["items"])

    # 3. Fallback for mixed query (e.g. "129 oil filter") when individual PN search had 0 items
    if part_numbers and item_descriptions and not parts_found:
        combined_query = f"{' '.join(part_numbers)} {' '.join(item_descriptions)}"
        q_res = inventory_service.advanced_search(combined_query, tier=user_tier, limit=5)
        if q_res.get("items"):
            in_stock_items = [it for it in q_res["items"] if int(it.get("stock") or 0) > 0]
            if in_stock_items:
                parts_found.extend(in_stock_items)
                missing_pns = []

    # 4. Fallback: if part_numbers were provided but still nothing found, try advanced search as last resort
    if part_numbers and not parts_found:
        for pn in part_numbers:
            q_res = inventory_service.advanced_search(pn, tier=user_tier, limit=10)
            if q_res.get("items"):
                in_stock_items = [it for it in q_res["items"] if int(it.get("stock") or 0) > 0]
                if in_stock_items:
                    parts_found.extend(in_stock_items)
                    pn_norm = normalize_part_number(pn)
                    missing_pns = [m for m in missing_pns if normalize_part_number(m) != pn_norm]

    # --- STEP 3: CONTEXT & CHUNKING ---
    replies = []
    machine_payloads = []
    
    CHUNK_SIZE = 10 # Split large lists into smaller messages  
    # print(parts_found)          
    total_parts = len(parts_found)
    print(f"DEBUG: Chunking Check - Total Parts: {total_parts} | Chunk Size: {CHUNK_SIZE}")
    
    if total_parts > CHUNK_SIZE:
        print(f"⚠️ Large result set ({total_parts} items). Splitting into chunks of {CHUNK_SIZE}.")
        
        part_chunks = [parts_found[i:i + CHUNK_SIZE] for i in range(0, total_parts, CHUNK_SIZE)]
        total_chunks = len(part_chunks)
        
        for i, chunk in enumerate(part_chunks):
            chunk_context = {
                "user_id": user_id,
                "vin_info": vin_info,
                "parts_found": chunk,
                "missing_pns": missing_pns if (i == total_chunks - 1) else [], # Only show missing in last chunk
                "session_summary": f"User ID: {user_id}. Stored VIN: {current_vin}",
                "extracted_entities": extracted,
                "preferred_area": preferred_area,
                "is_warning_light": is_warning_light, # PASS THE FLAG
                "skip_intro": (i >= 0), # Skip intro for 2nd+ message
                "failed_vin_decode": True if (current_vin and not vin_info) else False,
                "user_lang": user_lang
            }
            
            print(f"   🔄 Processing Chunk {i+1}/{total_chunks} ({len(chunk)} items)...")
            gpt_result = gpt.run_super_intent(unified_text, chunk_context)
            
            replies.append(gpt_result.get("whatsapp_text", "..."))
            machine_payloads.append(gpt_result.get("machine_payload", {}))
            
    else:
        # Standard Single Call
        context_data = {
            "user_id": user_id,
            "vin_info": vin_info,
            "parts_found": parts_found,
            "missing_pns": missing_pns, 
            "session_summary": f"User ID: {user_id}. Stored VIN: {current_vin}",
            "extracted_entities": extracted,
            "preferred_area": preferred_area,
            "is_warning_light": is_warning_light, # PASS THE FLAG
            "skip_intro": True,
            "failed_vin_decode": True if (current_vin and not vin_info) else False,
            "user_lang": user_lang
        }
        gpt_result = gpt.run_super_intent(unified_text, context_data)
        
        replies.append(gpt_result.get("whatsapp_text", "..."))
        machine_payloads.append(gpt_result.get("machine_payload", {}))

    # --- STEP 5: ACTIONS (Backend Side Effects) ---
    final_payload = machine_payloads[0] if machine_payloads else {}
    action = final_payload.get("action")
    
    if action == "escalate":
        # Handle escalation (e.g. notify admin, flag lead)
        pass
        
    # --- STEP 6: RECORD QUERY FOR DASHBOARD STATS ---
    try:
        lead_service.create_lead(
            whatsapp_user_id=user_id,
            query_text=unified_text,
            intent=final_payload.get("intent", "system")
        )
    except Exception as e:
        print(f"⚠️ Failed to log query to Lead table: {e}")
    
    # Return list if we have multiple replies, otherwise string (for backward compatibility)
    if len(replies) == 1:
        bot_response = replies[0]
    else:
        bot_response = str(replies)
        
    try:
        from datetime import datetime, timezone
        from app.services.lovable_service import lovable_service
        ts = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
        intent_val = final_payload.get("intent", "system") if 'final_payload' in locals() and final_payload else "system"
        
        lovable_service.post_chat_logs({
            "whatsapp_user_id": user_id,
            "user_message": unified_text,
            "intent": intent_val,
            "bot_response": bot_response,
            "timestamp": ts
        })
        
        event_type = "part_search" if part_numbers or raw_item_descriptions else "vin_search"
        
        parts_list = parts_found if 'parts_found' in locals() else []
        
        lovable_service.post_analytics_events({
            "whatsapp_user_id": user_id,
            "event_type": event_type,
            "timestamp": ts,
            "vin": vin_search_logs[0].get('vin') if vin_search_logs else None,
            "part_number": part_numbers[0] if part_numbers else None,
            "query": unified_text,
            "intent": intent_val,
            "vin_searches": vin_search_logs,
            "part_numbers_searched": part_numbers,
            "item_descriptions_searched": raw_item_descriptions,
            "parts_found": parts_list,
            "parts": parts_list
        })
    except Exception as e:
        print(f"Failed to post final analytics: {e}")

    if len(replies) == 1:
        return replies[0]
    return replies