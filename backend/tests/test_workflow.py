import os
import tempfile
import unittest
import uuid

from fastapi.testclient import TestClient

_database_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_database_file.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_database_file.name.replace(os.sep, '/')}"
os.environ["APP_ENV"] = "development"
os.environ["JWT_SECRET"] = "tests-only-secret-that-is-long-enough-123456"
os.environ["SEED_DEMO_DATA"] = "true"
os.environ.pop("OPENAI_API_KEY", None)

from app.main import app


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()
        login = cls.client.post(
            "/api/auth/login",
            json={"email": "demo.admin@smartcampus.example.com", "password": "CampusDemo2026!"},
        )
        if login.status_code != 200:
            raise AssertionError(login.text)
        cls.admin_token = login.json()["access_token"]

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        try:
            os.unlink(_database_file.name)
        except OSError:
            pass

    def candidate(self):
        email = f"candidate-{uuid.uuid4().hex}@example.com"
        result = self.client.post(
            "/api/auth/register",
            json={"name": "Test Candidate", "email": email, "password": "OrientationTest2026!"},
        )
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()["access_token"]

    def staff_token(self, email):
        result = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": "CampusDemo2026!"},
        )
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()["access_token"]

    def test_guest_conversation_can_be_linked_to_new_account(self):
        created = self.client.post("/api/guest/sessions")
        self.assertEqual(created.status_code, 201, created.text)
        guest = created.json()
        headers = {"X-Guest-Token": guest["token"]}
        sent = self.client.post(
            f"/api/guest/sessions/{guest['id']}/messages",
            headers=headers,
            json={"content": "What official information does the project brief give about IIT Licence and engineering?"},
        )
        self.assertEqual(sent.status_code, 201, sent.text)
        self.assertTrue(sent.json()["assistant_message"]["citations"])

        email = f"linked-{uuid.uuid4().hex}@example.com"
        registered = self.client.post(
            "/api/auth/register",
            headers=headers,
            json={"name": "Linked Candidate", "email": email, "password": "OrientationTest2026!"},
        )
        self.assertEqual(registered.status_code, 201, registered.text)
        self.assertTrue(registered.json()["guest_session_linked"])
        account_headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
        conversations = self.client.get("/api/conversations", headers=account_headers)
        self.assertEqual(conversations.status_code, 200, conversations.text)
        self.assertEqual(len(conversations.json()), 1)
        forbidden = self.client.get(
            f"/api/guest/sessions/{guest['id']}", headers=headers
        )
        self.assertEqual(forbidden.status_code, 409)

    def test_preregistration_requires_consent_and_academic_review_is_scoped(self):
        token = self.candidate()
        headers = {"Authorization": f"Bearer {token}"}
        programs = self.client.get("/api/programs", headers=headers).json()
        program = next(item for item in programs if item["institution"] == "IIT")
        no_consent = self.client.post(
            "/api/preregistrations",
            headers=headers,
            json={"program_id": program["id"], "consent": False},
        )
        self.assertEqual(no_consent.status_code, 422)

        created = self.client.post(
            "/api/preregistrations",
            headers=headers,
            json={"program_id": program["id"], "consent": True},
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["registration"]["status"], "pending_review")
        self.assertEqual(created.json()["notification"]["delivery_status"], "not_configured")

        isb_headers = {
            "Authorization": f"Bearer {self.staff_token('demo.isb@smartcampus.example.com')}"
        }
        review = self.client.patch(
            f"/api/preregistrations/{created.json()['registration']['id']}",
            headers=isb_headers,
            json={"status": "approved", "notes": "Human review"},
        )
        self.assertEqual(review.status_code, 403)

        iit_headers = {
            "Authorization": f"Bearer {self.staff_token('demo.iit@smartcampus.example.com')}"
        }
        review = self.client.patch(
            f"/api/preregistrations/{created.json()['registration']['id']}",
            headers=iit_headers,
            json={"status": "approved", "notes": "Human review"},
        )
        self.assertEqual(review.status_code, 200, review.text)

    def test_questionnaire_is_advisory_and_cannot_be_submitted_twice(self):
        token = self.candidate()
        headers = {"Authorization": f"Bearer {token}"}
        program = self.client.get("/api/programs", headers=headers).json()[0]
        quiz = self.client.post(
            f"/api/quizzes?program_id={program['id']}", headers=headers
        )
        self.assertEqual(quiz.status_code, 201, quiz.text)
        quiz_data = quiz.json()
        self.assertIn("Exploratory", quiz_data["interpretation"])
        answers = {quiz_data["questions"][0]["id"]: ["mathematics"]}
        submitted = self.client.post(
            f"/api/quizzes/{quiz_data['id']}/submit",
            headers=headers,
            json={"answers": answers},
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertIn("not a knowledge or admission score", submitted.json()["summary"])
        again = self.client.post(
            f"/api/quizzes/{quiz_data['id']}/submit",
            headers=headers,
            json={"answers": answers},
        )
        self.assertEqual(again.status_code, 409)

    def test_staff_routes_reject_candidate_accounts(self):
        headers = {"Authorization": f"Bearer {self.candidate()}"}
        result = self.client.get("/api/admin/users", headers=headers)
        self.assertEqual(result.status_code, 403)
        result = self.client.post("/api/admin/evaluations", headers=headers)
        self.assertEqual(result.status_code, 403)


    def test_program_catalog_api_enforces_admin_scope_and_round_trips_program(self):
        token = self.candidate()
        candidate_headers = {"Authorization": f"Bearer {token}"}
        admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        payload = {
            "code": f"TEST-{uuid.uuid4().hex[:12]}",
            "institution": "IIT",
            "title": "API contract sample",
            "level": "Licence",
            "summary": "Test-only record, not official programme information.",
            "duration": "",
            "prerequisites": "",
            "tuition": "",
            "subjects": ["informatique"],
            "careers": [],
            "source_url": None,
            "is_sample": True,
            "is_active": True,
        }

        forbidden = self.client.post(
            "/api/programs", headers=candidate_headers, json=payload
        )
        self.assertEqual(forbidden.status_code, 403)

        created = self.client.post("/api/programs", headers=admin_headers, json=payload)
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["code"], payload["code"])
        self.assertTrue(created.json()["is_sample"])

        listed = self.client.get("/api/programs", headers=candidate_headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertIn(created.json()["id"], {item["id"] for item in listed.json()})

        duplicate = self.client.post(
            "/api/programs", headers=admin_headers, json=payload
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_admin_evaluation_reports_multilingual_retrieval_metrics(self):
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        result = self.client.post("/api/admin/evaluations", headers=headers)
        self.assertEqual(result.status_code, 200, result.text)
        evaluation = result.json()
        self.assertEqual(len(evaluation["cases"]), 6)
        self.assertEqual(
            {check["metric"] for check in evaluation["checks"]},
            {
                "language_detection",
                "institution_retrieval_recall",
                "expected_source_recall",
            },
        )
        self.assertTrue(
            all("expected_source_retrieved" in case for case in evaluation["cases"])
        )
        self.assertTrue(
            all(check["passed"] for check in evaluation["checks"]),
            evaluation["checks"],
        )
        self.assertIn("not an academic or model-quality benchmark", evaluation["suite"])


    def test_chunk_index_supports_reindex_and_chunk_citations(self):
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        reindexed = self.client.post("/api/admin/documents/reindex", headers=headers)
        self.assertEqual(reindexed.status_code, 200, reindexed.text)
        body = reindexed.json()
        self.assertGreaterEqual(body["documents"], 1)
        self.assertGreater(body["chunks"], body["documents"])

        documents = self.client.get("/api/admin/documents", headers=headers).json()
        self.assertTrue(all(document["chunks"] > 0 for document in documents))

        guest = self.client.post("/api/guest/sessions").json()
        sent = self.client.post(
            f"/api/guest/sessions/{guest['id']}/messages",
            headers={"X-Guest-Token": guest["token"]},
            json={"content": "Quels sont les frais du cycle préparatoire à l'IIT ?"},
        )
        self.assertEqual(sent.status_code, 201, sent.text)
        citations = sent.json()["assistant_message"]["citations"]
        self.assertTrue(citations)
        self.assertIn("snippet", citations[0])
        self.assertTrue(citations[0]["snippet"])


if __name__ == "__main__":
    unittest.main()
