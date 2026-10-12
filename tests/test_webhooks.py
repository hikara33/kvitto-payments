from app.core.config import settings


def test_webhook_applies_allowed_transitions(api, create_payment, webhook, payment_status):
    paid = create_payment().json()["id"]
    failed = create_payment().json()["id"]

    response = webhook(paid, "succeeded")
    assert response.status_code == 200
    assert response.json() == {"result": "ok"}
    assert payment_status(paid) == "succeeded"

    assert webhook(paid, "refunded").status_code == 200
    assert api.get(f"/payments/{paid}").json()["status"] == "refunded"

    assert webhook(failed, "failed").status_code == 200
    assert payment_status(failed) == "failed"


def test_forbidden_transition_is_409_and_keeps_status(create_payment, webhook, payment_status):
    scenarios = [
        ([], "refunded"),  # pending -> refunded
        ([], "pending"),  # pending -> pending
        (["succeeded"], "failed"),
        (["succeeded"], "succeeded"),  # повтор того же статуса
        (["failed"], "succeeded"),  # из failed выхода нет
        (["succeeded", "refunded"], "succeeded"),  # из refunded выхода нет
    ]
    for path, forbidden in scenarios:
        payment_id = create_payment().json()["id"]
        for step in path:
            assert webhook(payment_id, step).status_code == 200
        before = payment_status(payment_id)

        response = webhook(payment_id, forbidden)

        label = f"{before} -> {forbidden}"
        assert response.status_code == 409, label
        assert response.json() == {"error": "invalid_transition"}, label
        assert payment_status(payment_id) == before, label


def test_webhook_for_unknown_payment_is_404(api, webhook):
    assert webhook(999_999, "succeeded").status_code == 404


def test_webhook_rejects_missing_or_wrong_signature(create_payment, webhook, payment_status):
    payment_id = create_payment().json()["id"]

    for signature in [None, "", "deadbeef", "ключ".encode()]:
        response = webhook(payment_id, "succeeded", signature=signature)
        assert response.status_code == 401, signature

    assert payment_status(payment_id) == "pending"
    assert webhook(999_999, "succeeded", signature="deadbeef").status_code == 401


def test_signature_check_is_off_when_secret_is_not_set(
    create_payment, webhook, payment_status, monkeypatch
):
    monkeypatch.setattr(settings, "webhook_secret", None)
    payment_id = create_payment().json()["id"]

    response = webhook(payment_id, "succeeded", signature=None)

    assert response.status_code == 200
    assert payment_status(payment_id) == "succeeded"