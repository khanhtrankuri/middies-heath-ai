import os


# CI and unit tests must never download or allocate the production model.
os.environ.setdefault("MEDDIES_MODEL_PROVIDER", "stub")
os.environ.setdefault("MODEL_PROVIDER", "stub")
os.environ.setdefault("RAG_ENABLED", "false")
