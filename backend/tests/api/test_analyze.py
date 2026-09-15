"""Uses TestClient(app) directly, so requests go through the real
app.db.get_db dependency — i.e. these hit the actual dev Postgres
database (same one scripts/run_ingest.py populates), not the isolated
"_test" database the db_session fixture uses elsewhere. Requires the bulk
pipeline to have been run.
"""

from fastapi.testclient import TestClient

from app.auth.dependency import require_authenticated_user
from app.auth.firebase import AuthenticatedUser
from app.main import app

# /api/analyze is gated behind a real Firebase ID token, which tests can't
# mint. Override with a fake authenticated user — these tests are about the
# analyze pipeline, not the auth layer (that's tests/auth/test_firebase.py).
app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
    uid="test-uid", email="test@example.com"
)

client = TestClient(app)


def test_analyze_resolves_known_drugs_end_to_end():
    # app.linking.resolver.resolve is real now (Module 1) — this is a full
    # round trip: tokenize -> gazetteer match -> interaction lookup,
    # against real loaded data (both Aspirin and Ibuprofen are canonical
    # ingredients with a real DDInter rule between them).
    response = client.post("/api/analyze", json={"input": "Aspirin, Ibuprofen"})
    assert response.status_code == 200

    body = response.json()
    assert len(body["items"]) == 2
    assert all(item["recognized"] for item in body["items"])
    names = {item["medication"]["name"] for item in body["items"]}
    assert names == {"aspirin", "ibuprofen"}


def test_analyze_reports_unrecognized_for_unknown_drug_name():
    response = client.post("/api/analyze", json={"input": "SomeCompletelyUnknownDrugXYZ"})
    assert response.status_code == 200

    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["recognized"] is False
    assert body["items"][0]["medication"] is None


def test_analyze_resolves_a_prescription_style_token_with_dose_and_frequency():
    response = client.post("/api/analyze", json={"input": "Tab. Paracetamol 500mg BD"})
    assert response.status_code == 200

    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["recognized"] is True
    assert body["items"][0]["medication"]["name"] == "acetaminophen"


def test_analyze_rejects_empty_input():
    response = client.post("/api/analyze", json={"input": ""})
    assert response.status_code == 422


def test_analyze_rejects_request_with_no_auth_token():
    # Temporarily drop the module-level override to confirm the real gate
    # is actually wired in, not just bypassed everywhere.
    del app.dependency_overrides[require_authenticated_user]
    try:
        response = client.post("/api/analyze", json={"input": "Aspirin"})
        assert response.status_code == 401
    finally:
        app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
            uid="test-uid", email="test@example.com"
        )
