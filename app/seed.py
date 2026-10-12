from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tariff

DEFAULT_TARIFFS: list[tuple[str, int]] = [
    ("basic", 990_000),
    ("standard", 1_990_000),
    ("premium", 2_990_000),
]


def seed_tariffs(db: Session) -> None:
    existing = set(db.scalars(select(Tariff.title)))
    for title, price in DEFAULT_TARIFFS:
        if title not in existing:
            db.add(Tariff(title=title, price=price))
    db.commit()