import requests
from flask import current_app

def get_media_url(media_id):
    token = current_app.config["META_ACCESS_TOKEN"]
    resp = requests.get(
        f"https://graph.facebook.com/v18.0/{media_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    return resp.json().get("url")
