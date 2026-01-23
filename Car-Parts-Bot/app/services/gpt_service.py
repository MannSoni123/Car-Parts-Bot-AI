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
             6. If the answer is in the Reference, use it. If not, say "Not found in reference".
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
            final_system_message += "\n\n" + "\n".join(strict_instructions)

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
            print(f"🤖 [GPT-4o Raw Response]: {raw_content[:500]}...") # DEBUG LOG
            result = json.loads(raw_content)
            
            # Simple validation
            if "whatsapp_text" not in result:
                result["whatsapp_text"] = "Software Error: Invalid GPT response."
            if "machine_payload" not in result:
                # auto-repair payload
                result["machine_payload"] = {"action": "info_only", "intent": "super_intent"}
                
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


    def extract_entities(self, text: str) -> dict:
        """
        Pure Entity Extraction (No Intent Routing).
        Extracts:
        - VINs (17 chars)
        - Part Numbers (alphanumeric codes)
        - Part Names (free text descriptions)
        """
        if not self.client:
            return {"vin_list": [], "part_numbers": [], "item_descriptions": []}

        system_prompt = """
        You are an Entity Extractor API. Your job is to extract vehicle information and part identifiers from user text.
        
        EXTRACT THESE ENTITIES:
        1. "vin_list": List of 17-character VINs (alphanumeric, exclude I,O,Q check if possible).
        2. "part_numbers": List of part numbers or OEM codes. 
           - RULES: 
             - Capture ANY alphanumeric sequence that looks like a part identifier.
             - Capture sequences with spaces/dashes if they look like a single unit (e.g. "19 475 MM", "81-22-9-407-758").
             - If the user explicitly says "part number X" or "number is X", ALWAYS extract X as a part number, even if it looks like a dimension (e.g. "19 inch").
             - Minimal length 3 chars.
             - Ignore common words unless they are part of the ID.
        3. "item_descriptions": List of part names/descriptions (e.g. "brake pad", "oil filter").
           - Exclude the part numbers themselves.
           - CRITICAL: Exclude vehicle attributes like "Model 318i", "X5", "5 Series", "Year 2020", "Brand BMW".
           - CRITICAL: Exclude generic label text like "Made in Germany", "Manufacturer", "Date", "Weight".
           - ONLY include names of ACTUAL REPLACEMENT PARTS. If unsure, leave empty.
        
        OUTPUT JSON ONLY:
        {
            "vin_list": [],
            "part_numbers": [],
            "item_descriptions": []
        }
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
            return json.loads(response.choices[0].message.content)
        except Exception:
            return {"vin_list": [], "part_numbers": [], "item_descriptions": []}

    def execute_specific_intent(
        self,
        intent_key: str,
        user_text: str,
        context_data: dict,
    ) -> dict:
        """
        Execute a SPECIFIC intent (e.g. 'warning_light') bypassing the Super Intent router.
        Fetches the prompt + reference text from DB and runs it.
        """
        if not self.client:
            return {
                "whatsapp_text": "System error: OpenAI client not configured.",
                "machine_payload": {"action": "escalate", "error": "no_client"}
            }

        # 1. Fetch Dynamic Prompt
        try:
            prompt_row = IntentPrompt.query.filter_by(intent_key=intent_key, is_active=True).first()
        except Exception:
            prompt_row = None
        
        if not prompt_row:
            # Fallback if specific intent lookup fails -> Run Super Intent? 
            # Or return error. For now, let's log and fallback.
            print(f"⚠️ Specific intent '{intent_key}' not found or inactive. Falling back to Super Intent.")
            return self.run_super_intent(user_text, context_data)

        # 2. Construct System Message
        base_prompt = prompt_row.prompt_text or "You are a helpful assistant."
        reference_text = prompt_row.reference_text or ""

        system_message = f"""
        {base_prompt}

        === REFERENCE MATERIAL (STRICTLY FOLLOW THIS) ===
        {reference_text}
        
        === CONTEXT ===
        User Input: "{user_text}"
        Vehicle Context: {context_data.get('vin_info') or 'None'}
        """

        # 3. Execute
        try:
            response = self.client.chat.completions.create(
                model=current_app.config.get("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_text},
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            reply_text = response.choices[0].message.content.strip()
            
            # Wrap in standard format
            return {
                "whatsapp_text": reply_text,
                "machine_payload": {
                    "intent": intent_key,
                    "action": "reply",
                    "confidence": 1.0
                }
            }

        except Exception as e:
            current_app.logger.error(f"Specific Intent '{intent_key}' failed: {e}")
            return {
                "whatsapp_text": "I encountered an error processing your request.",
                "machine_payload": {"action": "error", "error": str(e)}
            }


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
        1. Keep the EXACT SAME information/meaning. Do not add new facts.
        2. Use relevant Emojis (✅, ⚠️, 💰, 🔎) to make it engaging. BUT use a MAXIMUM of 3 emojis in the entire message. Do not overuse them.
        3. Use key WhatsApp formatting:
           - *Bold* for key terms (Part Names, Prices, Action Items).
           - Bullet points for lists.
           - Separate paragraphs for readability.
        4. Tone: Helpful, Polite, Efficient.
        5. DEDUPLICATION: CHECK the Input Text. If it *already* contains "www.carpartsdubai.com" or a sign-off, do NOT add it again in your output. Your job is to format the list, not to add a second footer.
        6. NO TRUNCATION: You format EVERY single item in the list. Do not summarize. If there are 50 items, format all 50.
        7. NO CHATTY INTROS: Do NOT say "Here is the reformatted text", or use markdown code blocks/fences. Just output the final text directly.
        
        INPUT TEXT:
        {raw_text}
        
        OUTPUT:
        The reformatted text only.
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
