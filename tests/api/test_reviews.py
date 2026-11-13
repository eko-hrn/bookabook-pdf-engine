"""Tests for Review Workflow endpoints."""

from __future__ import annotations

import io
from fastapi.testclient import TestClient


def _upload_book(client: TestClient, pdf_bytes: bytes) -> str:
    """Helper to upload a PDF and return its document_id."""
    files = {"file": ("book.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    res = client.post("/api/documents/upload", files=files)
    assert res.status_code == 201
    return res.json()["document_id"]


def test_create_review_session(client: TestClient, sample_6page_pdf_bytes: bytes) -> None:
    """Verify creating a review session from an uploaded document."""
    doc_id = _upload_book(client, sample_6page_pdf_bytes)

    payload = {
        "document_id": doc_id,
        "metadata": {"reviewer_assigned": "lead_operator"},
    }
    res = client.post("/api/reviews/sessions", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert "session_id" in data
    assert data["metadata"]["document_id"] == doc_id
    assert data["metadata"]["reviewer_assigned"] == "lead_operator"
    assert data["document_summary"]["status"] == "PENDING_REVIEW"
    assert len(data["page_records"]) == 6

    # Verify initial page states are PENDING
    for p in data["page_records"]:
        assert p["review_decision"] == "PENDING"


def test_create_review_session_duplicate_fails(
    client: TestClient, sample_6page_pdf_bytes: bytes
) -> None:
    """Verify attempting to create a duplicate session ID returns 409 Conflict."""
    doc_id = _upload_book(client, sample_6page_pdf_bytes)
    custom_sid = "custom-session-uuid-12345"

    payload = {"document_id": doc_id, "session_id": custom_sid}
    res1 = client.post("/api/reviews/sessions", json=payload)
    assert res1.status_code == 201

    # Attempt to reuse the same session ID
    res2 = client.post("/api/reviews/sessions", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"].lower()


def test_create_review_session_nonexistent_document_fails(client: TestClient) -> None:
    """Verify creating a session for missing document returns 404."""
    payload = {"document_id": "doc_nonexistent"}
    res = client.post("/api/reviews/sessions", json=payload)
    assert res.status_code == 404


def test_get_review_session(client: TestClient, sample_6page_pdf_bytes: bytes) -> None:
    """Verify retrieving full review session by ID."""
    doc_id = _upload_book(client, sample_6page_pdf_bytes)
    create_res = client.post("/api/reviews/sessions", json={"document_id": doc_id})
    sid = create_res.json()["session_id"]

    res = client.get(f"/api/reviews/sessions/{sid}")
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"] == sid
    assert data["metadata"]["document_id"] == doc_id


def test_get_nonexistent_review_session_fails(client: TestClient) -> None:
    """Verify requesting non-existent session returns 404."""
    res = client.get("/api/reviews/sessions/missing-session-id")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_get_page_review_record(client: TestClient, sample_6page_pdf_bytes: bytes) -> None:
    """Verify retrieving an individual page review record."""
    doc_id = _upload_book(client, sample_6page_pdf_bytes)
    create_res = client.post("/api/reviews/sessions", json={"document_id": doc_id})
    sid = create_res.json()["session_id"]

    # Page 1 (Cover Spread)
    p1_res = client.get(f"/api/reviews/sessions/{sid}/pages/1")
    assert p1_res.status_code == 200
    p1 = p1_res.json()
    assert p1["pdf_page_number"] == 1
    assert p1["layout_type"] == "COVER_SPREAD"
    assert p1["review_decision"] == "PENDING"

    # Out of range page 99
    p99_res = client.get(f"/api/reviews/sessions/{sid}/pages/99")
    assert p99_res.status_code == 404


def test_record_page_decision(client: TestClient, sample_6page_pdf_bytes: bytes) -> None:
    """Verify recording an explicit operator decision."""
    doc_id = _upload_book(client, sample_6page_pdf_bytes)
    create_res = client.post("/api/reviews/sessions", json={"document_id": doc_id})
    sid = create_res.json()["session_id"]

    decision_payload = {
        "decision": "APPROVED",
        "reviewer_id": "operator_alice",
        "notes": "Cover geometry verified and approved manually",
    }
    dec_res = client.post(
        f"/api/reviews/sessions/{sid}/pages/1/decision",
        json=decision_payload,
    )
    assert dec_res.status_code == 200
    p1 = dec_res.json()
    assert p1["review_decision"] == "APPROVED"
    assert p1["reviewer_id"] == "operator_alice"
    assert p1["notes"] == "Cover geometry verified and approved manually"


def test_invalid_decision_transition_fails(
    client: TestClient, sample_6page_pdf_bytes: bytes
) -> None:
    """Verify illegal transitions (e.g. reverting APPROVED back to PENDING) fail with 400."""
    doc_id = _upload_book(client, sample_6page_pdf_bytes)
    create_res = client.post("/api/reviews/sessions", json={"document_id": doc_id})
    sid = create_res.json()["session_id"]

    # Approve page 1
    client.post(
        f"/api/reviews/sessions/{sid}/pages/1/decision",
        json={"decision": "APPROVED", "reviewer_id": "op_alice"},
    )

    # Attempt to revert to PENDING
    revert_res = client.post(
        f"/api/reviews/sessions/{sid}/pages/1/decision",
        json={"decision": "PENDING", "reviewer_id": "op_alice"},
    )
    assert revert_res.status_code == 400
    assert "cannot revert" in revert_res.json()["detail"].lower()


def test_update_page_notes(client: TestClient, sample_6page_pdf_bytes: bytes) -> None:
    """Verify updating review notes without changing decision state."""
    doc_id = _upload_book(client, sample_6page_pdf_bytes)
    create_res = client.post("/api/reviews/sessions", json={"document_id": doc_id})
    sid = create_res.json()["session_id"]

    note_payload = {
        "reviewer_id": "operator_bob",
        "notes": "Checked alignment with physical proof sheet",
    }
    res = client.patch(
        f"/api/reviews/sessions/{sid}/pages/2/notes",
        json=note_payload,
    )
    assert res.status_code == 200
    p2 = res.json()
    assert p2["notes"] == "Checked alignment with physical proof sheet"
    # Decision state remains PENDING
    assert p2["review_decision"] == "PENDING"


def test_update_page_notes_empty_fails(
    client: TestClient, sample_6page_pdf_bytes: bytes
) -> None:
    """Verify empty notes are rejected."""
    doc_id = _upload_book(client, sample_6page_pdf_bytes)
    create_res = client.post("/api/reviews/sessions", json={"document_id": doc_id})
    sid = create_res.json()["session_id"]

    # min_length=1 in pydantic schema yields 422 Unprocessable Entity
    res = client.patch(
        f"/api/reviews/sessions/{sid}/pages/2/notes",
        json={"reviewer_id": "operator_bob", "notes": ""},
    )
    assert res.status_code == 422


def test_session_audit_history(client: TestClient, sample_6page_pdf_bytes: bytes) -> None:
    """Verify chronological audit trail tracks all session events."""
    doc_id = _upload_book(client, sample_6page_pdf_bytes)
    create_res = client.post("/api/reviews/sessions", json={"document_id": doc_id})
    sid = create_res.json()["session_id"]

    # Event 1: Approve page 1
    client.post(
        f"/api/reviews/sessions/{sid}/pages/1/decision",
        json={"decision": "APPROVED", "reviewer_id": "op_alice", "notes": "Approved"},
    )

    # Event 2: Update notes on page 2
    client.patch(
        f"/api/reviews/sessions/{sid}/pages/2/notes",
        json={"reviewer_id": "op_bob", "notes": "Checking page 2"},
    )

    # Fetch full history
    hist_res = client.get(f"/api/reviews/sessions/{sid}/history")
    assert hist_res.status_code == 200
    history = hist_res.json()
    assert len(history) >= 3  # SESSION_CREATED, DECISION_RECORDED, NOTES_UPDATED

    event_types = [h["event_type"] for h in history]
    assert "SESSION_CREATED" in event_types
    assert "DECISION_RECORDED" in event_types
    assert "NOTES_UPDATED" in event_types

    # Filter history by page 1
    p1_hist_res = client.get(f"/api/reviews/sessions/{sid}/history?page_number=1")
    assert p1_hist_res.status_code == 200
    p1_history = p1_hist_res.json()
    assert all(h["pdf_page_number"] == 1 for h in p1_history)


def test_session_summary(client: TestClient, sample_6page_pdf_bytes: bytes) -> None:
    """Verify session summary correctly computes state aggregations."""
    doc_id = _upload_book(client, sample_6page_pdf_bytes)
    create_res = client.post("/api/reviews/sessions", json={"document_id": doc_id})
    sid = create_res.json()["session_id"]

    # Initial summary: all 6 pages pending
    sum_res1 = client.get(f"/api/reviews/sessions/{sid}/summary")
    assert sum_res1.status_code == 200
    s1 = sum_res1.json()
    assert s1["total_pages"] == 6
    assert s1["pending_pages_count"] == 6
    assert s1["approved_pages_count"] == 0
    assert s1["status"] == "PENDING_REVIEW"

    # Approve page 1
    client.post(
        f"/api/reviews/sessions/{sid}/pages/1/decision",
        json={"decision": "APPROVED", "reviewer_id": "op_alice"},
    )

    # Updated summary
    sum_res2 = client.get(f"/api/reviews/sessions/{sid}/summary")
    assert sum_res2.status_code == 200
    s2 = sum_res2.json()
    assert s2["pending_pages_count"] == 5
    assert s2["approved_pages_count"] == 1
    assert s2["status"] == "PARTIALLY_REVIEWED"


def test_unknown_layout_approval_safety_rejection(
    client: TestClient, sample_unknown_layout_pdf_bytes: bytes
) -> None:
    """Verify UNKNOWN_LAYOUT page cannot be approved and raises 400."""
    doc_id = _upload_book(client, sample_unknown_layout_pdf_bytes)
    create_res = client.post("/api/reviews/sessions", json={"document_id": doc_id})
    assert create_res.status_code == 201
    sid = create_res.json()["session_id"]

    # Attempt to approve page with UNKNOWN_LAYOUT
    res = client.post(
        f"/api/reviews/sessions/{sid}/pages/1/decision",
        json={"decision": "APPROVED", "reviewer_id": "op_alice"},
    )
    assert res.status_code == 400
    assert "unknown_layout" in res.json()["detail"].lower()
