import json
import time
from typing import Any, Dict, Optional
from app.redis_client import redis_client

# ================= CONFIG =================

SESSION_TTL = 900  # 15 minutes
SESSION_KEY_PREFIX = "chat:session:"

# ================= HELPERS =================

def _session_key(user_id: str) -> str:
    return f"{SESSION_KEY_PREFIX}{user_id}"


# ================= CORE API =================

def get_session(user_id: str) -> Dict[str, Any]:
    """
    Fetch an existing session or create a new one.
    """
    key = _session_key(user_id)
    raw = redis_client.get(key)

    if raw:
        try:
            return json.loads(raw)
        except Exception:
            # Corrupted session → reset safely
            pass

    return _new_session()


def save_session(user_id: str, session: Dict[str, Any]) -> None:
    """
    Persist session with TTL refresh.
    """
    key = _session_key(user_id)
    session["meta"]["updated_at"] = int(time.time())

    redis_client.setex(
        key,
        SESSION_TTL,
        json.dumps(session)
    )


def clear_session(user_id: str) -> None:
    """
    Explicitly clear a user session.
    """
    redis_client.delete(_session_key(user_id))


# ================= SESSION STRUCTURE =================

def _new_session() -> Dict[str, Any]:
    """
    Base session structure.
    Keep this SMALL and STRUCTURED.
    """
    now = int(time.time())

    return {
        "entities": {
            "vin": None,           # Stored VIN
            "part": None           # Future use
        },
        "context": {
            "vin_set_at": None     # Timestamp when VIN was stored
        },
        "state": {
            "awaiting": None       # e.g. vin_confirmation, workshop_confirmation
        },
        "meta": {
            "created_at": now,
            "updated_at": now
        }
    }


# ================= ENTITY HELPERS =================

def set_vin(session: Dict[str, Any], vin: str) -> None:
    """
    Store VIN in session.
    """
    session["entities"]["vin"] = vin
    session["context"]["vin_set_at"] = int(time.time())


def get_vin(session: Dict[str, Any]) -> Optional[str]:
    """
    Get VIN if present and not expired logically.
    TTL is handled by Redis, this is extra safety.
    """
    return session["entities"].get("vin")


def clear_vin(session: Dict[str, Any]) -> None:
    session["entities"]["vin"] = None
    session["context"]["vin_set_at"] = None


# ================= STATE HELPERS =================

def set_awaiting(session: Dict[str, Any], state: Optional[str]) -> None:
    """
    Set or clear awaiting conversational state.
    """
    session["state"]["awaiting"] = state


def get_awaiting(session: Dict[str, Any]) -> Optional[str]:
    return session["state"].get("awaiting")
