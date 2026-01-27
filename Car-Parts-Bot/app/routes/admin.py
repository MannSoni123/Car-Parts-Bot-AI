"""
Admin API endpoints for configuration management.
"""
from flask import Blueprint, current_app, jsonify, request
from functools import wraps
from ..extensions import db
from ..models import IntentPrompt
import jwt
import datetime
import os
from flask import make_response
from datetime import datetime, timedelta, timezone
from app.services.reference_extractor import extract_text_from_file
from app.services.upload_validator import validate_reference_file
from werkzeug.utils import secure_filename
admin_bp = Blueprint("admin", __name__)

JWT_SECRET = os.getenv("JWT_SECRET")
ADMIN_SECRET = os.getenv("ADMIN_SECRET")


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.cookies.get("admin_session")
        if not token:
            return jsonify({"error": "Unauthorized"}), 401
        try:
            jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Session expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid session"}), 401
        return f(*args, **kwargs)
    return wrapper



@admin_bp.post("/login")
def admin_login():
    data = request.get_json() or {}
    token = data.get("token")
    if token != ADMIN_SECRET:
        return jsonify({"error": "Invalid admin token"}), 401

    payload = {
        "role": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=6)
    }

    jwt_token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    resp = make_response(jsonify({"success": True}))
    resp.set_cookie(
        "admin_session",
        jwt_token,
        httponly=True,
        secure=True,        # HTTPS ONLY
        # secure=False,  # LOCAL ONLY

        samesite="Strict",
        max_age=6 * 3600
    )
    return resp


@admin_bp.post("/logout")
def admin_logout():
    resp = make_response(jsonify({"success": True}))
    resp.delete_cookie("admin_session")
    return resp


@admin_bp.get("/me")
@admin_required
def admin_me():
    return jsonify({
        "authenticated": True
    }), 200


@admin_bp.get("/config")
@admin_required
def get_config():
    """Get current configuration (without sensitive values)."""
    return jsonify({
        "openai_model": current_app.config.get("OPENAI_MODEL"),
        "chassis_api_configured": bool(
            current_app.config.get("CHASSIS_API_BASE_URL")
            and current_app.config.get("CHASSIS_API_KEY")
        ),
        "whatsapp_configured": bool(
            current_app.config.get("META_ACCESS_TOKEN")
            and current_app.config.get("META_PHONE_NUMBER_ID")
        ),
        "openai_configured": bool(current_app.config.get("OPENAI_API_KEY")),
    })


@admin_bp.get("/stats")
@admin_required
def get_stats():
    """Get basic statistics."""
    from ..extensions import db
    from ..models import Lead

    return jsonify({
        # "total_parts": db.session.query(Part).count(),
        # "total_vehicles": db.session.query(Vehicle).count(),
        "total_leads": db.session.query(Lead).count(),
        "new_leads": db.session.query(Lead).filter_by(status="new").count(),
        "assigned_leads": db.session.query(Lead).filter_by(status="assigned").count(),
    })


@admin_bp.get("/metrics")
@admin_required
def get_metrics():
    """Get GPT performance metrics (in-memory tracking)."""
    from ..services.gpt_service import GPTService

    avg_latency = (
        sum(GPTService.response_times) / len(GPTService.response_times)
        if GPTService.response_times
        else 0
    )

    accuracy = (
        GPTService.correct_intent_predictions / GPTService.total_intent_checks * 100
        if GPTService.total_intent_checks > 0
        else 0
    )

    return jsonify({
        "avg_latency": round(avg_latency, 3),
        "last_100_latencies": GPTService.response_times,
        "intent_accuracy_percent": round(accuracy, 2),
        "correct_intents": GPTService.correct_intent_predictions,
        "total_intent_checks": GPTService.total_intent_checks,
        "incorrect_intents": GPTService.incorrect_intent_predictions,
    })

# @admin_bp.post("/prompts")
# @admin_required
# def create_prompt():
#     data = request.json or {}
#     intent_key = data.get("intent_key", "").strip().lower()
#     prompt_text = data.get("prompt_text", "").strip()

#     if not intent_key or not prompt_text:
#         return jsonify({"error": "intent_key and prompt_text are required"}), 400

#     if IntentPrompt.query.filter_by(intent_key=intent_key).first():
#         return jsonify({"error": "Intent key already exists"}), 400

#     prompt = IntentPrompt(
#         intent_key=intent_key,
#         prompt_text=prompt_text,
#         is_active=data.get("is_active", True),
#     )
#     db.session.add(prompt)
#     db.session.commit()

#     return jsonify({"message": "Prompt created successfully", "id": prompt.id}), 201


# @admin_bp.put("/prompts/<int:prompt_id>")
# @admin_required
# def update_prompt(prompt_id):
#     prompt = IntentPrompt.query.get(prompt_id)
#     if not prompt:
#         return jsonify({"error": "Prompt not found"}), 404

#     data = request.json or {}

#     if "intent_key" in data:
#         prompt.intent_key = data["intent_key"].strip().lower()

#     if "prompt_text" in data:
#         prompt.prompt_text = data["prompt_text"].strip()

#     db.session.commit()

#     return jsonify({"message": "Prompt updated successfully"})
@admin_bp.get("/prompts")
@admin_required
def list_prompts():
    prompts = IntentPrompt.query.order_by(IntentPrompt.intent_key).all()
    return jsonify([
        {
            "id": p.id,
            "display_name": p.display_name,
            "intent_type": p.intent_type,
            "prompt_text": p.prompt_text,
            "reference_file": p.reference_file,  # 🔥 REQUIRED
            "parts_alias_text": p.parts_alias_text, # Added alias text
            "is_active": p.is_active,
        }
        for p in prompts
    ])

@admin_bp.post("/prompts")
@admin_required
def create_prompt():
    data = request.form
    file = request.files.get("reference_file")

    intent_key = data.get("intent_key", "").strip().lower()
    display_name = data.get("display_name", "").strip()
    prompt_text = data.get("prompt_text", "").strip()
    parts_alias_text = data.get("parts_alias_text", "").strip()
    intent_type = data.get("intent_type", "text").strip()

    if not intent_key or not display_name or not prompt_text:
        return jsonify({"error": "Required fields missing"}), 400

    # Relaxed validation for unified intent
    # if intent_type not in ("text", "image"):
    #     return jsonify({"error": "Invalid intent_type"}), 400

    if IntentPrompt.query.filter_by(intent_key=intent_key).first():
        return jsonify({"error": "Intent key already exists"}), 400

    reference_file = None
    reference_text = None

    # Unified: Allow file for any intent type
    if file:
        validate_reference_file(file)

        intent_dir = os.path.join(
            current_app.config["UPLOAD_ROOT"],
            "intents",
            intent_key
        )
        os.makedirs(intent_dir, exist_ok=True)

        filename = secure_filename(file.filename)
        path = os.path.join(intent_dir, filename)
        file.save(path)

        reference_file = f"intents/{intent_key}/{filename}"
        reference_text = extract_text_from_file(path)
    else:
        reference_file = None
        reference_text = None

    prompt = IntentPrompt(
        intent_key=intent_key,
        display_name=display_name,
        prompt_text=prompt_text,
        intent_type=intent_type,
        reference_file=reference_file,
        reference_text=reference_text,
        parts_alias_text=parts_alias_text,
        is_active=True,
    )

    db.session.add(prompt)
    db.session.commit()

    return jsonify({"message": "Prompt created", "id": prompt.id}), 201

@admin_bp.put("/prompts/<int:prompt_id>")
@admin_required
def update_prompt(prompt_id):
    prompt = IntentPrompt.query.get_or_404(prompt_id)

    data = request.form
    file = request.files.get("reference_file")

    if "intent_key" in data:
        return jsonify({"error": "intent_key cannot be modified"}), 400
    if data.get("remove_reference_file") == "true":
        prompt.reference_file = None
        prompt.reference_text = None

    prompt.display_name = data.get("display_name", prompt.display_name).strip()
    prompt.prompt_text = data.get("prompt_text", prompt.prompt_text).strip()
    if "parts_alias_text" in data:
        prompt.parts_alias_text = data.get("parts_alias_text", "").strip()

    intent_type = data.get("intent_type", prompt.intent_type).strip()
    # Relaxed validation
    # if intent_type not in ("text", "image"):
    #     return jsonify({"error": "Invalid intent_type"}), 400

    prompt.intent_type = intent_type

    if file:
        validate_reference_file(file)

        intent_dir = os.path.join(
            current_app.config["UPLOAD_ROOT"],
            "intents",
            prompt.intent_key
        )
        os.makedirs(intent_dir, exist_ok=True)

        filename = secure_filename(file.filename)
        path = os.path.join(intent_dir, filename)
        file.save(path)

        prompt.reference_file = f"intents/{prompt.intent_key}/{filename}"
        prompt.reference_text = extract_text_from_file(path)



    db.session.commit()
    return jsonify({"message": "Prompt updated"})


@admin_bp.patch("/prompts/<int:prompt_id>/toggle")
@admin_required
def toggle_prompt(prompt_id):
    prompt = IntentPrompt.query.get(prompt_id)
    if not prompt:
        return jsonify({"error": "Prompt not found"}), 404

    prompt.is_active = not prompt.is_active
    db.session.commit()

    return jsonify({"message": "Status updated", "is_active": prompt.is_active})


@admin_bp.delete("/prompts/<int:prompt_id>")
@admin_required
def delete_prompt(prompt_id):
    prompt = IntentPrompt.query.get(prompt_id)
    if not prompt:
        return jsonify({"error": "Prompt not found"}), 404

    db.session.delete(prompt)
    db.session.commit()

    return jsonify({"message": "Prompt deleted"})
