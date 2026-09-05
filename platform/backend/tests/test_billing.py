import os
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.billing import BillingCustomer
from app.schemas.billing import (
    AccountCreate,
    BillingAppCreate,
    EntitlementCreate,
    PriceCreate,
    ProductCreate,
)
from app.services import billing_service


class BillingServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(prefix="billing-service-", suffix=".db")
        os.close(fd)
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _seed_catalog(self) -> tuple[str, str]:
        with self.Session() as db:
            billing_service.create_or_update_app(
                db,
                BillingAppCreate(
                    key="energy_data_explorer",
                    name="Energy Data Explorer",
                ),
            )
            billing_service.create_or_update_entitlement(
                db,
                EntitlementCreate(
                    app_key="energy_data_explorer",
                    key="explorer_access",
                    name="Explorer Access",
                ),
            )
            billing_service.create_or_update_product(
                db,
                ProductCreate(
                    app_key="energy_data_explorer",
                    key="explorer_pro",
                    name="Explorer Pro",
                    stripe_product_id="prod_explorer_pro",
                ),
            )
            billing_service.create_or_update_price(
                db,
                PriceCreate(
                    product_key="explorer_pro",
                    key="explorer_pro_monthly",
                    stripe_price_id="price_explorer_pro_monthly",
                    entitlement_key="explorer_access",
                    currency="usd",
                    unit_amount=4900,
                    recurring_interval="month",
                    active=True,
                ),
            )
            account = billing_service.create_account(
                db,
                AccountCreate(
                    name="Acme Energy",
                    billing_email="billing@acme.test",
                ),
            )
            return account.id, "explorer_pro_monthly"

    def test_checkout_session_creates_customer_and_returns_checkout_url(self) -> None:
        account_id, price_key = self._seed_catalog()

        with patch.object(
            billing_service.stripe_service,
            "create_customer",
            return_value={"id": "cus_test_123"},
        ), patch.object(
            billing_service.stripe_service,
            "create_checkout_session",
            return_value={"id": "cs_test_123", "url": "https://checkout.stripe.test/session"},
        ):
            with self.Session() as db:
                session = billing_service.create_checkout_session(
                    db,
                    account_id=account_id,
                    price_key=price_key,
                    quantity=1,
                    success_url="https://app.example.com/billing/success",
                    cancel_url="https://app.example.com/billing/cancel",
                    caller_app_key="energy_data_explorer",
                )
                customer = db.query(BillingCustomer).filter_by(account_id=account_id).one()

        self.assertEqual("cs_test_123", session["session_id"])
        self.assertEqual("https://checkout.stripe.test/session", session["url"])
        self.assertEqual("cus_test_123", customer.stripe_customer_id)

    def test_subscription_webhook_grants_and_revokes_entitlement(self) -> None:
        account_id, _ = self._seed_catalog()

        created_event = {
            "id": "evt_subscription_created",
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": "sub_test_123",
                    "customer": "cus_test_123",
                    "status": "active",
                    "metadata": {
                        "account_id": account_id,
                        "app_key": "energy_data_explorer",
                    },
                    "current_period_start": 1_700_000_000,
                    "current_period_end": 1_700_259_200,
                    "cancel_at_period_end": False,
                    "latest_invoice": "in_test_123",
                    "items": {
                        "data": [
                            {
                                "price": {
                                    "id": "price_explorer_pro_monthly",
                                }
                            }
                        ]
                    },
                }
            },
        }
        deleted_event = {
            "id": "evt_subscription_deleted",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_test_123",
                    "customer": "cus_test_123",
                    "status": "canceled",
                    "metadata": {
                        "account_id": account_id,
                        "app_key": "energy_data_explorer",
                    },
                    "current_period_start": 1_700_000_000,
                    "current_period_end": 1_700_259_200,
                    "cancel_at_period_end": False,
                    "latest_invoice": "in_test_123",
                    "items": {
                        "data": [
                            {
                                "price": {
                                    "id": "price_explorer_pro_monthly",
                                }
                            }
                        ]
                    },
                }
            },
        }

        with patch.object(
            billing_service.stripe_service,
            "construct_webhook_event",
            side_effect=[created_event, deleted_event],
        ):
            with self.Session() as db:
                created = billing_service.process_stripe_webhook(
                    db,
                    payload=b"{}",
                    signature_header="t=1,v1=test",
                )
                created_status = created.status
                active_entitlements = billing_service.list_account_entitlements(
                    db,
                    account_id=account_id,
                    app_key="energy_data_explorer",
                    only_active=True,
                )

                deleted = billing_service.process_stripe_webhook(
                    db,
                    payload=b"{}",
                    signature_header="t=1,v1=test",
                )
                deleted_status = deleted.status
                all_entitlements = billing_service.list_account_entitlements(
                    db,
                    account_id=account_id,
                    app_key="energy_data_explorer",
                    only_active=False,
                )

        self.assertEqual("processed", created_status)
        self.assertEqual(1, len(active_entitlements))
        self.assertEqual("explorer_access", active_entitlements[0]["key"])
        self.assertEqual("processed", deleted_status)
        self.assertEqual(1, len(all_entitlements))
        self.assertEqual("inactive", all_entitlements[0]["status"])


if __name__ == "__main__":
    unittest.main()
