"""
Admin API endpoints for configuration management.
"""
from flask import Blueprint, current_app, jsonify, request, g
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
SUPER_ADMIN_SECRET = os.getenv("SUPER_ADMIN_SECRET")


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.cookies.get("admin_session")
        if not token:
            return jsonify({"error": "Unauthorized"}), 401
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            g.admin_role = payload.get("role", "admin")
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Session expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid session"}), 401
        return f(*args, **kwargs)
    return wrapper


def super_admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.cookies.get("admin_session")
        if not token:
            return jsonify({"error": "Unauthorized"}), 401
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            if payload.get("role") != "super_admin":
                return jsonify({"error": "Forbidden: Super Admin access required"}), 403
            g.admin_role = payload.get("role", "super_admin")
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
    
    role = None
    if token == SUPER_ADMIN_SECRET:
        role = "super_admin"
    elif token == ADMIN_SECRET:
        role = "admin"
        
    if not role:
        return jsonify({"error": "Invalid admin token"}), 401

    payload = {
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=6)
    }

    jwt_token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    resp = make_response(jsonify({"success": True, "role": role}))
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
        "authenticated": True,
        "role": getattr(g, "admin_role", "admin")
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

    total_customers = db.session.query(Lead.whatsapp_user_id).distinct().count()

    return jsonify({
        "total_customers": total_customers
    })

@admin_bp.get("/users")
@admin_required
def get_users():
    """Get list of unique users who sent queries."""
    from ..extensions import db
    from ..models import Lead
    from sqlalchemy import func

    # Group by whatsapp_user_id to get total queries and last active time
    users_data = db.session.query(
        Lead.whatsapp_user_id,
        func.count(Lead.id).label('total_queries'),
        func.max(Lead.created_at).label('last_active')
    ).group_by(Lead.whatsapp_user_id).order_by(func.max(Lead.created_at).desc()).all()

    uae_tz = timezone(timedelta(hours=4))

    return jsonify([
        {
            "whatsapp_user_id": u.whatsapp_user_id,
            "total_queries": u.total_queries,
            # Database stores in UTC. Convert to UAE time (+4)
            "last_active": u.last_active.replace(tzinfo=timezone.utc).astimezone(uae_tz).isoformat() if u.last_active else None
        }
        for u in users_data
    ])

@admin_bp.get("/trends")
@admin_required
def get_trends():
    """Get daily and weekly query volume trends."""
    from ..extensions import db
    from ..models import Lead
    import datetime
    from collections import defaultdict
    from datetime import timezone, timedelta

    start_param = request.args.get('start')
    end_param = request.args.get('end')

    uae_tz = timezone(timedelta(hours=4))

    # Fetch all leads from the last 90 days (approx 12 weeks)
    now = datetime.datetime.now(uae_tz)
    
    # Base query for default trends
    ninety_days_ago = now - datetime.timedelta(days=90)
    base_query = db.session.query(Lead.created_at)

    if start_param and end_param:
        try:
            # Parse YYYY-MM-DD
            start_date = datetime.datetime.strptime(start_param, "%Y-%m-%d").replace(tzinfo=uae_tz)
            end_date = datetime.datetime.strptime(end_param, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=uae_tz
            )
            
            # Since DB is UTC, we need to convert our UAE bounds to UTC for the query
            start_utc = start_date.astimezone(timezone.utc)
            end_utc = end_date.astimezone(timezone.utc)
            
            # Fetch custom range separately
            custom_leads = base_query.filter(Lead.created_at >= start_utc, Lead.created_at <= end_utc).all()
            
            custom_counts = defaultdict(int)
            for (created_at,) in custom_leads:
                if not created_at: continue
                if created_at.tzinfo is None: created_at = created_at.replace(tzinfo=timezone.utc)
                # Convert back to UAE for grouping
                created_at_uae = created_at.astimezone(uae_tz)
                custom_counts[created_at_uae.strftime("%b %d")] += 1
                
            # Generate continuous days list between start and end
            custom_trend = []
            delta = (end_date.date() - start_date.date()).days
            for i in range(delta + 1):
                target_date = start_date + datetime.timedelta(days=i)
                lbl = target_date.strftime("%b %d")
                custom_trend.append({"date": lbl, "count": custom_counts.get(lbl, 0)})
                
            return jsonify({
                "custom": custom_trend
            })
            
        except ValueError:
            pass # Invalid dates fall back to default

    # Default logic (last 30 days & 12 weeks)
    ninety_days_ago_utc = ninety_days_ago.astimezone(timezone.utc)
    recent_leads = base_query.filter(Lead.created_at >= ninety_days_ago_utc).all()

    daily_counts = defaultdict(int)
    weekly_counts = defaultdict(int)

    for (created_at,) in recent_leads:
        if not created_at:
            continue
            
        # Ensure UTC timezone awareness if naive
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        # Convert to UAE
        created_at_uae = created_at.astimezone(uae_tz)

        # 1. Daily Aggregation (Format: "Feb 23")
        day_str = created_at_uae.strftime("%b %d")
        daily_counts[day_str] += 1

        # 2. Weekly Aggregation (Group by Monday of that week)
        monday = created_at_uae - datetime.timedelta(days=created_at_uae.weekday())
        week_str = f"Week of {monday.strftime('%b %d')}"
        weekly_counts[week_str] += 1

    # Format for Recharts consumption
    
    # Sort last 30 days chronologically using the last 30 days
    last_30_days = []
    for i in range(29, -1, -1):
        target_date = now - datetime.timedelta(days=i)
        lbl = target_date.strftime("%b %d")
        last_30_days.append({"date": lbl, "count": daily_counts.get(lbl, 0)})

    # Sort last 12 weeks chronologically
    last_12_weeks = []
    for i in range(11, -1, -1):
        target_date = now - datetime.timedelta(weeks=i)
        monday = target_date - datetime.timedelta(days=target_date.weekday())
        lbl = f"Week of {monday.strftime('%b %d')}"
        last_12_weeks.append({"date": lbl, "count": weekly_counts.get(lbl, 0)})

    return jsonify({
        "daily": last_30_days,
        "weekly": last_12_weeks
    })

@admin_bp.get("/peak-usage")
@admin_required
def get_peak_usage():
    """Get the hourly usage distribution for a specific date."""
    from ..extensions import db
    from ..models import Lead
    from datetime import time, timezone, timedelta
    
    uae_tz = timezone(timedelta(hours=4))

    date_param = request.args.get('date')
    
    # Default to today in UAE if no date provided
    now_uae = datetime.now(uae_tz)
    target_date = now_uae.date()
    
    if date_param:
        try:
            target_date = datetime.strptime(date_param, "%Y-%m-%d").date()
        except ValueError:
            pass # Fallback to today if parsing fails
            
    # Create start and end datetime bounds strictly for that day (in UAE)
    start_dt_uae = datetime.combine(target_date, time.min).replace(tzinfo=uae_tz)
    end_dt_uae = datetime.combine(target_date, time.max).replace(tzinfo=uae_tz)
    
    # Convert to UTC to query DB
    start_utc = start_dt_uae.astimezone(timezone.utc)
    end_utc = end_dt_uae.astimezone(timezone.utc)

    # Query leads for that specific day
    daily_leads = db.session.query(Lead.created_at).filter(
        Lead.created_at >= start_utc,
        Lead.created_at <= end_utc
    ).all()

    # Initialize all 24 hours with 0
    hourly_counts = {f"{i:02d}:00": 0 for i in range(24)}
    
    for (created_at,) in daily_leads:
        if not created_at: continue
        # Ensure UTC timezone awareness
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
            
        # Convert back to UAE to bin into the right hour
        created_at_uae = created_at.astimezone(uae_tz)
        hour_str = created_at_uae.strftime("%H:00")
        hourly_counts[hour_str] += 1

    # Format for charting
    hourly_data = [{"hour": hour, "count": count} for hour, count in hourly_counts.items()]
    
    # Calculate Peak Hour (highest count)
    peak_hour = "N/A"
    if daily_leads:
        peak_item = max(hourly_data, key=lambda x: x["count"])
        if peak_item["count"] > 0:
            peak_hour = peak_item["hour"]

    return jsonify({
        "date": target_date.strftime("%Y-%m-%d"),
        "peak_hour": peak_hour,
        "hourly_data": hourly_data
    })

@admin_bp.get("/vin-performance")
@admin_required
def get_vin_performance():
    """Get aggregated VIN search metrics across all users."""
    from ..extensions import db
    from ..models import User
    from sqlalchemy import func

    # Calculate sums for the three vin tracking columns
    metrics = db.session.query(
        func.sum(User.total_vin_search).label('total_searches'),
        func.sum(User.success_vin_search).label('successful_searches'),
        func.sum(User.failed_vin_search).label('failed_searches')
    ).first()

    total = int(metrics.total_searches or 0)
    success = int(metrics.successful_searches or 0)
    failed = int(metrics.failed_searches or 0)

    # Get individual user stats for those who have searched at least once
    users_data = db.session.query(User).filter(User.total_vin_search > 0).all()
    users_list = [
        {
            "whatsapp_id": u.whatsapp_id,
            "total_searches": u.total_vin_search,
            "successful_searches": u.success_vin_search,
            "failed_searches": u.failed_vin_search
        }
        for u in users_data
    ]

    from ..session_store import get_failed_vins
    
    recent_failed_vins = get_failed_vins(limit=50)

    return jsonify({
        "total_searches": total,
        "successful_searches": success,
        "failed_searches": failed,
        "users": users_list,
        "recent_failed_vins": recent_failed_vins
    })

@admin_bp.get("/analytics/top-parts")
@admin_required
def get_top_parts():
    """Get the most searched part numbers and item descriptions."""
    from ..extensions import db
    from ..models import PartSearchLog
    from sqlalchemy import func, desc

    # Group by part_number and count
    top_pns = db.session.query(
        PartSearchLog.part_number,
        func.count(PartSearchLog.id).label('count')
    ).filter(
        PartSearchLog.part_number.isnot(None)
    ).group_by(
        PartSearchLog.part_number
    ).order_by(
        desc('count')
    ).limit(10).all()

    # Group by item_description and count
    top_descs = db.session.query(
        PartSearchLog.item_description,
        func.count(PartSearchLog.id).label('count')
    ).filter(
        PartSearchLog.item_description.isnot(None)
    ).group_by(
        PartSearchLog.item_description
    ).order_by(
        desc('count')
    ).limit(10).all()

    # User search metrics: group by whatsapp_user_id and count searches
    user_pns = db.session.query(
        PartSearchLog.whatsapp_user_id,
        func.count(PartSearchLog.id).label('pn_count')
    ).filter(
        PartSearchLog.part_number.isnot(None)
    ).group_by(
        PartSearchLog.whatsapp_user_id
    ).all()

    user_descs = db.session.query(
        PartSearchLog.whatsapp_user_id,
        func.count(PartSearchLog.id).label('desc_count')
    ).filter(
        PartSearchLog.item_description.isnot(None)
    ).group_by(
        PartSearchLog.whatsapp_user_id
    ).all()

    # Combine user metrics
    user_stats = {}
    for uid, count in user_pns:
        user_stats[uid] = {"whatsapp_user_id": uid, "part_number_searches": count, "item_description_searches": 0}
    for uid, count in user_descs:
        if uid not in user_stats:
            user_stats[uid] = {"whatsapp_user_id": uid, "part_number_searches": 0, "item_description_searches": 0}
        user_stats[uid]["item_description_searches"] = count

    return jsonify({
        "top_part_numbers": [{"name": pn, "count": count} for pn, count in top_pns],
        "top_item_descriptions": [{"name": desc, "count": count} for desc, count in top_descs],
        "user_demand_stats": list(user_stats.values())
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

@admin_bp.get("/out-of-stock")
@admin_required
def get_out_of_stock():
    """Get list of out-of-stock part numbers from search logs."""
    from ..extensions import db
    from ..models import PartSearchLog, Stock
    import re
    
    # Query logs matching WhatsApp users who searched for specific part numbers
    logs = db.session.query(
        PartSearchLog.whatsapp_user_id,
        PartSearchLog.part_number,
        PartSearchLog.created_at
    ).filter(PartSearchLog.part_number.isnot(None)).order_by(PartSearchLog.created_at.desc()).all()
    
    # Get set of all currently stocked item part numbers (normalized)
    stock_pns_raw = db.session.query(Stock.part_number, Stock.tag).filter(Stock.qty > 0).all()
    
    def normalize(pn):
        return re.sub(r'[^A-Z0-9]', '', str(pn).upper()) if pn else ''

    in_stock_normalized_set = set()
    for row in stock_pns_raw:
        in_stock_normalized_set.add(normalize(row.part_number))
        in_stock_normalized_set.add(normalize(row.tag))
        
    from datetime import timezone, timedelta
    uae_tz = timezone(timedelta(hours=4))
    
    out_of_stock_list = []
    grouped = {}
    
    for log in logs:
        norm_pn = normalize(log.part_number)
        
        # Check if requested PN is not available in our local DB stock list
        if norm_pn and norm_pn not in in_stock_normalized_set:
            created_at = log.created_at
            if created_at is None:
                continue
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            
            created_at_uae = created_at.astimezone(uae_tz)
            date_str = created_at_uae.strftime("%Y-%m-%d")
            
            key = (log.whatsapp_user_id, date_str)
            if key not in grouped:
                grouped[key] = {
                    "wp_id": log.whatsapp_user_id,
                    "part_numbers_set": set(),
                    "part_numbers": [],
                    "date": created_at.isoformat()
                }
                
            if log.part_number not in grouped[key]["part_numbers_set"]:
                grouped[key]["part_numbers_set"].add(log.part_number)
                grouped[key]["part_numbers"].append(log.part_number)
                
    for val in grouped.values():
        out_of_stock_list.append({
            "wp_id": val["wp_id"],
            "part_numbers": val["part_numbers"],
            "date": val["date"]
        })
                
    return jsonify({
        "out_of_stock_items": out_of_stock_list
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
@super_admin_required
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
            "clarification_rules": p.clarification_rules, # Added dynamic clarification rules
            "vip_numbers": p.vip_numbers, # 🔥 Added VIP Numbers
            "is_active": p.is_active,
        }
        for p in prompts
    ])

@admin_bp.post("/prompts")
@super_admin_required
def create_prompt():
    data = request.form
    file = request.files.get("reference_file")

    intent_key = data.get("intent_key", "").strip().lower()
    display_name = data.get("display_name", "").strip()
    prompt_text = data.get("prompt_text", "").strip()
    parts_alias_text = data.get("parts_alias_text", "").strip()
    clarification_rules = data.get("clarification_rules", "").strip()
    vip_numbers = data.get("vip_numbers", "").strip()
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
        clarification_rules=clarification_rules,
        vip_numbers=vip_numbers,
        is_active=True,
    )

    db.session.add(prompt)
    db.session.commit()

    return jsonify({"message": "Prompt created", "id": prompt.id}), 201

@admin_bp.put("/prompts/<int:prompt_id>")
@super_admin_required
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
    if "clarification_rules" in data:
        prompt.clarification_rules = data.get("clarification_rules", "").strip()
    if "vip_numbers" in data:
        prompt.vip_numbers = data.get("vip_numbers", "").strip()

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
@super_admin_required
def toggle_prompt(prompt_id):
    prompt = IntentPrompt.query.get(prompt_id)
    if not prompt:
        return jsonify({"error": "Prompt not found"}), 404

    prompt.is_active = not prompt.is_active
    db.session.commit()

    return jsonify({"message": "Status updated", "is_active": prompt.is_active})


@admin_bp.delete("/prompts/<int:prompt_id>")
@super_admin_required
def delete_prompt(prompt_id):
    prompt = IntentPrompt.query.get(prompt_id)
    if not prompt:
        return jsonify({"error": "Prompt not found"}), 404

    db.session.delete(prompt)
    db.session.commit()

    return jsonify({"message": "Prompt deleted"})

@admin_bp.get("/analytics/export")
@admin_required
def export_analytics():
    """Export analytics data as CSV."""
    import csv
    import io
    from ..extensions import db
    from ..models import Lead, User
    from sqlalchemy import func
    from datetime import timezone, timedelta

    uae_tz = timezone(timedelta(hours=4))

    # 1. Fetch user query data
    users_data = db.session.query(
        Lead.whatsapp_user_id,
        func.count(Lead.id).label('total_queries'),
        func.max(Lead.created_at).label('last_active')
    ).group_by(Lead.whatsapp_user_id).all()

    # Create a dictionary for quick lookup by whatsapp_id
    analytics_dict = {}
    for u in users_data:
        # Convert UTC to UAE timezone for last active
        last_active_uae = ""
        if u.last_active:
             last_active_uae = u.last_active.replace(tzinfo=timezone.utc).astimezone(uae_tz).strftime("%Y-%m-%d %H:%M:%S")
        
        analytics_dict[u.whatsapp_user_id] = {
            "whatsapp_id": u.whatsapp_user_id,
            "total_queries": u.total_queries,
            "last_active": last_active_uae,
            "total_vin_searches": 0,
            "success_vin_searches": 0,
            "failed_vin_searches": 0,
            "searched_part_numbers": set(),
            "searched_item_descriptions": set()
        }

    # 2. Fetch VIN search data
    vin_users = db.session.query(User).all()

    for vu in vin_users:
        # User might have done VIN search but no queries (or vice versa), ensure they are in dict
        if vu.whatsapp_id not in analytics_dict:
            analytics_dict[vu.whatsapp_id] = {
                 "whatsapp_id": vu.whatsapp_id,
                 "total_queries": 0,
                 "last_active": "N/A",
                 "total_vin_searches": 0,
                 "success_vin_searches": 0,
                 "failed_vin_searches": 0,
                 "searched_part_numbers": set(),
                 "searched_item_descriptions": set()
            }
        
        analytics_dict[vu.whatsapp_id]["total_vin_searches"] = vu.total_vin_search
        analytics_dict[vu.whatsapp_id]["success_vin_searches"] = vu.success_vin_search
        analytics_dict[vu.whatsapp_id]["failed_vin_searches"] = vu.failed_vin_search

    # 3. Fetch Part Search Logs
    from ..models import PartSearchLog
    part_logs = db.session.query(PartSearchLog).all()
    for log in part_logs:
        if log.whatsapp_user_id not in analytics_dict:
            analytics_dict[log.whatsapp_user_id] = {
                 "whatsapp_id": log.whatsapp_user_id,
                 "total_queries": 0,
                 "last_active": "N/A",
                 "total_vin_searches": 0,
                 "success_vin_searches": 0,
                 "failed_vin_searches": 0,
                 "searched_part_numbers": set(),
                 "searched_item_descriptions": set()
            }
        if log.part_number:
            analytics_dict[log.whatsapp_user_id]["searched_part_numbers"].add(log.part_number)
        if log.item_description:
            analytics_dict[log.whatsapp_user_id]["searched_item_descriptions"].add(log.item_description)

    # 4. Generate CSV
    si = io.StringIO()
    cw = csv.writer(si)
    
    # Write Headers
    cw.writerow([
        "WhatsApp ID", 
        "Total Queries", 
        "Last Active (UAE Time)", 
        "Total VIN Searches", 
        "Success VIN Searches", 
        "Failed VIN Searches",
        "Total Searched Part Numbers",
        "Searched Part Numbers",
        "Total Searched Item Descriptions",
        "Searched Item Descriptions"
    ])
    
    # Write Data Rows
    for uid, data in analytics_dict.items():
        cw.writerow([
            data["whatsapp_id"],
            data["total_queries"],
            data["last_active"],
            data["total_vin_searches"],
            data["success_vin_searches"],
            data["failed_vin_searches"],
            len(data["searched_part_numbers"]),
            " | ".join(data["searched_part_numbers"]),
            len(data["searched_item_descriptions"]),
            " | ".join(data["searched_item_descriptions"])
        ])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=analytics_export.csv"
    output.headers["Content-type"] = "text/csv"
    return output
