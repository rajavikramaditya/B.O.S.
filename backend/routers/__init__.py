"""Feature-wise API routers (AGENTS rule 2/4: single responsibility per domain).

Each module owns one HTTP feature domain and exposes a `router` APIRouter that
`main.py` mounts. Routers depend on services/db and the shared `app_core`
singletons only — never on `main` — to keep coupling loose (rule 1).
"""
