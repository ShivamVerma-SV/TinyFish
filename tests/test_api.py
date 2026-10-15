import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api import app


VALID_REQUEST = {
    "role": "Product Designer",
    "location": "London, United Kingdom",
    "locationScope": "preferred",
    "skills": ["Figma", "Design systems"],
    "opportunityType": "Full-time",
    "experienceLevel": "Mid-level",
    "useAgent": False,
    "maxResults": 10,
}


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_preferred_location_is_validated(self):
        response = self.client.post("/api/search", json={**VALID_REQUEST, "location": ""})
        self.assertEqual(response.status_code, 422)

    @patch("backend.api.discover_jobs")
    def test_search_stream_reports_real_events_and_result(self, mock_discover):
        def fake_discover(preferences, publish):
            publish({"type": "progress", "phase": "discovering", "state": "complete", "message": "Discovery finished"})
            return {
                "jobs": [],
                "sources": [],
                "warnings": [],
                "summary": {
                    "uniqueResults": 0,
                    "verifiedResults": 0,
                    "searchResultsScreened": 0,
                    "pagesInspected": 0,
                    "successfulSources": 6,
                    "failedSources": 0,
                },
                "searchedAt": "2026-10-15T00:00:00+00:00",
            }

        mock_discover.side_effect = fake_discover
        response = self.client.post("/api/search", json=VALID_REQUEST)
        self.assertEqual(response.status_code, 200)
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual(events[0]["phase"], "discovering")
        self.assertEqual(events[-1]["type"], "complete")
        self.assertEqual(events[-1]["result"]["jobs"], [])


if __name__ == "__main__":
    unittest.main()
