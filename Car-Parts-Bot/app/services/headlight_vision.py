# services/headlight_vision.py

from typing import Dict


def analyze_headlight_image(image_bytes: bytes, content_type: str) -> Dict:
    """
    Analyze a headlight image for high-level visual traits ONLY.

    IMPORTANT:
    - Do NOT identify vehicle brand, model, or year
    - Do NOT guarantee left/right side
    - Do NOT confirm compatibility

    This function provides weak signals that can help guide the next step.
    """

    # ⚠️ Placeholder for future CV model (YOLO / CLIP / CNN)
    # Right now we keep it intentionally minimal and safe.

    features = {
        "part_type": "headlight",
        "lighting_type": "unknown",   # halogen / xenon / led → unknown unless CV added
        "shape": "unknown",           # projector / reflector → unknown
        "side": "unknown",            # left / right → unknown
        "confidence": 0.50             # low confidence by design
    }

    return features
