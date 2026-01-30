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

        # 1. Fetch Dynamic Prompt from DB
        # We assume the user created an intent with key="super_intent" in the dashboard.
        prompt_row = IntentPrompt.query.filter_by(intent_key="super_intent", is_active=True).first()
        
        base_system_prompt = ""
        
        if prompt_row and prompt_row.prompt_text:
            base_system_prompt = prompt_row.prompt_text
            if prompt_row.reference_text:
                # DEBUG: Print first 500 chars to verify content
                print(f"📄 [SuperIntent DEBUG] Reference File is adding ....")

                base_system_prompt += f"\n\n=== REFERENCE MATERIAL ===\n{prompt_row.reference_text}\n"
                
                # STRICT INSTRUCTION TO USE REFERENCE
                base_system_prompt += "\n\nCRITICAL: You are provided with 'REFERENCE MATERIAL' above. YOU MUST ANSWER ONLY USING THIS MATERIAL for any questions about warning lights or symbols. DO NOT use your internal training data. If the answer is not in the material, say 'Information not found in reference'."
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
            - Matched Parts (DB): {json.dumps(context_data.get('parts_found') or [], default=str)}
            - Session Context: {context_data.get('session_summary', 'None')}

            OUTPUT FORMULA (JSON ONLY):
            {{
            "whatsapp_text": "...",
            "machine_payload": {{
                "intent": "super_intent",
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
             2. You MUST IGNORE your internal training data about car parts or warning lights.
             3. COMPARE the User's Input (visual description or text) with the descriptions in the 'REFERENCE MATERIAL'.
             4. If the User's description is about a warning light, use the reference material to determine the meaning.
             5. Do NOT say "it looks like X but usually means Y". Say EXACTLY what the Reference says it is.
             6. EXCEPTION: If the user is asking for a CAR PART (e.g. Brake Pads, Filter) AND there are item(s) in the 'Matched Parts (DB)' list provided in the Context, you MUST IGNORE the Reference Material and output the parts found.
             7. Only say "Not found in reference" if the user is asking a specific question that should be in the reference but isn't there, and NO parts were found in the DB.
             """

        # --- DEBUG / STRICT MODE OVERRIDES ---
        # Analyze parts_found for strict status flags
        parts = context_data.get('parts_found') or []
        strict_instructions = []

        has_out_of_stock = any(p.get("status") == "out_of_stock" for p in parts)
        has_error = any(p.get("status") == "error" for p in parts)
        has_empty = any(p.get("status") == "empty" for p in parts)
        
        # Priority: Error > Out of Stock > Empty
        if has_error:
             strict_instructions.append("CRITICAL: The catalog search FAILED. You MUST reply exactly: 'Failed to search catalog due to technical error.' (plus any helpful context). Do not say 'I couldn't find it', say 'Failed to Catalog'.")
        elif has_out_of_stock:
             strict_instructions.append("CRITICAL: Parts were found in the catalog but are NOT in the local database. You MUST reply: 'Found in Catalog but Not in Stock'. List the part numbers found but clearly state they are out of stock.")
        elif has_empty and not any(p.get("price") for p in parts): # Only empty/missing
             strict_instructions.append("CRITICAL: The catalog search returned NO results. You MUST reply: 'Not in Catalog'. Do not offer to search again.")

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
        extracted = context_data.get("extracted_entities", {})
        user_pns = extracted.get("part_numbers", [])
        user_descs = extracted.get("item_descriptions", [])
        
        # Condition: Has Part Numbers AND (No Descriptions OR Very few descriptions compared to PNs)
        # We'll use a simple heuristic: If PNs exist, we want this strict table format for clarity.
        if user_pns:
            missing_pns = context_data.get("missing_pns", [])
            print(f"   🔢 [SuperIntent] User provided Part Numbers. Enforcing EXTENDED FORMAT. Found: {len(parts)}, Missing: {len(missing_pns)}")
            
            # CASE A: Some parts found
            if len(parts) > 0:
                 format_instruction = f"""
                 CRITICAL: The user searched by PART NUMBER. 
                 1. You MUST start the response with: "Thank you for providing the part number . Here are the available options for this part:"
                 2. You MUST format the output for found parts EXACTLY as follows for each item (Use a Numbered List):
                 
                 [Number]. *[Part Name]*
                    - Brand: [Insert Actual Brand Name]
                    - Price: [Insert Actual Price]
                    - Part Number: [Insert Actual Part Number]
                    - Availability: [Insert In Stock / Out of Stock]
                 
                 IMPORTANT: Replace the terms in brackets [] with the REAL data from the found parts context. Do NOT use the text "Brand Name" or "Price" literally.
                 MANDATORY: You MUST include the 'Part Number' line for EVERY item.
                 Do not summarize. Show this block for EVERY matching part found.
                 """
                 
                 if missing_pns:
                     format_instruction += f"\n\n3. FOR MISSING PARTS: The following part numbers were NOT found in the database: {', '.join(missing_pns)}.\n   You MUST add this exact line for each missing part:\n   'For part number [Missing Part Number], our team will contact you soon.'"

                 final_system_message += "\n\n" + format_instruction
            
            # CASE B: NO parts found at all
            elif len(parts) == 0:
                 format_instruction = f"""
                 CRITICAL: The user searched by PART NUMBER, but NO MATCHING PARTS were found in the database.
                 
                 You MUST output the following message explicitly:
                 "Thank you for providing the part number .
                 
                 For part number {', '.join(missing_pns)}, our team will contact you soon."
                 
                 Do NOT add any other table or placeholders. Just the above acknowledgement.
                 """
                 final_system_message += "\n\n" + format_instruction
        
        print(f"   📦 [SuperIntent] Parts Context: {len(parts)} items passed to GPT.")

        try:
            start_time = time.time()
            response = self.client.chat.completions.create(
                # CRITICAL UPGRADE: Use gpt-4o for better reasoning and strict instruction following
                model="gpt-4o", 
                messages=[
                    {"role": "system", "content": final_system_message},
                    {"role": "user", "content": user_text},
                ],
                temperature=0.1, # Reduced temperature for stricter adherence
                max_tokens=10000,
                response_format={"type": "json_object"}
            )
            
            raw_content = response.choices[0].message.content
            # print(f"🤖 [GPT-4o Raw Response]: {raw_content[:500]}...") # DEBUG LOG
            result = json.loads(raw_content)
            
            # Simple validation
            if "whatsapp_text" not in result:
                result["whatsapp_text"] = "Software Error: Invalid GPT response."
            if "machine_payload" not in result:
                # auto-repair payload
                result["machine_payload"] = {"action": "info_only", "intent": "super_intent"}
            print(result['whatsapp_text'])
            # Chain: Format Response (Sales Agent Persona)
            if "whatsapp_text" in result:
                formatted_text = self._format_as_sales_agent(result["whatsapp_text"])
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
                model="gpt-4o",
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


    def _normalize_part_names(self, raw_parts: List[str]) -> List[str]:
        """
        Takes a list of raw part names (e.g. "boot", "fly wheel") and normalizes them
        according to the 'parts_alias_text' defined in the Super Intent.
        """
        if not raw_parts:
            return []

        # 1. Fetch Normalization Rules
        normalization_rules = ""
        try:
            prompt_row = IntentPrompt.query.filter_by(intent_key="super_intent").first()
            if prompt_row and prompt_row.parts_alias_text:
                normalization_rules = prompt_row.parts_alias_text
        except Exception:
            return raw_parts # Fallback to raw if DB fails

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
        - If a part match a rule, swap it (e.g. "bonnet" -> "hood").
        - If no match, keep original.
        - Fix spacing (e.g. "waterpump" -> "water pump").
        - Remove generic words like "price", "cost", "genuine".
        
        EXAMPLE OUTPUT:
        {{ "normalized": ["hood", "oil filter"] }}
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini", # Fast model is fine here
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
        Your ONLY Job is to list words/phrases from the input that refer to a CAR PART.
        
        RULES:
        - Include slang (e.g. "boot", "rims", "rubber").
        - Include generic terms (e.g. "lights", "glass", "filter").
        - **EXCLUDE** the word "part", "parts", "chassis", "vin", "regn", "no" or numbers. Only extracting specific component names.
        - IGNORE matching it to a database. Just extract what the user said.
        - IGNORE vehicle models ("BMW", "318i") or years ("2012").
        - IGNORE identifiers like "VIN", "Chassis Number".
        - Output JSON list.
        
        EXAMPLE: 
        Input: "I need boot and side mirror for BMW" 
        Output: {"parts": ["boot", "side mirror"]}
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
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
            return {"vin_list": [], "part_numbers": [], "item_descriptions": []}

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
        
        OUTPUT JSON ONLY:
        {
            "vin_list": [],
            "part_numbers": []
        }
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o", 
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
            
            # 3. Normalize Part Names (Strict)
            if raw_parts:
                normalized_parts = self._normalize_part_names(raw_parts)
                result["item_descriptions"] = normalized_parts
            else:
                result["item_descriptions"] = []
                
            return result
            
        except Exception:
            return {"vin_list": [], "part_numbers": [], "item_descriptions": []}

    # def execute_specific_intent(
    #     self,
    #     intent_key: str,
    #     user_text: str,
    #     context_data: dict,
    # ) -> dict:
    #     """
    #     Execute a SPECIFIC intent (e.g. 'warning_light') bypassing the Super Intent router.
    #     Fetches the prompt + reference text from DB and runs it.
    #     """
    #     if not self.client:
    #         return {
    #             "whatsapp_text": "System error: OpenAI client not configured.",
    #             "machine_payload": {"action": "escalate", "error": "no_client"}
    #         }

    #     # 1. Fetch Dynamic Prompt
    #     try:
    #         prompt_row = IntentPrompt.query.filter_by(intent_key=intent_key, is_active=True).first()
    #     except Exception:
    #         prompt_row = None
        
    #     if not prompt_row:
    #         # Fallback if specific intent lookup fails -> Run Super Intent? 
    #         # Or return error. For now, let's log and fallback.
    #         print(f"⚠️ Specific intent '{intent_key}' not found or inactive. Falling back to Super Intent.")
    #         return self.run_super_intent(user_text, context_data)

    #     # 2. Construct System Message
    #     base_prompt = prompt_row.prompt_text or "You are a helpful assistant."
    #     reference_text = prompt_row.reference_text or ""

    #     system_message = f"""
    #     {base_prompt}

    #     === REFERENCE MATERIAL (STRICTLY FOLLOW THIS) ===
    #     {reference_text}
        
    #     === CONTEXT ===
    #     User Input: "{user_text}"
    #     Vehicle Context: {context_data.get('vin_info') or 'None'}
    #     """

    #     # 3. Execute
    #     try:
    #         response = self.client.chat.completions.create(
    #             model=current_app.config.get("OPENAI_MODEL", "gpt-4o-mini"),
    #             messages=[
    #                 {"role": "system", "content": system_message},
    #                 {"role": "user", "content": user_text},
    #             ],
    #             temperature=0.3,
    #             max_tokens=800
    #         )
            
    #         reply_text = response.choices[0].message.content.strip()
            
    #         # Wrap in standard format
    #         return {
    #             "whatsapp_text": reply_text,
    #             "machine_payload": {
    #                 "intent": intent_key,
    #                 "action": "reply",
    #                 "confidence": 1.0
    #             }
    #         }

    #     except Exception as e:
    #         current_app.logger.error(f"Specific Intent '{intent_key}' failed: {e}")
    #         return {
    #             "whatsapp_text": "I encountered an error processing your request.",
    #             "machine_payload": {"action": "error", "error": str(e)}
    #         }


    def _format_as_sales_agent(self, raw_text: str) -> str:
        """
        Post-processing step: Reformats the text to look like a professional WhatsApp Sales Agent.
        - Adds Emojis (🏎️, 🔧, ✅)
        - Add maximum 2 to 3 Emojis
        - Improves Layout (Bulleted lists, bolding)
        - Ensures professional tone
        """
        if not raw_text or len(raw_text) < 5:
            return raw_text

        system_prompt = """
        You are a Professional Car Parts Sales Agent on WhatsApp.
        Your job is to REFORMAT the provided text to make it look visually appealing, friendly, and professional.
        
        GUIDELINES:
        1. REFORMAT ONLY. Do NOT add greetings ("Hello", "Hi"), sign-offs, or polite conversational filler if they are not in the input.
        2. Keep the EXACT SAME information/meaning. Do not add new facts.
        3. Use relevant Emojis (✅, ⚠️, 💰, 🔎) to make it engaging. BUT use a MAXIMUM of 3 emojis in the entire message. Do not overuse them.
        4. Use key WhatsApp formatting:
           - *Bold* for key terms (Part Names, Prices, Action Items).
           - Bullet points for lists.
           - Separate paragraphs for readability.
        5. DEDUPLICATION(MANDATORY): CHECK the Input Text. If it *already* contains "www.carpartsdubai.com" or a sign-off, do NOT add it again in your output.
        6. NO TRUNCATION: You format EVERY single item in the list. Do not summarize.
        7. NO CHATTY INTROS/OUTROS: Output ONLY the reformatted text.
        
        INPUT TEXT:
        {raw_text}
        
        OUTPUT:
        The reformatted text only. No greetings.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o", # UPGRADE to gpt-4o for better long-context handling
                messages=[
                    {"role": "system", "content": system_prompt.replace("{raw_text}", raw_text)},
                ],
                temperature=0.3, 
                max_tokens=10000 # Standard safe max output for GPT models
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            current_app.logger.error(f"Formatting failed: {e}")
            return raw_text
