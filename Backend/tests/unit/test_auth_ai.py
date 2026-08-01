from __future__ import annotations

import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.domain.models import Asset, User, Warranty
from app.services.ai_agent import query_asset_insights
from app.services.auth import AuthenticatedUser, UserRole, create_access_token, hash_password, verify_password


class AuthAndAiTests(unittest.TestCase):
    def test_password_hashing_and_token_payload(self) -> None:
        user = User(id=7, username="operator", password_hash=hash_password("correct horse battery"), role="VIEW")
        self.assertNotEqual(user.password_hash, "correct horse battery")
        self.assertTrue(verify_password("correct horse battery", user.password_hash))
        self.assertFalse(verify_password("wrong password", user.password_hash))
        token = create_access_token(user)
        self.assertEqual(token.count("."), 1)
        self.assertEqual(AuthenticatedUser(7, "operator", UserRole.VIEW).role, UserRole.VIEW)

    def test_ai_service_builds_mockable_asset_context(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            asset = Asset(asset_tag="FOS-1", type="Laptop", manufacturer="HP", model="840", ram_mb=4096, cpu_name="i3")
            session.add(asset)
            session.flush()
            session.add(Warranty(asset_id=asset.id, vendor="HP", start_date=date.today(), end_date=date.today()))
            session.commit()
            result = query_asset_insights(
                session,
                asset.id,
                backend=lambda context, config: {
                    "summary": context["asset"]["manufacturer"],
                    "warnings": [],
                    "warranty": context["warranty"],
                    "model": config["model"],
                },
            )
        self.assertEqual(result["summary"], "HP")
        self.assertEqual(result["warranty"]["vendor"], "HP")


if __name__ == "__main__":
    unittest.main()
