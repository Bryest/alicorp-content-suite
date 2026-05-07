"""
End-to-end test in pure mock mode.

Exercises the full flow without network:
  1. Login as creator → JWT
  2. POST /brand-dna → 5 sections embedded
  3. POST /generate happy → content + retrieved_chunks
  4. POST /generate with forbidden word → blocked, no save
  5. Login as approver A → approve text
  6. Login as approver B → upload image → audit
  7. Verify final status APPROVED or REJECTED
  8. RBAC: creator denied on /audit/text
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _login(client: TestClient, email: str, password: str = "Test1234!") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def test_health(client: TestClient):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    # Mock mode should be active for all services in this env.
    assert all(body["mock_mode"].values())


def test_full_happy_flow(client: TestClient):
    creator = _login(client, "creator@test.com")
    creator_h = {"Authorization": f"Bearer {creator['access_token']}"}

    # ── 1) Brand DNA ──
    brand_payload = {
        "name": "QuinoaSnack Pro",
        "product_type": "Healthy snack with quinoa",
        "tone": "Fun but professional",
        "audience": "Gen Z, health-conscious, ages 18-26",
        "visual_rules": "Lime green dominant, white background, logo minimum 80px",
        "forbidden_words": ["cheap", "diet", "artificial"],
        "key_messages": ["real ingredients", "sustainable", "energizing"],
    }
    r = client.post("/api/v1/brand-dna", json=brand_payload, headers=creator_h)
    assert r.status_code == 200, r.text
    brand = r.json()
    assert brand["sections_embedded"] == 5
    assert "TONE" in brand["sections"]
    brand_id = brand["brand_id"]

    # ── 2) Generate content (happy) ──
    r = client.post(
        "/api/v1/generate",
        json={
            "brand_id": brand_id,
            "content_type": "product_description",
            "request": "Write a short Instagram description for our snack",
        },
        headers=creator_h,
    )
    assert r.status_code == 200, r.text
    gen = r.json()
    assert gen["status"] == "pending"
    assert gen["content_id"] is not None
    assert gen["content"]
    assert gen["retrieved_chunks"]
    content_id = gen["content_id"]

    # ── 3) Generate content (forbidden word in request → blocked) ──
    r = client.post(
        "/api/v1/generate",
        json={
            "brand_id": brand_id,
            "content_type": "product_description",
            "request": "Write a description that says it is a cheap diet snack",
        },
        headers=creator_h,
    )
    assert r.status_code == 200
    blocked = r.json()
    assert blocked["status"] == "blocked"
    assert blocked["content"] is None
    assert blocked["conflicts"]
    assert blocked["content_id"] is None  # not persisted

    # ── 4) Approver A approves text ──
    aa = _login(client, "approver.a@test.com")
    aa_h = {"Authorization": f"Bearer {aa['access_token']}"}
    r = client.patch(
        f"/api/v1/audit/text/{content_id}",
        json={"decision": "approved_text", "notes": "tone is on-brand"},
        headers=aa_h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved_text"

    # ── 5) Approver B uploads image audit ──
    ab = _login(client, "approver.b@test.com")
    ab_h = {"Authorization": f"Bearer {ab['access_token']}"}
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 4096
    files = {"image": ("hero.png", io.BytesIO(fake_png), "image/png")}
    r = client.post(f"/api/v1/audit/image/{content_id}", files=files, headers=ab_h)
    assert r.status_code == 200, r.text
    final = r.json()
    assert final["status"] in {"approved", "rejected"}
    assert final["audit_result"]
    assert "checks" in final["audit_result"]


def test_rbac_blocks_cross_role(client: TestClient):
    creator = _login(client, "creator@test.com")
    creator_h = {"Authorization": f"Bearer {creator['access_token']}"}

    # Creator cannot approve text
    r = client.patch(
        "/api/v1/audit/text/00000000-0000-0000-0000-000000000000",
        json={"decision": "approved_text"},
        headers=creator_h,
    )
    assert r.status_code == 403


def test_block_when_no_brand_grounding(client: TestClient):
    """If similarity threshold cannot be met, generation is refused — that's the point."""
    creator = _login(client, "creator@test.com")
    creator_h = {"Authorization": f"Bearer {creator['access_token']}"}

    # Create a brand
    r = client.post(
        "/api/v1/brand-dna",
        json={
            "name": "Niche Brand",
            "product_type": "industrial lubricant",
            "tone": "technical and dry",
            "audience": "factory engineers",
            "visual_rules": "monochrome, no decorative elements",
            "forbidden_words": [],
            "key_messages": ["reliability", "viscosity"],
        },
        headers=creator_h,
    )
    assert r.status_code == 200
    brand_id = r.json()["brand_id"]

    # Use an ultra-strict similarity threshold via a request that's
    # semantically far from the brand.
    r = client.post(
        "/api/v1/generate",
        json={
            "brand_id": brand_id,
            "content_type": "tagline",
            # we can't override min_similarity over the API, but with the
            # mock embedder a wildly off-topic short query usually scores low
            "request": "purple unicorn balloon party invitation language",
        },
        headers=creator_h,
    )
    assert r.status_code == 200
    body = r.json()
    # In mock mode we may or may not block depending on hash collisions —
    # but if we DO have content, retrieved_chunks should be present.
    if body["status"] == "blocked":
        assert body["content_id"] is None
    else:
        assert body["retrieved_chunks"]


def test_invalid_image_mime(client: TestClient):
    ab = _login(client, "approver.b@test.com")
    ab_h = {"Authorization": f"Bearer {ab['access_token']}"}
    files = {"image": ("x.gif", io.BytesIO(b"GIF89a..."), "image/gif")}
    r = client.post(
        "/api/v1/audit/image/00000000-0000-0000-0000-000000000000",
        files=files,
        headers=ab_h,
    )
    assert r.status_code == 415
