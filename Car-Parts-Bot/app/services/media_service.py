import requests
from flask import current_app
from ..services.vin_ocr import download_media_blob, run_chassis_ocr
from ..services.image_intent_router import detect_image_intent
from ..services.extract_vin_service import extract_vin_from_text
from ..services.image_intent_executor import run_image_intent
from app.services.scraper.partsouq_xpath_scraper import get_scraper
from app.session_store import get_session, save_session
import time

def download_whatsapp_media(url: str) -> bytes:
    token = current_app.config["META_ACCESS_TOKEN"]

    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    resp.raise_for_status()
    # print(resp.content)
    return resp.content


def process_image_media(user_id,media_id: str) -> dict:
    try:
        # 1️⃣ Download image
        content, content_type = download_media_blob(media_id)
        print("✅ Downloaded media:", media_id, "Type:", content_type)
        # 2️⃣ Detect image intent
        intent_key = detect_image_intent(content, content_type)

        print("🔍 Detected image intent:", intent_key)
         # 4️⃣ All other image intents → DB driven
        result = run_image_intent(intent_key, content, content_type)
        print(result.get("message"))
        message = result.get("message", "")

        # 4️⃣ 🔥 Extract VIN from LLM message
        vin = extract_vin_from_text(message)
        print("Extracted VIN:", vin)
        if vin:
            session = get_session(user_id)
            session["entities"]["vin"] = vin
            session["context"]["vin_set_at"] = time.time()
            save_session(user_id, session)
            scraper = get_scraper()
            if scraper is None:
                return "SCRAPER NOT ACCESSIBLE"
            vehicle_info = scraper.get_vehicle_details(vin)
            vehicle_brand = vehicle_info.get('brand', 'N/A')
            
            # Normalize and check supported brands
            supported_brands = ["BMW", "MERCEDES", "ROLLS ROYCE", "MINI", "HONDA"]
            brand_upper = vehicle_brand.upper().strip()
            
            is_supported = any(b in brand_upper for b in supported_brands)
            
            if vehicle_info and is_supported:
                # 3. Format the Response
                return (
                    f"✅ *Vehicle Found!* 🚘\n"
                    f"• *VIN:* {vin}\n"
                    f"• *Brand:* {vehicle_brand}\n"
                    f"• *Model:* {vehicle_info.get('name', 'N/A')}\n"
                    f"• *Year:* {vehicle_info.get('date', 'N/A')}\n\n"
                    f"Please tell me the *part name* you are looking for. (e.g. Brake Pads, Oil Filter)"
                )
            elif vehicle_info:
                 return (
                    f"❌ *Vehicle Not Supported* 🚘\n"
                    f"• *VIN:* {vin}\n"
                    f"• *Brand:* {vehicle_brand}\n\n"
                    f"Sorry, we currently only support BMW, Mercedes-Benz, Rolls-Royce, Mini Cooper, and Honda."
                )
            print(session)
        
        # Ensure consistent output
        return {
            "intent": intent_key,
            "message": result.get("message", "Image processed.")
        }

    except Exception as exc:
        print("❌ Image processing failed:", exc)
        return {
            "intent": "No intent Found",
            "message": "Image processing failed. Please try again or contact us on +971 50 482 7057" 
        }