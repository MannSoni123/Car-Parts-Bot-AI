# # app/redis_client.py
# import redis
# import os

# REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
# REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
# REDIS_DB = int(os.environ.get("REDIS_DB", 0))

# # decode_responses=True so redis.publish returns regular strings
# redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


# import os
# import redis

# REDIS_URL = os.getenv("REDIS_URL")

# if not REDIS_URL:
#     raise RuntimeError(
#         "REDIS_URL is not set. "
#         "You must configure a Redis service (Upstash / Render Redis)."
#     )

# redis_client = redis.from_url(
#     REDIS_URL,
#     decode_responses=True,
# )
import os
import redis

REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    raise RuntimeError("REDIS_URL is not set")

redis_client = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=False,

    # 🔥 critical for Upstash + Gunicorn
    socket_timeout=5,
    socket_connect_timeout=5,
    retry_on_timeout=True,

    # 🔥 prevents dead TLS sockets
    health_check_interval=30,
)

