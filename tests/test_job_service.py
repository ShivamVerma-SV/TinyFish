import os
import unittest
from unittest.mock import patch

from backend.job_service import (
    TinyFishError,
    canonical_url,
    deduplicate_jobs,
    discover_jobs,
    has_individual_job_evidence,
    is_generic_page,
    preference_match,
)


PREFERENCES = {
    "role": "Software Engineer",
    "location": "Bengaluru, India",
    "locationScope": "preferred",
    "skills": ["Python"],
    "opportunityType": "Both",
    "experienceLevel": "Any",
    "useAgent": False,
    "maxResults": 16,
}


class JobServiceTests(unittest.TestCase):
    def test_canonical_url_removes_tracking_but_preserves_application_parameters(self):
        url = "https://jobs.lever.co/acme/123?utm_source=feed&team=platform"
        self.assertEqual(canonical_url(url), "https://jobs.lever.co/acme/123?team=platform")

    def test_generic_career_pages_are_rejected(self):
        self.assertTrue(is_generic_page("https://jobs.lever.co/acme", "Careers"))
        self.assertFalse(is_generic_page("https://jobs.lever.co/acme/1234", "Software Engineer"))

    def test_individual_listing_requires_fetched_job_evidence(self):
        url = "https://jobs.lever.co/acme/1234"
        self.assertTrue(has_individual_job_evidence(url, "Software Engineer", "About the role Qualifications Apply for this job"))
        self.assertFalse(has_individual_job_evidence(url, "Software Engineer", "Welcome to Acme"))

    def test_cross_portal_duplicate_prefers_verified_record(self):
        base = {"title": "Software Engineer", "company": "Acme", "description": "Short"}
        jobs = [
            {**base, "apply_url": "https://jobs.lever.co/acme/123", "verification": "discovered"},
            {**base, "apply_url": "https://boards.greenhouse.io/acme/jobs/456", "verification": "fetch_verified"},
        ]
        result = deduplicate_jobs(jobs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["verification"], "fetch_verified")

    def test_remote_only_filter_rejects_onsite_role(self):
        job = {
            "title": "Software Engineer",
            "description": "Build Python services",
            "location": "Bengaluru, India",
            "remote": False,
            "employmentType": "Full-time",
        }
        preferences = {**PREFERENCES, "locationScope": "remote", "location": ""}
        self.assertFalse(preference_match(job, preferences))

    def test_preferred_location_rejects_a_different_known_city(self):
        job = {
            "title": "Software Engineer",
            "description": "Build Python services",
            "location": "London, United Kingdom",
            "remote": False,
            "employmentType": "Full-time",
        }
        self.assertFalse(preference_match(job, PREFERENCES))

    @patch.dict(os.environ, {"TINYFISH_API_KEY": "test-key"})
    @patch("backend.job_service.tinyfish_fetch")
    @patch("backend.job_service.tinyfish_search", return_value=[])
    def test_empty_discovery_returns_a_complete_empty_state(self, _mock_search, mock_fetch):
        events = []
        result = discover_jobs(PREFERENCES, events.append)
        self.assertEqual(result["jobs"], [])
        self.assertEqual(result["summary"]["uniqueResults"], 0)
        mock_fetch.assert_not_called()
        self.assertTrue(any(event.get("phase") == "reading" and event.get("state") == "skipped" for event in events))

    @patch.dict(os.environ, {"TINYFISH_API_KEY": "test-key"})
    @patch("backend.job_service.tinyfish_fetch")
    @patch("backend.job_service.tinyfish_search")
    def test_partial_search_failure_keeps_successful_results(self, mock_search, mock_fetch):
        calls = 0

        def search_side_effect(_key, _plan, _location_code):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TinyFishError("Search", "Open web unavailable")
            if calls == 2:
                return [{
                    "title": "Job Application for Software Engineer at Acme",
                    "url": "https://jobs.lever.co/acme/1234",
                    "snippet": "Python full-time role in Bengaluru",
                }]
            return []

        mock_search.side_effect = search_side_effect
        mock_fetch.return_value = ([{
            "url": "https://jobs.lever.co/acme/1234",
            "title": "Job Application for Software Engineer at Acme",
            "text": "Location: Bengaluru, India\nAbout the role Build Python services. Qualifications: two years. Apply for this job.",
        }], [])

        events = []
        result = discover_jobs(PREFERENCES, events.append)
        self.assertEqual(result["summary"]["uniqueResults"], 1)
        self.assertEqual(result["summary"]["failedSources"], 1)
        self.assertTrue(result["warnings"])
        self.assertEqual(result["jobs"][0]["verification"], "fetch_verified")


if __name__ == "__main__":
    unittest.main()
