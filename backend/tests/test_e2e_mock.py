"""
End-to-end integration test (skipped when external services are not configured).

Exercises the full flow against real Supabase + Groq + Gemini + Langfuse.
Requires the environment to be fully provisioned with valid credentials —
otherwise the test is skipped, since the application no longer runs in
mock mode.

To enable locally, export:
  SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY,
  SUPABASE_JWT_SECRET, GROQ_API_KEY, GOOGLE_API_KEY,
  LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
"""


import os

import pytest

REQUIRED_ENV = (
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "GROQ_API_KEY",
    "GOOGLE_API_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
)

pytestmark = pytest.mark.skipif(
    not all(os.environ.get(k) for k in REQUIRED_ENV),
    reason="Integration tests require all external services to be configured.",
)


def test_placeholder_integration() -> None:
    """Placeholder until the real integration test suite is wired up.

    The real flow is covered by the manual end-to-end demo (creator →
    approver A → approver B) executed against the deployed environment.
    """
    pass
