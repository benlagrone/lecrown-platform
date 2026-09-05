import unittest
from datetime import date
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.services import gov_contract_service as service


PROJECT = {
    "ProjectID": "252263",
    "ReferenceID": "IT-123",
    "ProjectName": "Network support",
    "ProjectVisibilityID": "1",
    "DateClose": "2030-09-08 19:00:00",
    "DepartmentID": "6122",
}


class DartSourceTest(unittest.TestCase):
    def response(self, projects):
        response = Mock()
        response.json.return_value = {"success": 1, "payload": {"projects": projects}}
        return response

    def test_public_import_is_repeatable_and_excludes_private_projects(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        response = self.response({
            "public": PROJECT,
            "private": {**PROJECT, "ProjectID": "private", "ProjectVisibilityID": "2"},
        })
        with Session(engine) as db, patch.object(service.requests, "get", return_value=response):
            for _ in range(2):
                run = service.refresh_dart_contracts(db)
                self.assertEqual("completed", run.status)
            items = service.list_contracts(db, source=service.DART_PROCUREMENT_SOURCE_NAME,
                                          matches_only=False, open_only=False, limit=20)
            self.assertEqual(1, len(items))
            self.assertEqual("IT-123", items[0].solicitation_id)
            self.assertEqual(date(2030, 9, 8), items[0].due_date)
            self.assertEqual("https://dart.bonfirehub.com/opportunities/252263", items[0].source_url)
        engine.dispose()

    def test_empty_collection_and_duplicate_ids(self):
        for projects, count in (({}, 0), ([], 0), ([PROJECT, PROJECT], 1)):
            with self.subTest(projects=projects), patch.object(service.requests, "get", return_value=self.response(projects)):
                self.assertEqual(count, len(service.fetch_dart_contracts().records))

    def test_invalid_responses_are_not_reported_as_successful_empty_imports(self):
        for payload in ([], {"success": 0}, {"success": 1, "payload": {}},
                        {"success": 1, "payload": {"projects": [{"ProjectName": "Missing ID"}]}}):
            response = Mock()
            response.json.return_value = payload
            with self.subTest(payload=payload), patch.object(service.requests, "get", return_value=response):
                with self.assertRaises(service.GovContractSourceError):
                    service.fetch_dart_contracts()
