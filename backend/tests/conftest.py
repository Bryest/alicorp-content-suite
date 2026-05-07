"""Pytest config — make sure the backend package is importable."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root
sys.path.insert(0, str(ROOT))

# Force mock mode for tests by clearing any leaked env keys.
for k in (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_JWT_SECRET",
    "GROQ_API_KEY",
    "GOOGLE_API_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
):
    os.environ.pop(k, None)
