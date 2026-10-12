from app.core.db import SessionLocal
from app.models import Payment
from app.services import payments as payments_service


def test_tariffs_are_seeded_with_prices_in_kopecks(api):
    response = api.get("/tariffs")

    assert response.status_code == 200
    tariffs = response.json()
    assert all(set(t) == {"id", "title", "price"} for t in tariffs)
    assert {t["title"]: t["price"] for t in tariffs} == {
        "basic": 990_000,
        "standard": 1_990_000,
        "premium": 2_990_000,
    }


def test_amount_without_promo_and_with_promo_in_any_case(create_payment, payment_status):
    # (тариф, промокод, ожидаемая скидка, ожидаемая сумма к оплате)
    cases = [
        ("standard", None, 0, 1_990_000),
        ("standard", "KVITTO10", 199_000, 1_791_000),
        ("standard", "kvitto10", 199_000, 1_791_000),
        ("basic", "KVITTO10", 99_000, 891_000),
        ("premium", None, 0, 2_990_000),
    ]
    for tariff, promo, discount, amount in cases:
        response = create_payment(tariff=tariff, promo_code=promo)

        label = f"{tariff} / {promo}"
        assert response.status_code == 201, label
        body = response.json()
        assert (body["discount"], body["amount"]) == (discount, amount), label
        assert body["status"] == "pending", label
        assert body["schedule"] is None and body["installment_months"] is None, label
        assert payment_status(body["id"]) == "pending", label


def test_installment_schedule_sums_to_amount_for_3_6_and_12_months(create_payment):
    # лишние копейки должны уйти в первые платежи.
    expected = {
        3: [663_334, 663_333, 663_333],
        6: [331_667] * 4 + [331_666] * 2,
        12: [165_834] * 4 + [165_833] * 8,
    }
    for months, schedule in expected.items():
        response = create_payment(method="installment", installment_months=months)

        assert response.status_code == 201, months
        body = response.json()
        assert body["installment_months"] == months
        assert body["schedule"] == schedule, months
        assert sum(body["schedule"]) == body["amount"] == 1_990_000, months

        with SessionLocal() as db:  # в БД лежит то же самое
            assert db.get(Payment, body["id"]).schedule == schedule, months


def test_schedule_is_built_from_the_discounted_amount(create_payment):
    response = create_payment(method="installment", installment_months=12, promo_code="kvitto10")

    body = response.json()
    assert body["amount"] == 1_791_000
    assert body["schedule"] == [149_250] * 12
    assert sum(body["schedule"]) == body["amount"]


def test_invalid_requests_are_rejected_and_create_nothing(create_payment, payment_count):
    bad_requests = {
        "неизвестный промокод": {"promo_code": "NOPE"},
        "неизвестный тариф": {"tariff_id": 9999},
        "рассрочка без срока": {"method": "installment"},
        "недопустимый срок рассрочки": {"method": "installment", "installment_months": 5},
        "срок рассрочки для карты": {"method": "card", "installment_months": 3},
        "неизвестный способ оплаты": {"method": "cash"},
        "некорректный email": {"email": "not-an-email"},
    }
    for name, fields in bad_requests.items():
        assert create_payment(**fields).status_code == 422, name

    assert payment_count() == 0


def test_same_idempotency_key_returns_same_payment(create_payment, payment_count):
    headers = {"Idempotency-Key": "order-42"}

    first = create_payment(headers=headers)
    second = create_payment(headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()
    assert payment_count() == 1

    # другой ключ и запрос без ключа создают новые платежи
    assert create_payment(headers={"Idempotency-Key": "order-43"}).status_code == 201
    assert create_payment().status_code == 201
    assert payment_count() == 3


def test_unique_index_resolves_race_between_check_and_insert(
    create_payment, payment_count, monkeypatch
):
    headers = {"Idempotency-Key": "race-1"}
    first = create_payment(headers=headers)
    assert first.status_code == 201

    real_find = payments_service.find_by_idempotency_key
    calls = []

    def blind_first_lookup(db, key):
        calls.append(key)
        return None if len(calls) == 1 else real_find(db, key)

    monkeypatch.setattr(payments_service, "find_by_idempotency_key", blind_first_lookup)

    second = create_payment(headers=headers)

    assert len(calls) == 2  # сработал запасной поиск после IntegrityError
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert payment_count() == 1


def test_get_payment_returns_what_was_created(api, create_payment):
    created = create_payment(
        method="installment", installment_months=6, promo_code="kvitto10"
    ).json()

    response = api.get(f"/payments/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created
    assert set(created) == {
        "id", "status", "tariff_id", "amount", "discount", "method",
        "installment_months", "schedule", "email", "created_at",
    }  # fmt: skip


def test_get_missing_payment_is_404(api):
    assert api.get("/payments/999999").status_code == 404


def test_list_payments_filters_by_email_and_status(api, create_payment, webhook):
    first = create_payment(email="a@example.com").json()
    create_payment(email="a@example.com")
    create_payment(email="b@example.com")
    assert webhook(first["id"], "succeeded").status_code == 200

    by_email = api.get("/payments", params={"email": "A@example.com"}).json()
    by_status = api.get("/payments", params={"status": "succeeded"}).json()
    both = api.get("/payments", params={"email": "a@example.com", "status": "pending"}).json()

    assert [p["email"] for p in by_email] == ["a@example.com"] * 2
    assert [p["id"] for p in by_status] == [first["id"]]
    assert len(both) == 1 and both[0]["status"] == "pending"
    assert api.get("/payments", params={"status": "bogus"}).status_code == 422