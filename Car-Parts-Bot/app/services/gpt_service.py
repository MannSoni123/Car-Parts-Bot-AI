
"""
GPT/OpenAI service for natural language understanding and response formatting.
Handles multilingual queries and generates conversational responses via Super Intent.
"""

from typing import Any, Dict, List, Optional
from openai import OpenAI
from flask import current_app
from .translation_service import TranslationService
import json
import time
import re
from ..models import IntentPrompt

class GPTService:
    # Metrics for Admin API compatibility
    response_times = []
    correct_intent_predictions = 0
    total_intent_checks = 0
    incorrect_intent_predictions = 0

    def __init__(self):
        self._client = None
        self.translation_service = TranslationService()

    @property
    def client(self):
        if not self._client:
            # Lazy init within app context
            try:
                api_key = current_app.config.get("OPENAI_API_KEY")
                if api_key:
                    self._client = OpenAI(api_key=api_key)
            except RuntimeError:
                # Still outside context? Return None or handle
                return None
        return self._client

    def run_super_intent(
        self,
        user_text: str,
        context_data: dict,
    ) -> dict:
        """
        SINGLE Universal Entry Point for GPT.
        Fetches 'super_intent' prompt from DB and injects context.
        """
        if not self.client:
            return {
                "whatsapp_text": "System error: OpenAI client not configured.",
                "machine_payload": {"action": "escalate", "error": "no_client"}
            }

        # 1. Fetch Dynamic Prompt from Lovable API
        from app.services.lovable_service import lovable_service
        class PromptWrapper:
            def __init__(self, d):
                self.vip_numbers = d.get("vip_numbers", "")
                self.prompt_text = d.get("prompt_text", "")
                self.reference_text = d.get("reference_text", "")
                self.clarification_rules = d.get("clarification_rules", "")
                self.parts_alias_text = d.get("parts_alias_text", "")

        prompt_data = lovable_service.get_prompt("system")
        prompt_row = PromptWrapper(prompt_data) if prompt_data else None
        
        # --- VIP & MASKING LOGIC (Early Execution) ---
        user_id = str(context_data.get("user_id", ""))
        
        # Default VIPs (Hardcoded Backup)
        vip_list = [] 
        
        # Helper to strip non-digits
        import re
        def clean_phone(p):
            return re.sub(r'\D', '', str(p)) if p else ""

        # Load Dynamic VIPs
        if prompt_row and prompt_row.vip_numbers:
            # Split by comma or newline
            raw_vips = re.split(r'[,\n]', prompt_row.vip_numbers)
            dynamic_vips = [clean_phone(x) for x in raw_vips if x.strip()]
            vip_list.extend(dynamic_vips)
            
        # Check if user is VIP (Compare cleaned versions)
        # We clean user_id too just in case it comes with format
        clean_user_id = clean_phone(user_id)
        is_vip = any(vip in clean_user_id for vip in vip_list if vip)
        print("VIP Status:", " 👑 VIP 👑" if is_vip else " ❌ Non-VIP")
        
        parts = context_data.get('parts_found') or []
        is_warning_light = context_data.get('is_warning_light', False)
        
        if not is_vip:
            # Mask Catalog Part Numbers for non-VIPs
            for p in parts:
                if p.get("brand") == "OEM/Catalog":
                    p["part_number"] = "Call for Details"

        base_system_prompt = ""
        
        if prompt_row and prompt_row.prompt_text:
            base_system_prompt = prompt_row.prompt_text
            if prompt_row.reference_text:
                # DEBUG: Print first 500 chars to verify content
                print(f"📄 [SuperIntent DEBUG] Reference File is adding ....")

                base_system_prompt += f"\n\n=== REFERENCE MATERIAL ===\n{prompt_row.reference_text}\n"
                
                # STRICT INSTRUCTION TO USE REFERENCE
                base_system_prompt += "\n\nCRITICAL: You are provided with 'REFERENCE MATERIAL' above. YOU MUST ANSWER ONLY USING THIS MATERIAL for any questions about warning lights or symbols. DO NOT use your internal training data. If the answer is not in the material, say 'Information not found in reference'."
                base_system_prompt += "\n\nCRITICAL GLOBAL RULE: NEVER output the 'REFERENCE MATERIAL' text itself. Only use it to derive answers. Do not copy-paste large sections."
                print(f"📚 [SuperIntent] Reference material appended (length: {len(prompt_row.reference_text)} chars).")
            else:
                print(f"ℹ️ [SuperIntent] No reference material found/attached for this intent.")
        else:
            print("⚠️ [SuperIntent] Database lookup for 'super_intent' failed. Using HARDCODED fallback. No logs/reference available.")
            # FALLBACK if DB entry missing (Safety)
            base_system_prompt = """
                ROLE:
                You are an advanced AI assistant for a WhatsApp-based Car Parts bot.
                Your goal is to help users find car parts accurately and professionally.
                BEHAVIOR:
                - Act like a human sales agent.
                - Use provided "Hard Business Data". DO NOT GUESS.
                - Professional, concise tone.
                """

        # 2. Construct Context Block
        context_block = f"""
            INPUT CONTEXT:
            User Text: "{user_text}"

            Knowledge/State:
            - Decoded VIN: {context_data.get('vin_info') or 'None'}
            - Matched Parts (DB): {json.dumps(parts, default=str)}
            - Session Context: {context_data.get('session_summary', 'None')}
            - Preferred Area (for Workshop): {context_data.get('preferred_area') or 'None'}

            OUTPUT FORMULA (JSON ONLY):
            {{
            "whatsapp_text": "...",
            "machine_payload": {{
                "intent": "system",
                "action": "quote" | "ask_clarify" | "info_only" | "escalate",
                "vin": "{(context_data.get('vin_info') or {}).get('vin') or ''}",
                "confidence": 1.0
            }}
            }}
            """
        
        # 0. Detect Language
        detected_lang = "en"
        try:
            detected_lang = self.translation_service.detect_language(user_text)
        except Exception:
            pass

        # 3. Combine
        final_system_message = base_system_prompt + "\n\n" + context_block

        # --- RE-INJECT STRICT INSTRUCTION AT THE VERY END (RECENCY BIAS) ---
        if "=== REFERENCE MATERIAL ===" in base_system_prompt:
             final_system_message += """
             
             CRITICAL INSTRUCTION (OVERRIDE ALL PRIOR KNOWLEDGE):
             1. You contain a section called 'REFERENCE MATERIAL' above.
             2. YOUR INTERNAL KNOWLEDGE IS BANNED. You often hallucinate or provide generic answers. TRUST ONLY THE REFERENCE MATERIAL.
             3. COMPARE the User's Input (visual description or text) with the descriptions in the 'REFERENCE MATERIAL'.
             4. If the User's description is about a warning light, you MUST find an EXACT MATCH in the reference material.
             5. Do NOT say "it looks like X but usually means Y". Say EXACTLY what the Reference says it is.
             6. EXCEPTION: If the user is asking for a CAR PART (e.g. Brake Pads, Filter) AND there are item(s) in the 'Matched Parts (DB)' list provided in the Context, you MUST IGNORE the Reference Material and output the parts found.
             7. Only say "Not found in reference" if the user is asking a specific question that should be in the reference but isn't there, and NO parts were found in the DB.
             """

        # --- SIMPLIFIED WORKSHOP OVERRIDE ---
        if context_data.get("preferred_area"):
            final_system_message += f"""
            
            CRITICAL WORKSHOP INSTRUCTION:
            1. THE USER HAS PROVIDED THE AREA: "{context_data.get('preferred_area')}".
            2. You MUST NOT ask for the area again.
            3. IGNORE CAR BRAND FILTERS.
            4. SHOW ALL APPROVED WORKSHOPS from the 'Approved Workshop List' that are located in the area: "{context_data.get('preferred_area')}".
            """

        # --- DEBUG / STRICT MODE OVERRIDES ---
        # Analyze parts_found for strict status flags
        # parts already defined above
        strict_instructions = []

        # Extract user intent entities early for conditional logic
        extracted = context_data.get("extracted_entities", {})
        user_pns = extracted.get("part_numbers", [])
        user_descs = extracted.get("item_descriptions", [])
        user_vins = extracted.get("vin_list", [])
        
        # --- CALCULATION: SUPPRESS BRANDING (Early) ---
        # 1. Skip Intro (from context, e.g. chunking)
        should_skip_intro = context_data.get("skip_intro", False)
        
        # 2. Suppress Branding (User Request: PN OR Name OR VIN -> No "I am CarPartsAI" footer)
        has_pn = bool(user_pns)
        has_desc = bool(user_descs)
        # Check if User PROVIDED a VIN in this message (not just session context)
        has_new_vin = bool(user_vins)
        
        should_suppress_branding = (has_pn or has_desc or has_new_vin)
        
        if should_suppress_branding:
             print("   🔇 [SuperIntent] Suppressing Branding/Footer (Entity Detected).")
             # Inject Strict Instruction for FIRST GPT Call
             final_system_message += """
             \n\nCRITICAL FORMATTING RULE:
             The user is already in a conversation. 
             1. DO NOT add any self-introduction (e.g. "I am CarPartsAI"). However, if the user greeted you (e.g., "Hello", "नमस्ते", "Bonjour"), you MUST start your response with a polite greeting in the same language.
             2. DO NOT add any generic footer or list of supported brands (e.g. "We supply Genuine and Aftermarket...").
             3. DO NOT add "Please share the VIN..." if you are already providing a list of parts.
             Just provide the requested information/list directly.
             """
        
        # --- VIP OVERRIDE ---
        # user_id / is_vip already defined above
        
        if is_vip:
            print(f" [SuperIntent] VIP Access for {user_id}. Enforcing Detailed Quote Mode.")
            # VIP Rules: Always show part numbers, technical details, full list.
        
        has_out_of_stock = any(p.get("status") == "out_of_stock" for p in parts)
        has_error = any(p.get("status") == "error" for p in parts)
        has_empty = any(p.get("status") == "empty" for p in parts)
        
        # --- MISSING VIN FOR PARTS REQUEST ---
        # If user asks for parts (by name) but NO VIN is known, we must ask for VIN.
        # This overrides Reference Material checks for "unknown" items.
        vin_info = context_data.get('vin_info')
        should_ask_vin = False
        if user_descs and not vin_info and not parts and not user_pns:
             # Only trigger if we have descriptions but no VIN and no results.
             # (If user provided Part Number, we might have matched it in DB without VIN, so we check user_pns too)
             should_ask_vin = True
             print(f"   🚫 [SuperIntent] User asked for parts {user_descs} but NO VIN. Enforcing VIN Request.")
             strict_instructions.append(f"CRITICAL: The user is asking for car parts (e.g. '{user_descs[0]}') but has NOT provided a VIN. You MUST politely ask for the VIN number to proceed. Do NOT use the Reference Material. Do NOT say 'Information not found'. Just ask for the VIN.")
             strict_instructions.append("CRITICAL: When asking for the VIN, do NOT output the list of supported brands or the phrase 'We supply Genuine and Aftermarket spare parts'. Just ask for the VIN concisly.")

        # --- SUPPRESS SALES PITCH FOR INFO ONLY ---
        # If warning light OR (no parts found AND no VIN needed AND not already suppressed)
        is_info_only = is_warning_light
        
        if is_info_only:
             print("   ℹ️ [SuperIntent] Info/Warning Light detected. Suppressing Sales Pitch.")
             strict_instructions.append("CRITICAL: This is an INFORMATIONAL response.")
             strict_instructions.append("1. DO NOT include the 'We supply Genuine and Aftermarket parts...' footer.")
             strict_instructions.append("2. DO NOT include the 'I am CarPartsAI' intro.")
             strict_instructions.append("3. STRICTLY USE THE PROVIDED REFERENCE MATERIAL ONLY. Do not use your own training data or internet knowledge.")
             strict_instructions.append("4. Check the Reference Material for an EXACT MATCH to the User's visual description/text.")
             strict_instructions.append("5. If the answer is not in the Reference Material, explicitly say 'Information not found in our reference'.")
             

        has_out_of_stock = any(p.get("status") == "out_of_stock" for p in parts)
        has_error = any(p.get("status") == "error" for p in parts)
        has_empty = any(p.get("status") == "empty" for p in parts)
        failed_vin = context_data.get("failed_vin_decode", False)
        
        # Priority: Failed VIN > Error > Out of Stock > Empty
        if failed_vin:
             strict_instructions.append("CRITICAL: The VIN provided by the user is invalid or not found in the catalog. You MUST inform the user and set the 'whatsapp_text' field exactly to: 'This VIN is not in catalog. Our team will contact you soon.' Do not output or guess any car details or prices.")
        elif has_error:
             strict_instructions.append("CRITICAL: The catalog search FAILED. You MUST set the 'whatsapp_text' field exactly to: 'Our team will contact you soon for catalog failure.' (plus any helpful context). Do not say 'I couldn't find it', say 'Failed to Catalog'.")
        elif has_out_of_stock:
             if user_pns or is_vip:
                 strict_instructions.append("CRITICAL: Parts were found in the catalog but are NOT in the local database. You MUST start the 'whatsapp_text' field with: 'Found in Catalog but Not in Stock'. List the part numbers found but clearly state they are out of stock.")
             else:
                 strict_instructions.append("CRITICAL: Parts were found in the catalog but are NOT in the local database. You MUST start the 'whatsapp_text' field with: 'Found in Catalog but Not in Stock'. List the items found (Name only) but clearly state they are out of stock. Do NOT show Part Numbers.")
        elif has_empty and not any(p.get("price") for p in parts): # Only empty/missing
             strict_instructions.append("CRITICAL: The catalog search returned NO results. You MUST set the 'whatsapp_text' field exactly to: 'There is no item in catalog for this. Our team will contact you soon.'. Do not offer to search again.")

        if len(parts) >= 1:
            strict_instructions.append(f"CRITICAL: {len(parts)} parts have been found in the database matching the user's request. You MUST present these parts (Product Name, Brand, Price, Availability). You SHOULD briefly acknowledge the user's specific issue (e.g. 'I see the door handle is broken') derived from the input before listing the parts.")
            # strict_instructions.append(f"CRITICAL: {len(parts)} parts have been found in the database matching the user's request. You MUST present these parts (Product Name, Brand, Price, Availability). Do NOT ask the user what they are looking for, because the search was successful!")

        # --- MULTIPLE parts enforcement ---
        if len(parts) > 1:
            strict_instructions.append(f"""CRITICAL: {len(parts)} parts were found in the database. 
            The user might have asked for a specific part number, BUT you MUST also show the other {len(parts)-1} related parts (Siblings/Alternatives) found in the database.
            DO NOT FILTER the list. You are a salesman offering OPTIONS.
            You MUST output the details for ALL {len(parts)} parts found. List them all.""")

        # --- MULTILINGUAL ENFORCEMENT ---
        if detected_lang != "en":
            strict_instructions.append(f"CRITICAL: The user is speaking language code '{detected_lang}'. You MUST reply ENTIRELY in that language, except for Technical Terms (Part Names/Numbers) which can remain in English. Do NOT mix languages unnecessarily.")
        
        if strict_instructions:
            # print(f"   🚨 [SuperIntent] Strict Instructions Triggered: {len(strict_instructions)} rules.")
            # print(f"   🚨 Rules: {strict_instructions}")
            final_system_message += "\n\n" + "\n".join(strict_instructions)

        # --- PART NUMBER SPECIFIC FORMATTING ---
        # User Rule: if user provide part number then in reply it also include part number as per item in reply
        # means: brand, price, part number, availability. Only if user only provide part number.
        
        # Use a simple heuristic: If PNs exist, we want this strict table format for clarity.
        # OR if VIP user.
        
        # Define is_supported_brand locally for prompt logic
        vin_data = context_data.get('vin_info') or {}
        brand_name = vin_data.get("brand", "").lower()
        supported_list = ["bmw", "mercedes", "benz", "rolls royce", "mini", "honda"]
        is_supported_brand = any(s in brand_name for s in supported_list)

        # if user_pns or is_vip:
        if (user_pns or (is_vip and (user_descs or len(parts) > 0))) and not should_ask_vin:
            # print("we are breaking here")
            missing_pns = context_data.get("missing_pns", [])
            print(f"   🔢 [SuperIntent] User provided Part Numbers OR VIP. Enforcing EXTENDED FORMAT. Found: {len(parts)}, Missing: {len(missing_pns)}")
            
            # CASE A: Some parts found
            if len(parts) > 0:
                 format_instruction = f"""
                 CRITICAL: {'VIP REQUEST RECEIVED.' if is_vip else 'The user searched by PART NUMBER.'}
                 
                 CRITICAL: {'VIP REQUEST RECEIVED.' if is_vip else 'The user searched by PART NUMBER.'}
                 
                 {f'''
                 LOGIC: Check the brand in 'vin_info' ({context_data.get('vin_info', {}).get('brand', 'Unknown')}).
                 Supported Brands: BMW, Mercedes, Benz, Rolls Royce, Mini, Honda.
                 
                 IF BRAND IS SUPPORTED:
                    1. Start with:
                    "Vehicle details for your reference are listed below:
                    Brand: [Brand]
                    Model: [Model]
                    Year: [Year]"
                    
                    Then add a blank line.
                    Then say: "[Optional Greeting if user greeted you] Here are the available options:"

                 IF BRAND IS NOT SUPPORTED (e.g. Chevrolet, Toyota, etc.):
                    1. Start with:
                    "[Optional Greeting if user greeted you] We do not support [Insert Brand Name] cars, but here are the details for the part you requested:"
                    2. DO NOT show the "Vehicle details" block (Brand/Model/Year). Skip it.
                 ''' if context_data.get('vin_info') else '1. Start with: "[Optional Greeting if user greeted you] Here are the available options:"'}

                 2. You MUST format the output for found parts EXACTLY as follows for each item (Use a Numbered List):
                 
                 [Number]. *[Part Name]*
                    - Brand: [Insert Actual Brand Name]
                    - Price: [Insert Actual Price]
                    - Part Number: [Insert Actual Part Number]
                    - Availability: [Insert In Stock / Out of Stock]
                    {' - Quantity: [Insert Quantity]' if is_vip else ''}
                 
                 IMPORTANT: Replace the terms in brackets [] with the REAL data from the found parts context. Do NOT use the text "Brand Name" or "Price" literally.
                 MANDATORY: You MUST include the 'Part Number' line for EVERY item.
                 Do not summarize. Show this block for EVERY matching part found.
                 """
                 
                 if missing_pns:
                     format_instruction += f"\n\n3. FOR MISSING PARTS: The following part numbers were NOT found in the database: {', '.join(missing_pns)}.\n   You MUST add this exact line ONCE inside your 'whatsapp_text':\n   'For part number {', '.join(missing_pns)} our team will contact you soon.'"

                 final_system_message += "\n\n" + format_instruction
            
            
            # CASE B: NO parts found at all
            elif len(parts) == 0:
                 # Standard logic even for VIP if nothing found
                 
                 # Prepare the Vehicle Details Block (reused logic)
                 vehicle_block = ""
                 if context_data.get('vin_info'):
                     if is_supported_brand:
                         vehicle_block = f"""
                         Vehicle details for your reference are listed below:
                         Brand: {context_data.get('vin_info', {}).get('brand', 'Unknown')}
                         Model: {context_data.get('vin_info', {}).get('model', 'Unknown')}
                         Year: {context_data.get('vin_info', {}).get('year', 'Unknown')}
                         """
                     else:
                         vehicle_block = f"We do not support {context_data.get('vin_info', {}).get('brand', 'Unknown')} cars."

                 format_instruction = f"""
                 CRITICAL: NO MATCHING PARTS were found in the database.
                 
                 You MUST set the 'whatsapp_text' field exactly to the following message:
                 
                 "{vehicle_block.strip()}
                 
                 For following parts {', '.join(missing_pns)}, our team will contact you soon."
                 
                 Do NOT add any other table or placeholders. Just the above acknowledgement.
                 """
                 final_system_message += "\n\n" + format_instruction
        else:
            # User SEARCHED BY NAME/DESCRIPTION (No Part Numbers provided)
            print(f"   📝 [SuperIntent] User searched by Description. Hiding Part Numbers.")
            if len(parts) > 0:
                format_instruction = f"""
                CRITICAL: The user searched by ITEM NAME (e.g. "Water Pump").
                
                {f'''
                LOGIC: Check the brand in 'vin_info' ({context_data.get('vin_info', {}).get('brand', 'Unknown')}).
                 Supported Brands: BMW, Mercedes, Benz, Rolls Royce, Mini, Honda.
                 
                 IF BRAND IS SUPPORTED:
                    1. Start with:
                    "Vehicle details for your reference are listed below:
                    Brand: [Brand]
                    Model: [Model]
                    Year: [Year]"
                    
                    Then add a blank line.
                    Then say: "[Optional Greeting if user greeted you] Here are the available options:"

                 IF BRAND IS NOT SUPPORTED (e.g. Chevrolet, Toyota, etc.):
                    1. Start with:
                    "[Optional Greeting if user greeted you] We do not support [Insert Brand Name] cars, but here are the details for the part you requested:"
                    2. DO NOT show the "Vehicle details" block (Brand/Model/Year). Skip it.
                 ''' if context_data.get('vin_info') else '1. Start with: "[Optional Greeting if user greeted you] Here are the available options:"'}

                 2. You MUST format the output for found parts with this EXACT structure (Use a Numbered List):
                 
                 [Number]. *[Part Name]*
                    - Brand: [Insert Actual Brand Name]
                    - Price: [Insert Actual Price]
                    - Availability: [Insert In Stock / Out of Stock]
                 
                 3. STRICT RULE: Do NOT show the "Part Number" field. The user did not ask for it.
                 4. Only show: Name, Brand, Price, Availability.
                 """
                final_system_message += "\n\n" + format_instruction
        print(f"   📦 [SuperIntent] Parts Context: {len(parts)} items passed to GPT.")
        try:
            start_time = time.time()
            response = self.client.chat.completions.create(
                # CRITICAL UPGRADE: Use gpt-4o-mini for better long-context handling
                model="gpt-4o", 
                messages=[
                    {"role": "system", "content": final_system_message},
                    {"role": "user", "content": user_text},
                ],
                temperature=0.1, # Reduced temperature for stricter adherence
                max_tokens=7000,
                response_format={"type": "json_object"}
            )
            
            raw_content = response.choices[0].message.content
            # print(f"🤖 [GPT-4o Raw Response]: {raw_content[:500]}...") # DEBUG LOG
            
            # --- ROBUST JSON PARSING ---
            # 1. Clean markdown wrappers if GPT accidentally included them
            # 2. Try parsing
            try:
                result = json.loads(raw_content)
            except json.JSONDecodeError as e:
                current_app.logger.error(f"Failed to parse GPT JSON. Truncated? Error: {e}")
                # Fallback gracefully
                result = {
                    "whatsapp_text": "Thank you for your message. Please try again after some time.",
                    "machine_payload": {"action": "info_only", "intent": "system"}
                }
            
            # Simple validation
            if "whatsapp_text" not in result:
                result["whatsapp_text"] = "Software Error: Invalid GPT response."
            if "machine_payload" not in result:
                # auto-repair payload
                result["machine_payload"] = {"action": "info_only", "intent": "system"}
            print("-----------------🌤️Reply from super intent DYNAMIC PROMPT----------------\n",result['whatsapp_text'])
            
            # Calculate suppression flags (Already done above)
            # Re-using should_skip_intro and should_suppress_branding from top of function
            pass
            
            # Chain: Format Response (Sales Agent Persona)
            if "whatsapp_text" in result:
                formatted_text = self._format_as_sales_agent(
                    result["whatsapp_text"], 
                    skip_intro=should_skip_intro, 
                    suppress_branding=should_suppress_branding
                )
                result["whatsapp_text"] = formatted_text
                
                
            return result

        except Exception as e:
            current_app.logger.error(f"GPT execution failed: {e}")
            return {
                "whatsapp_text": "Thank you for your message. I am unable to fetch your details accurately at the moment. Our team will contact you soon to assist you further.",
                "machine_payload": {"action": "escalate", "error": str(e)}
            }

    def extract_text_from_image(self, base64_image: str) -> str:
        """
        Uses GPT-4o Vision to extract text from a base64 encoded image.
        Focused on VINs and Part Numbers.
        """
        if not self.client:
            return ""

        system_prompt = """
        You are an Expert OCR Engine for Automotive Documents.
        Your job is to transcribe ALL text visible in the image.
        
        PRIORITY targets:
        1. Vehicle Identification Numbers (VIN) - Must be EXACTLY 17 characters.
           - Look carefully for I/1, O/0/Q confusion.
           - If you see 16 chars, look extremely closely for the missing one. A 16-digit VIN is usually invalid.
        2. Part Numbers / OEM Codes.
        3. Part Descriptions.
        
        Output format: Just the raw transcribed text. Do not add markdown or conversational filler.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": system_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1500
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            current_app.logger.error(f"OCR Vision failed: {e}")
            return ""

    def detect_ambiguity(self, item_descriptions: List[str]) -> dict:
        """
        Dynamically checks if any item in the list requires clarification based on DB rules.
        Returns:
        {
            "is_ambiguous": bool,
            "target_item": str (the item that triggered it),
            "question": str,
            "valid_options": List[str]
        }
        """
        if not item_descriptions:
             return {"is_ambiguous": False}

        # 1. Fetch Dynamic Rules
        rules_text = ""
        try:
            from app.services.lovable_service import lovable_service
            prompt_data = lovable_service.get_prompt("system")
            if prompt_data and prompt_data.get("clarification_rules"):
                rules_text = prompt_data.get("clarification_rules")
        except Exception:
            return {"is_ambiguous": False}

        if not rules_text:
            return {"is_ambiguous": False}

        # 2. Run FAST GPT Check
        system_prompt = f"""
        You are an Auto Parts Technical Agent.
        Your job is to checking if ANY parts in the User's List requires clarification based on the Rules.

        RULES:
        {rules_text}
        
        INSTRUCTIONS:
        1. Check EACH item in the User's List.
        2. Valid options must be specific.
        3. Extract the 'Question' and the 'Valid Options' (keywords the user might answer with) from the rule.
        4. Return a LIST of all matching items.
        4. Return a LIST of all matching items.
        5. If no items match, return is_ambiguous=False.
        6. CRITICAL: "target_item" MUST be the exact string from the INPUT list. Do not modify it or just use a substring.
        7. CRITICAL: "valid_options" MUST be distinctive PHRASES (e.g. "with clutch", "without clutch") not single common words like "with" or "without".
        8.⁠ ⁠CRITICAL RULE TO PREVENT REDUNDANT QUESTIONS: If the input item ALREADY contains one of the valid options or a clear positional specifier (like "front", "rear", "left", "right", "upper", "lower", etc.), DO NOT mark it as ambiguous. For example, if the input is "rear brake pad", do NOT ask "Front or Rear". Return ⁠ is_ambiguous=False ⁠ for that item.
        INPUT: List of part names.
        OUTPUT JSON:
        {{
            "is_ambiguous": true,
            "clarifications": [
                {{
                    "target_item": "matched item name",
                    "question": "The question to ask",
                    "valid_options": ["keyword1", "keyword2"]
                }},
                ...
            ]
        }}
        OR
        {{ "is_ambiguous": false }}
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(item_descriptions)},
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            current_app.logger.error(f"Ambiguity check failed: {e}")
            return {"is_ambiguous": False}


    def _normalize_part_names(self, raw_parts: List[str]) -> List[str]:
        """
        Takes a list of raw part names (e.g. "boot", "fly wheel") and normalizes them
        according to the 'parts_alias_text' defined in the Super Intent.
        """
        print(f"   🔍 [DEBUG] _normalize_part_names called with: {raw_parts}")
        if not raw_parts:
            return []

        # 1. Fetch Normalization Rules
        normalization_rules = ""
        try:
            from app.services.lovable_service import lovable_service
            prompt_data = lovable_service.get_prompt("system")
            if prompt_data and prompt_data.get("parts_alias_text"):
                normalization_rules = prompt_data.get("parts_alias_text")
                print(f"   🔍 [DEBUG] Found normalization rules (len={len(normalization_rules)})")
        except Exception as e:
            print(f"   ❌ [DEBUG] API Error in normalization: {e}")
            return raw_parts # Fallback to raw if API fails

        if not normalization_rules:
            return raw_parts

        # 2. Run FAST GPT Check
        system_prompt = f"""
        You are a Part Name Normalizer.
        
        INPUT: List of part names.
        OUTPUT: JSON object with key "normalized" containing the list.

        TRANSFORMATION RULES:
        {normalization_rules}
        
        INSTRUCTIONS:
        1. CHECK the rules for matches. A rule might look like "bonnet / hood" or "boot / trunk".
        2. IF the input part matches exact full word in a rule (e.g. user says "bonnet", rule is "bonnet / hood"), REPLACE IT with the FULL rule string (e.g. "bonnet  hood").
        3. Do NOT just pick one side. Return the combined string.
        4. If no match, keep original.
        5. Fix spelling (e.g. "shok" -> "shock").
        6. Remove generic words like "price", "cost", "genuine".
        7. CRITICAL: DO NOT assume positional or specific variations if the user didn't provide them. For example, if the user asks for "brake pad" (without specifying Front or Rear), DO NOT map it to a "Front Brake Pad" or "Rear Brake Pad" rule. Keep it as "brake pad". Only apply a rule if the user's text specifically matches the rule's specific condition (like 'rear' or 'front' or 'upper').

        
        EXAMPLE OUTPUT:
        {{ "normalized": ["bonnet  hood", "oil filter"] }}
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini", # Fast model is fine here
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(raw_parts)},
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            # Expecting {"parts": [...]} or just a list? 
            # Let's force a structured output or just parse the list.
            # actually better to ask for {"normalized": []}
            return data.get("normalized", raw_parts)
        except Exception as e:
            current_app.logger.error(f"Normalization failed: {e}")
            return raw_parts


    def _extract_part_names_only(self, text: str) -> List[str]:
        """
        Specialized extractor just for Part Names.
        designed to be LOOSE and catch "boot", "glass", "rubber" etc.
        """
        system_prompt = """
        You are a Car Part Detector.
        Your ONLY Job is to extract the MAIN NOUN PHRASE that refers to a PHYSICAL CAR PART.
        
        RULES:
        - Input is often a sentence: "I need a water pump" -> "water pump"
        - Input: "looking for front brake pads" -> "front brake pads"
        - Input: "coolant pump" -> "coolant pump"
        - Include adjectives if they describe the part (e.g. "front", "rear", "upper", "lower").
        - Include slang (e.g. "boot", "rims", "rubber").
        - Include generic terms (e.g. "lights", "glass", "filter").
        - **EXCLUDE** the word "part", "parts", "chassis", "vin", "regn", "no" or numbers. Only extracting specific component names.
        - **EXCLUDE** Greetings and Salutations (e.g. "Hi", "Hello", "Hola", "Good Morning", "Hey"). These are NOT car parts.
        
        CRITICAL EXCLUSION RULE (WARNING LIGHTS):
        - If the text describes a Warning Light, Dashboard Symbol, or Indicator (e.g. "Check Engine Light", "Temperature Symbol", "Triangle with Exclamation"), DO NOT EXTRACT IT.
        - Warning Lights require INFORMATION, not parts.
        - EXCEPTION: If the user explicitly asks for the *bulb* or *sensor* for that light (e.g. "Oil Pressure Sensor", "Headlight Bulb"), then EXTRACT "Oil Pressure Sensor".
        - BUT: "Oil Pressure Light is on" -> [] (Empty).
        
        - IGNORE matching it to a database. Just extract what the user said.
        - IGNORE vehicle models ("BMW", "318i") or years ("2012").
        - IGNORE identifiers like "VIN", "Chassis Number".
        - Output JSON list.
        
        EXAMPLE 1: 
        Input: "I need boot and side mirror for BMW" 
        Output: {"parts": ["boot", "side mirror"]}
        
        EXAMPLE 2 (WARNING LIGHT):
        Input: "Warning light is on looks like a thermometer"
        Output: {"parts": []}
        
        EXAMPLE 3 (MIXED):
        Input: "Check Engine Light is on and need Price for Brake Pads"
        Output: {"parts": ["Brake Pads"]}
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            return data.get("parts", [])
        except Exception as e:
            current_app.logger.error(f"Part name extraction failed: {e}")
            return []

    def extract_entities(self, text: str) -> dict:
        """
        Pure Entity Extraction (No Intent Routing).
        Extracts:
        - VINs (17 chars)
        - Part Numbers (alphanumeric codes)
        - Part Names (via dedicated sub-agent)
        """
        if not self.client:
            return {"vin_list": [], "part_numbers": [], "item_descriptions": [], "raw_item_descriptions": []}

        # 1. Main Extraction (VINs + Numbers)
        system_prompt = """
        You are an Entity Extractor API. 
        
        EXTRACT THESE ENTITIES:
        1. "vin_list": List of 17-character VINs (alphanumeric).
           - PRIORITY: Capture any 17-char VIN.
           - If a sequence is 16 chars but looks like a VIN, try to find the adjacent missing char (or remove a stray space).
           - Do not invent characters. Only fix obvious splits.

        2. "part_numbers": List of part numbers or OEM codes. 
           - Capture alphanumeric sequences (min 3 chars).
           - ALLOW hyphens, dots, or spaces IF they connect parts of a single code (e.g. "17 127 537 - 101" is ONE code).
           - Do not split codes that are separated by a space or hyphen if they look like a single identifier.
           - Treat "17-127-537 -101" as a SINGLE part number string "17-127-537-101".
            
        3. "is_warning_light": Boolean (true/false).
           - Set to TRUE if the user is describing a dashboard symbol, warning light, or asking about an icon (e.g. "red thermostat symbol", "check engine light", "triangle with !", "symbol on dash").
           - Set to FALSE for normal part requests (e.g. "brake pads", "oil filter") or general greetings.
            
        OUTPUT JSON ONLY:
        {
            "vin_list": [],
            "part_numbers": [],
            "is_warning_light": false
        }
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini", 
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            
            # 2. Dedicated Part Name Extraction (Loose)
            raw_parts = self._extract_part_names_only(text)
            print(f"   🔍 [DEBUG] raw_parts extracted: {raw_parts}")
            
            # 3. Normalize Part Names (Strict)
            if raw_parts:
                result["raw_item_descriptions"] = raw_parts
                normalized_parts = self._normalize_part_names(raw_parts)
                print(f"   🔍 [DEBUG] normalized_parts: {normalized_parts}")
                result["item_descriptions"] = normalized_parts
            else:
                result["item_descriptions"] = []
                result["raw_item_descriptions"] = []
            # print(f"   🔍 [DEBUG] result: {result}")
            return result
            
        except Exception as e:
            current_app.logger.error(f"CRITICAL ERROR in extract_entities: {e}")
            import traceback
            traceback.print_exc()
            return {"vin_list": [], "part_numbers": [], "item_descriptions": [], "raw_item_descriptions": [], "is_warning_light": False}


    def _format_as_sales_agent(self, raw_text: str, skip_intro: bool = False, suppress_branding: bool = False) -> str:
        
        if not raw_text or len(raw_text) < 5:
            return raw_text
        
        # BYPASS: If text is a specific system error or simple notification, skip reformatting.
        # This prevents "I'm sorry, no text to reformat" errors for simple replies.
        bypass_phrases = [
            "no item in catalog",
            "team will contact you",
            "software error",
            "not found in reference", # ADDED: Prevent reformatting errors for this frequent case
        ]
        if any(phrase in raw_text.lower() for phrase in bypass_phrases):
             # Special Handle for "Not Found in Reference" -> Standard Polite Message
             if "not found in reference" in raw_text.lower():
                 return "Thank you for your inquiry. Our team will review the details and contact you shortly to provide the necessary assistance. 😊"
             return raw_text
        system_prompt = f"""
        You are a Professional Car Parts Sales Agent on WhatsApp.
        Your job is to REFORMAT the provided text to make it look visually appealing, friendly, and professional.
        
        GUIDELINES:
        1. REFORMAT ONLY. Do not add sign-offs or polite conversational filler if they are not in the input.
       
        2. Use relevant Emojis (✅, ⚠️, 💰, 🔎) to make it engaging.
        3. **Styling & Layout Rules (CRITICAL)**:
           - Use *Bold* for ALL labels (e.g., *Brand:*, *Price:*, *Part Number:*).
           - Use a standard Bullet Point "•" for list items to look clean.
           - Add a blank line between different parts/items for readability.
           - Ensure the Part Name is also *Bold* or clearly highlighted.
        4. DEDUPLICATION(MANDATORY): CHECK the Input Text. If it *already* contains "www.carpartsdubai.com or https://carpartsdubai.com/" or a sign-off, do NOT add it again in your output.
        5. NO TRUNCATION: You format EVERY single item in the list. Do not summarize.
        6. Output ONLY the reformatted text.
        7. GREETINGS: If the input text contains a greeting (e.g., "Hello," "Hi there,"), you MUST PRESERVE it at the beginning of your response. Ensure there is a blank line after the greeting before the content starts.
        
       
        8. STRICT RULE: DO NOT ADD ANY FOOTER/SIGN-OFF, SUMMARY, or OUTRO like "I see you are looking for...". Just end with the list.
        9. EXCEPTION: If the input text contains 'I am CarPartsAI', YOU MUST PRESERVE IT in the output. Do not remove it.
        
        INPUT TEXT:
        {{raw_text}}
        
        OUTPUT:
        The reformatted text. If the input text had a greeting, keep it followed by a newline.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o", # UPGRADE to gpt-4.1-mini for better long-context handling
                messages=[
                    {"role": "system", "content": system_prompt.replace("{raw_text}", raw_text)},
                ],
                temperature=0.2, 
                max_tokens=7000 # Standard safe max output for GPT models
            )
            formatted = response.choices[0].message.content.strip()
            # Strip markdown code block wrappers GPT sometimes adds
            formatted = re.sub(r'^```(?:plaintext|text|markdown)?\s*\n?', '', formatted)
            formatted = re.sub(r'\n?```\s*$', '', formatted)
            formatted = formatted.strip()
            # Guardrail: If GPT refused to format, return original text
            sorry_phrases = ["i'm sorry", "i cannot", "i can't assist", "i apologize", "i'm unable to"]
            if any(phrase in formatted.lower() for phrase in sorry_phrases):
                current_app.logger.warning(f"Format agent refused. Returning raw text.")
                print(f"⚠️ Format agent refused to reformat. Falling back to raw text.")
                return raw_text
            print(f"----------------✅ Formatting successful----------------\n: {formatted}")
            return formatted
        except Exception as e:
            current_app.logger.error(f"Formatting failed: {e}")
            return raw_text
    def filter_parts_by_relevance(self, parts: List[Dict], query: str) -> List[Dict]:
        if not self.client or not parts:
            return parts

        # Optimize context: Only send necessary fields to save tokens/latency
        minified_parts = []
        for i, p in enumerate(parts):
            minified_parts.append({
                "id": i,
                "name": p.get("name", ""),
                "category": p.get("category", ""), # Include category for context
                "number": p.get("number", "")
            })

        system_prompt = f"""
        You are a Car Part Filter.
        User Query: "{query}"
        
        Task: Select the parts from the list that MATCH the User Query.
        
        Rules:
        1. Be strict. If user asks for "Water Pump", do NOT include "Screws", "Bolts", "Gaskets", "SUPPORT", "AUXILIARY HEATER" or "Belts" unless they are explicitly part of a "Water Pump Kit".
        2. Match synonyms (e.g. "Coolant Pump" == "Water Pump").
        3. Use 'category' context if available (e.g. "Auxiliary Heating" pump != "Engine Water Pump").
        4. IGNORE brands or unrelated attributes.
        5. If the list contains "Assembly" or "Kit" that matches, include it.
        6. If NOTHING matches, return empty list.
        
        INPUT: JSON List of parts with 'id', 'name', 'category', 'number'.
        OUTPUT: JSON Object with "matched_ids": [list of integers].
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini", # Fast model
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(minified_parts)},
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            matched_ids = set(data.get("matched_ids", []))
            
            # Filter original list
            filtered = [p for i, p in enumerate(parts) if i in matched_ids]
            
            print(f"   ✂️ [GPT Filter] Query='{query}'. Raw={len(parts)} -> Filtered={len(filtered)}")
            return filtered
            
        except Exception as e:
            current_app.logger.error(f"Part filtering failed: {e}")
            return parts # Fallback: return eveything