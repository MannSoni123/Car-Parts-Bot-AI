# services/headlight_formatter.py

from typing import Dict


def format_headlight_response(features: Dict) -> str:
    """
    Generate a safe, user-facing response for headlight images.

    Rules:
    - Never identify the vehicle
    - Never confirm fitment
    - Always request VIN
    """

    message = (
        "I can see that this image appears to show a vehicle *headlight*.\n\n"
        "From an image alone, it’s not possible to reliably confirm the exact vehicle, "
        "model, or year.\n\n"
        "🚗 To ensure the correct headlight for your vehicle, please share your *VIN number*.\n\n"
        "If helpful, you can also let me know whether this is for:\n"
        "• Left or right side\n"
        "• Or if you’re unsure\n\n"
        "Once I have the VIN, I’ll be able to guide you with the correct options."
    )

    return message
