# # app/routes/sse.py
# from flask import Blueprint, Response
# from ..redis_client import redis_client
# import json

# sse_bp = Blueprint("sse", __name__)

# @sse_bp.route("/events")
# def events():
#     def stream():
#         pubsub = redis_client.pubsub()
#         pubsub.subscribe("chatbot_events")

#         # listen() blocks, yields messages as they arrive
#         for message in pubsub.listen():
#             if message is None:
#                 continue
#             if message.get("type") != "message":
#                 continue
#             data = message.get("data")
#             # data is already a JSON string from publisher; send as SSE data
#             yield f"data: {data}\n\n"

#     return Response(stream(), mimetype="text/event-stream")
# app/routes/sse.py
from flask import Blueprint, Response
from ..redis_client import redis_client
import time

sse_bp = Blueprint("sse", __name__)

@sse_bp.route("/events")
def events():
    def stream():
        pubsub = redis_client.pubsub()
        pubsub.subscribe("chatbot_events")

        last_ping = time.time()

        try:
            for message in pubsub.listen():
                now = time.time()

                # 🔹 Heartbeat every 15s (keeps proxies alive)
                if now - last_ping > 15:
                    yield ": ping\n\n"
                    last_ping = now

                if not message:
                    continue

                if message.get("type") != "message":
                    continue

                data = message.get("data")

                # Redis returns bytes → decode safely
                if isinstance(data, bytes):
                    data = data.decode("utf-8")

                yield f"data: {data}\n\n"

        except GeneratorExit:
            # Client disconnected
            pass

        finally:
            pubsub.close()

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 🚨 REQUIRED for Nginx/Render
        },
    )
