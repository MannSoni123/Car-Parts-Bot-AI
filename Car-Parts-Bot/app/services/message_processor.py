from app.extensions import db
from app.models import Stock, User, PartSearchLog
from app.services.gpt_service import GPTService
from app.services.scraper.partsouq_xpath_scraper import get_scraper
from app.session_store import get_session, save_session, set_vin, log_failed_vin
from app.services.lead_service import lead_service
from sqlalchemy import func, or_
import re

gpt = GPTService()

# --- CONSTANTS ---
# CLARIFICATION_RULES Removed - Now Dynamic via GPT

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
    normalized_tag_column = func.upper(Stock.tag)
    # Apply same stripping to tag column for consistent matching
    for ch in ['-', ' ', '+', '%', '$', '_', '/', '.', ',', ':', ';', '#', '@', '!', '*',
                        '(', ')', '?', '&', '=', '<', '>', '~', '`', '|', '^', '"', "'",
                        '~', '´', '“', '”', '‘', '’', '–', '—', '•', '…', '{', '}', '[', ']']:
        normalized_tag_column = func.replace(normalized_tag_column, ch, '')

    results = []
    # 1. Exact Match via Normalization (Check BOTH Part Number and Tag)

    # 1. Exact Match via Normalization
    matches = db.session.query(Stock).filter(
        or_(
            normalized_db_column.in_(cleaned_pns),
            normalized_tag_column.in_(cleaned_pns)
        )
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
        if p.qty and p.qty > 0 :
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
                
                # --- GPT FILTER ---
                # Filter out unrelated parts from the diagram (e.g. screws, clamps)
                parts_list = gpt.filter_parts_by_relevance(parts_list, name)
                print(f"   --> Filtered to {len(parts_list)} relevant parts.")
                # ------------------

                if not parts_list:
                     results.append({"status": "empty", "message": "Not in Catalog (Filtered)"})
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
                    for p in parts_list:
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

def search_db_by_tag(descriptions: list) -> list:
    """
    Search database for Tags matching the extracted item descriptions.
    Input: ["Wiper Blade 22\"", "Oil Filter"]
    """
    if not descriptions:
        return []

    print(f"   🔍 [DB Search] Checking Tags for descriptions: {descriptions}")
    results = []
    
    # We use a LIKE search for each description against the 'tag' column
    # Since 'tag' can be 'WIPER BLADE 22"', we want to match if user said 'Wiper Blade 22"'
    
    # Logic: Search where Tag contains the description string (case insensitive)
    # OR where Description contains the Tag (fuzzy) -- sticking to simple LIKE per description for now.
    
    unique_matches = {}

    for desc in descriptions:
        # Clean up description suitable for search
        # E.g. "Wiper Blade 22"" -> "%WIPER%BLADE%22%" ?? Or just simple string matching?
        # Let's try direct ILIKE first.
        search_term = f"%{desc}%"
        
        matches = db.session.query(Stock).filter(
             Stock.tag.ilike(search_term)
        ).limit(10).all() # Limit to prevent explosion
        
        for m in matches:
            if m.id not in unique_matches:
                 unique_matches[m.id] = {
                    "part_number": m.part_number,
                    "brand": m.brand,
                    "name": m.item_desc or m.tag, # Use Desc if avail, else Tag
                    "price": m.price,
                    "qty": m.qty,
                    "tag": m.tag,
                    "status": "in_stock" if m.qty > 0 else "out_of_stock",
                    "source": "localdb_tag"
                }

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
    
    # --- SIMPLIFIED WORKSHOP LOGIC ---
    preferred_area = None
    workshop_keywords = ["workshop", "suggest workshop", "recommend workshop", "garage"]
    is_workshop_request = any(kw in unified_text.lower() for kw in workshop_keywords)
    
    if is_workshop_request:
        print(f"🛠️ Workshop Request Detected. Setting state: workshop_area")
        session["state"]["awaiting"] = "workshop_area"
        save_session(user_id, session)
    
    elif session.get("state", {}).get("awaiting") == "workshop_area":
        # Capture the area and clear the state
        preferred_area = unified_text.strip()
        print(f"📍 Preferred Area Captured: {preferred_area}")
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
            print("This is getting issue")
            # Not cached or new VIN -> Scrape
            scraper = get_scraper()
            print(f"IT IS GOING TO FIND THE VIN {current_vin}")
            
            # --- TRACK VIN SEARCH ---
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
                        # Cache it ONLY if VIN was actually found in catalog
                        if vin_info.get("brand") and vin_info["brand"].lower() != "n/a":
                            session["vin_details"] = vin_info
                            save_session(user_id, session)
                            print(f"✅ VIN details cached for {current_vin}")
                            vin_search_logs.append({"vin": current_vin, "status": "success"})
                        else:
                            print(f"⚠️ VIN {current_vin} returned N/A brand. NOT caching. Clearing vin_info.")
                            vin_info = None  # Don't pass N/A info to GPT
                            vin_search_logs.append({"vin": current_vin, "status": "failure"})
                    else:
                        print("⚠️ VIN Decode returned no details. Proceeding...")
                        vin_search_logs.append({"vin": current_vin, "status": "failure"})
                        
                        try:
                            from datetime import datetime, timezone
                            from app.services.lovable_service import lovable_service
                            ts = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
                            lovable_service.post_chat_logs({
                                "whatsapp_user_id": user_id,
                                "user_message": unified_text,
                                "intent": "system",
                                "bot_response": "Catelog error our team will contact you soon",
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
                            
                        return "Catelog error our team will contact you soon"
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
                            "bot_response": "Catelog error our team will contact you soon",
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
                    
                    return "Catelog error our team will contact you soon"

    # # --- AMPIGUITY CHECK (Mid-Step) ---
    # # Only if we are NOT already in a clarification loop (which we just handled or cleared)
    # if item_descriptions and current_state != "clarification_part" and current_vin:
    #     # Call GPT to detect ambiguity dynamically
    #     ambiguity_result = gpt.detect_ambiguity(item_descriptions)
        
    #     clarifications = ambiguity_result.get("clarifications", []) # Expecting list
        
    #     if ambiguity_result.get("is_ambiguous") and clarifications:
    #         # Combine Questions
    #         questions = []
    #         pending_clarifications = []
            
    #         # Identify all targets involved
    #         # Identify all targets involved using FUZZY MATCHING logic
    #         # Because GPT might return "tie rod" when the list has "tie rod steering rod"
            
    #         # 1. Map each clarification back to an index in item_descriptions
    #         clarification_indices = set()
            
    #         final_clarifications = []
            
    #         for c in clarifications:
    #              target_gpt = c["target_item"]
                 
    #              # Find best match in item_descriptions
    #              best_match_idx = -1
    #              best_match_len = 0
                 
    #              for idx, item in enumerate(item_descriptions):
    #                  # If GPT target is substring of Item (e.g. 'tie rod' in 'tie rod steering') -> Match
    #                  # OR Item is substring of Target -> Match
    #                  if target_gpt.lower() in item.lower() or item.lower() in target_gpt.lower():
    #                      # Pick the longest match if multiple? usually just first valid is fine.
    #                      if len(item) > best_match_len:
    #                          best_match_idx = idx
    #                          best_match_len = len(item)
                
    #              if best_match_idx != -1:
    #                  clarification_indices.add(best_match_idx)
    #                  # Update the target to be the REAL item name, not just what GPT said
    #                  c["target_item"] = item_descriptions[best_match_idx]
    #                  final_clarifications.append(c)
    #              else:
    #                  print(f"⚠️ Could not map GPT target '{target_gpt}' to any item. Ignoring.")
            
    #         if not final_clarifications:
    #             return "Ambiguity detected but could not resolve target items."

    #         # 2. Identify NOT ambiguous terms (indices not in set)
    #         other_items = [item for i, item in enumerate(item_descriptions) if i not in clarification_indices]
            
    #         questions = []
    #         pending_clarifications = []

    #         for c in final_clarifications:
    #              target = c.get("target_item")
    #              q_text = c.get("question")
    #              opts = c.get("valid_options", [])
                 
    #              questions.append(f"For the *{target}*, {q_text}")
    #              pending_clarifications.append({
    #                  "target": target,
    #                  "valid_options": opts
    #              })
            
    #         combined_question_text = "\n".join(questions)
    #         print(f"🛑 Ambiguity Detected via GPT. Asking: {combined_question_text}")
            
    #         # Save State
    #         session["state"]["awaiting"] = "clarification_part"
    #         session["state"]["pending_clarifications"] = pending_clarifications
    #         session["state"]["clarification_others"] = other_items 
    #         save_session(user_id, session)
            
    #         # Immediate Return
    #         return combined_question_text
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

                 # Output: "For the <rule text>" e.g. "For the Brake pads  - Front or Rear"
                 questions.append(f"For the {target} - {q_text}")
                 pending_clarifications.append({
                     "target": target,
                     "valid_options": opts
                 })
            
            combined_question_text = "\n".join(questions)
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
        db_results = search_parts_in_db(part_numbers)
        parts_found.extend(db_results)
        
        # Calculate missing PNs
        found_pns_set = set()
        for p in db_results:
             found_pns_set.add(normalize_part_number(p.get('part_number', '')))
             if p.get('tag'):
                 found_pns_set.add(normalize_part_number(p['tag']))

        missing_pns = [pn for pn in part_numbers if normalize_part_number(pn) not in found_pns_set]


    
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
                return f"""We do not support {u_b} car parts \n
We supply Genuine and Aftermarket spare parts for the following brands: \n
•  BMW  
•  Mercedes Benz  
•  Rolls Royce  
•  Mini Cooper  
•  Honda  
                \nFor more details please contact us on +971 54 751 6365"""


    # 2. Search by Name (Catalog Search - Depends on VIN)
    if current_vin and item_descriptions:
        # Only search catalog if we didn't match via explicit Part Number? 
        # Or always? Requirement: "If item_descriptions exist -> search catalog".
        # We'll search and append.
        catalog_matches = search_catalog_by_name(current_vin, item_descriptions)
        
        # ERROR CHECK: If ANY catalog match is an error, ABORT immediately.
        # if any(p.get("status") == "error" for p in catalog_matches):
        #      print(f"🛑 Catalog Search Failed. Aborting flow for User {user_id}")
        #      return "Catelog error our team will contact you soon"
             
        parts_found.extend(catalog_matches)

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
                "failed_vin_decode": True if (current_vin and not vin_info) else False
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
            "failed_vin_decode": True if (current_vin and not vin_info) else False
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