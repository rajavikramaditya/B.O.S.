"""B.O.S. ASGI entry point.

Run locally:   uvicorn main:app --reload        (from the backend/ directory)
In Docker:     see Dockerfile
"""

import logging

from api.app import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# HTTP client request logs include full URLs, and some APIs (e.g. Telegram) carry credentials in the path.
for noisy in ("httpx", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

app = create_app()
