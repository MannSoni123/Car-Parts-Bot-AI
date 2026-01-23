import os
os.environ['no_proxy'] = '*'
os.environ['NO_PROXY'] = '*'
import multiprocessing
multiprocessing.set_start_method("spawn", force=True)

from rq import Worker, Queue
from app import create_app
from app.redis_client import redis_client as redis_rq

# Create Flask app so that tasks can use current_app
app = create_app()

if __name__ == "__main__":
    with app.app_context():
        queue_names = ["whatsapp"]

        worker = Worker(
            [Queue(name, connection=redis_rq) for name in queue_names],
            connection=redis_rq
        )

        worker.work(with_scheduler=True)
