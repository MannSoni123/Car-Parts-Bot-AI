import requests
import json
from flask import current_app
from app.redis_client import redis_client

class LovableService:
    def get_prompt(self, intent_key: str = "system") -> dict:
        """
        Fetches the prompt config from Lovable API, caching it in Redis for 5 minutes.
        Returns a dict matching the IntentPrompt structure, or None if it fails.
        """
        cache_key = f"lovable_prompt:{intent_key}"
        
        try:
            cached = redis_client.get(cache_key)
            if cached:
                print(f"⚡ [LovableService] Loaded '{intent_key}' from Redis Cache.")
                return json.loads(cached)
        except Exception as e:
            current_app.logger.warning(f"Redis cache read failed: {e}")

        base_url = current_app.config.get("LOVABLE_API_BASE_URL", "https://car-parts-uae.lovable.app")
        api_key = current_app.config.get("CHATBOT_API_KEY", "")

        url = f"{base_url}/api/public/prompts/{intent_key}"
        headers = {
            "x-chatbot-api-key": api_key,
            "Content-Type": "application/json"
        }

        try:
            print(f"🌐 [LovableService] Fetching fresh '{intent_key}' from {url}...")
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("success") and "data" in data:
                prompt_data = data["data"]
                
                # Cache for only 5 seconds during testing to see instant updates!
                try:
                    redis_client.setex(cache_key, 5, json.dumps(prompt_data))
                except Exception as e:
                    current_app.logger.warning(f"Redis cache write failed: {e}")
                
                return prompt_data
            else:
                current_app.logger.error(f"Lovable Prompt API returned unsuccessful response: {data}")
                return None
        except Exception as e:
            current_app.logger.error(f"Failed to fetch prompt from Lovable API: {e}")
            return None

    def post_analytics_events(self, payload: dict):
        """
        Posts search analytics events to the Lovable API.
        """
        base_url = current_app.config.get("LOVABLE_API_BASE_URL", "https://car-parts-uae.lovable.app")
        api_key = current_app.config.get("CHATBOT_API_KEY", "")

        url = f"{base_url}/api/public/analytics/events"
        headers = {
            "x-chatbot-api-key": api_key,
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            response.raise_for_status()
            current_app.logger.info("Successfully posted analytics events to Lovable.")
        except requests.exceptions.RequestException as e:
            error_msg = e.response.text if getattr(e, 'response', None) is not None else str(e)
            current_app.logger.error(f"Failed to post analytics events to Lovable API: {e} | Response Body: {error_msg}")

    def post_chat_logs(self, payload: dict):
        """
        Posts chat conversational history to the Lovable API.
        """
        base_url = current_app.config.get("LOVABLE_API_BASE_URL", "https://car-parts-uae.lovable.app")
        api_key = current_app.config.get("CHATBOT_API_KEY", "")

        url = f"{base_url}/api/public/chat-logs"
        headers = {
            "x-chatbot-api-key": api_key,
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            response.raise_for_status()
            current_app.logger.info("Successfully posted chat logs to Lovable.")
        except requests.exceptions.RequestException as e:
            error_msg = e.response.text if getattr(e, 'response', None) is not None else str(e)
            current_app.logger.error(f"Failed to post chat logs to Lovable API: {e} | Response Body: {error_msg}")

lovable_service = LovableService()
