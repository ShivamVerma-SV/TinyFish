"""Live job discovery using TinyFish Search, Fetch, and optional Agent verification.

The original Streamlit app's discovery, verification, filtering, and ranking behavior
lives here without any presentation concerns so it can be tested and served over HTTP.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests


SEARCH_URL = "https://api.search.tinyfish.ai"
FETCH_URL = "https://api.fetch.tinyfish.ai"
AGENT_URL = "https://agent.tinyfish.ai/v1/automation/run"

TRUSTED_JOB_HOSTS = (
    "jobs.lever.co",
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "jobs.ashbyhq.com",
    "jobs.smartrecruiters.com",
    "myworkdayjobs.com",
    "workdayjobs.com",
    "jobs.jobvite.com",
    "careers.icims.com",
    "jobs.paylocity.com",
    "jobs.dayforcehcm.com",
    "jobs.personio.com",
    "jobs.recruitee.com",
    "apply.workable.com",
)

BLOCKED_HOSTS = (
    "instagram.com",
    "facebook.com",
    "linkedin.com",
    "x.com",
    "twitter.com",
    "reddit.com",
    "youtube.com",
    "tiktok.com",
    "threads.net",
    "indeed.com",
    "internshala.com",
    "glassdoor.com",
    "naukri.com",
    "foundit.in",
)

GENERIC_PATH_PARTS = (
    "/search",
    "/job-search",
    "/jobs/search",
    "/careers",
    "/career-home",
    "/open-positions",
    "/job-openings",
    "/opportunities",
    "/departments",
    "/locations",
    "/teams",
    "/all-jobs",
    "/joblist",
    "/job-list",
)

KNOWN_SKILLS = (
    "Python",
    "Java",
    "JavaScript",
    "TypeScript",
    "React",
    "Node.js",
    "Django",
    "Flask",
    "FastAPI",
    "Spring Boot",
    "Go",
    "Rust",
    "C++",
    "C#",
    "SQL",
    "PostgreSQL",
    "MongoDB",
    "AWS",
    "Azure",
    "GCP",
    "Docker",
    "Kubernetes",
    "Figma",
    "Product Design",
    "Machine Learning",
    "Data Analysis",
)

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gh_src",
    "source",
    "ref",
}

ProgressCallback = Callable[[dict[str, Any]], None]


class TinyFishError(RuntimeError):
    """A sanitized TinyFish request failure safe to return to the client."""

    def __init__(self, service: str, message: str, status_code: int | None = None):
        super().__init__(message)
        self.service = service
        self.status_code = status_code


@dataclass
class SourceState:
    id: str
    label: str
    status: str = "pending"
    discovered_count: int = 0
    verified_count: int = 0
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "status": self.status,
            "discoveredCount": self.discovered_count,
            "verifiedCount": self.verified_count,
            "error": self.error,
        }


@dataclass
class DiscoveryContext:
    preferences: dict[str, Any]
    progress: ProgressCallback
    sources: dict[str, SourceState] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def phase(self, phase: str, state: str, message: str, **extra: Any) -> None:
        self.progress({"type": "progress", "phase": phase, "state": state, "message": message, **extra})

    def source(self, source: SourceState) -> None:
        self.sources[source.id] = source
        self.progress({"type": "source", "source": source.as_dict()})


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def api_headers(key: str) -> dict[str, str]:
    return {"X-API-Key": key, "Content-Type": "application/json"}


def normalize_url(value: Any) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    if value.startswith("//"):
        value = "https:" + value
    elif not value.startswith(("http://", "https://")):
        value = "https://" + value
    try:
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return ""
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc.lower(),
                parsed.path.rstrip("/") or "/",
                parsed.params,
                parsed.query,
                "",
            )
        )
    except ValueError:
        return ""


def canonical_url(value: Any) -> str:
    normalized = normalize_url(value)
    if not normalized:
        return ""
    parsed = urlparse(normalized)
    query = urlencode([(key, val) for key, val in parse_qsl(parsed.query) if key.lower() not in TRACKING_PARAMS])
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", query, "")).lower()


def host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def source_host(url: str) -> str:
    return urlparse(url).netloc.lower().split(":")[0].removeprefix("www.")


def is_blocked_source(url: str) -> bool:
    host = source_host(url)
    return any(host_matches(host, domain) for domain in BLOCKED_HOSTS)


def is_trusted_job_host(url: str) -> bool:
    host = source_host(url)
    return any(host_matches(host, domain) for domain in TRUSTED_JOB_HOSTS)


def is_generic_page(url: str, title: str = "") -> bool:
    parsed = urlparse(url)
    path = (parsed.path or "/").lower().rstrip("/") or "/"
    title_l = clean(title).lower()
    if is_blocked_source(url):
        return True
    if path in ("", "/", "/jobs", "/careers", "/career", "/search", "/jobs/search"):
        return True
    if any(part in path for part in GENERIC_PATH_PARTS):
        detail = bool(
            re.search(r"/(jobs?|job-details?|requisitions?|positions?|openings?)/[^/?#]+(?:/[^/?#]+)?$", path)
        )
        if not detail:
            return True
    generic_titles = {
        "careers",
        "career opportunities",
        "jobs",
        "job search",
        "open positions",
        "job openings",
        "search jobs",
        "all jobs",
        "opportunities",
        "job listings",
        "find jobs",
        "job market",
        "job vacancies",
    }
    return title_l in generic_titles or title_l.startswith(("search results for", "careers at ", "login"))


def title_looks_like_job(title: Any) -> bool:
    title_l = clean(title).lower()
    if len(title_l) < 5:
        return False
    blocked = (
        "search jobs",
        "job search",
        "career opportunities",
        "open positions",
        "job openings",
        "all jobs",
        "careers at",
        "job results",
        "find a job",
        "job market",
        "hiring alert",
        "job alert",
        "reactions ·",
        "reddit",
    )
    return not any(term in title_l for term in blocked)


def has_expired_deadline(text: str) -> bool:
    today = datetime.now(timezone.utc).date()
    patterns = (
        r"(?:apply by|application deadline|last date to apply|deadline|closing date)\s*[:\-]?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
        r"(?:apply by|application deadline|last date to apply|deadline|closing date)\s*[:\-]?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
        r"(?:apply by|application deadline|last date to apply|deadline|closing date)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text or "", flags=re.I):
            raw = match.group(1).replace(",", "").strip()
            for fmt in ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y", "%Y-%m-%d"):
                try:
                    if datetime.strptime(raw, fmt).date() < today:
                        return True
                    break
                except ValueError:
                    continue
    return False


def has_individual_job_evidence(url: str, title: str, content: str) -> bool:
    if is_blocked_source(url) or is_generic_page(url, title) or not title_looks_like_job(title):
        return False
    if not is_trusted_job_host(url):
        return False
    path = urlparse(url).path.strip("/")
    if len(path.split("/")) < 2 and not re.search(r"/[a-f0-9-]{8,}$", "/" + path, re.I):
        return False
    if has_expired_deadline(content):
        return False
    body = (content or "").lower()
    evidence = (
        "responsibilities",
        "qualifications",
        "requirements",
        "apply for this job",
        "job description",
        "about the role",
        "what you'll do",
        "what you will do",
        "minimum qualifications",
        "preferred qualifications",
        "requisition",
        "employment type",
        "job id",
        "about the job",
    )
    return any(term in body for term in evidence)


def safe_api_error(service: str, exc: requests.RequestException) -> TinyFishError:
    status = exc.response.status_code if exc.response is not None else None
    if status == 401:
        message = "The TinyFish API key was rejected. Check TINYFISH_API_KEY and restart the server."
    elif status == 402:
        message = f"TinyFish {service} allowance is unavailable for this run."
    elif status == 429:
        message = f"TinyFish {service} is rate-limited. Please retry shortly."
    elif status and status >= 500:
        message = f"TinyFish {service} is temporarily unavailable."
    elif isinstance(exc, requests.Timeout):
        message = f"TinyFish {service} timed out."
    else:
        message = f"TinyFish {service} could not complete this request."
    return TinyFishError(service, message, status)


def tinyfish_search(key: str, plan: dict[str, str], location_code: str) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "query": plan["query"],
        "purpose": "Discover current individual job-detail pages for a live job-search product",
        "language": "en",
        "exclude_domains": ",".join(BLOCKED_HOSTS),
    }
    if location_code:
        params["location"] = location_code
    if plan.get("domains"):
        params["include_domains"] = plan["domains"]
    try:
        response = requests.get(SEARCH_URL, params=params, headers={"X-API-Key": key}, timeout=30)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        if isinstance(exc, requests.RequestException):
            raise safe_api_error("Search", exc) from exc
        raise TinyFishError("Search", "TinyFish Search returned an unreadable response.") from exc
    return payload.get("results", []) if isinstance(payload, dict) else []


def tinyfish_fetch(key: str, urls: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        response = requests.post(
            FETCH_URL,
            headers=api_headers(key),
            json={
                "urls": urls[:10],
                "format": "markdown",
                "ttl": 0,
                "per_url_timeout_ms": 45000,
                "purpose": "Verify current job-detail pages and extract role, company, location, and requirements",
            },
            timeout=150,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        if isinstance(exc, requests.RequestException):
            raise safe_api_error("Fetch", exc) from exc
        raise TinyFishError("Fetch", "TinyFish Fetch returned an unreadable response.") from exc
    if not isinstance(payload, dict):
        return [], []
    return payload.get("results", []) or [], payload.get("errors", []) or []


AGENT_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "listings": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "location": {"type": "string"},
                    "description": {"type": "string"},
                    "employment_type": {"type": "string"},
                    "apply_url": {"type": "string"},
                },
                "required": ["title", "company", "location", "description", "employment_type", "apply_url"],
            },
        }
    },
    "required": ["listings"],
}


def tinyfish_agent(key: str, url: str, preferences: dict[str, Any]) -> list[dict[str, Any]]:
    goal = f"""
Inspect this exact job-detail page. Return the opening only if it is currently visible and matches these preferences:
- Role: {preferences['role']}
- Location preference: {preferences.get('location') or 'Anywhere'} ({preferences['locationScope']})
- Skills: {', '.join(preferences.get('skills', [])) or 'No required skills'}
- Opportunity type: {preferences['opportunityType']}
- Experience: {preferences['experienceLevel']}

Never invent a role, company, location, description, status, or URL. Do not return a careers homepage,
search page, category page, social post, or expired opening. apply_url must be the individual vacancy URL.
If this cannot be verified from visible page evidence, return an empty listings array.
"""
    try:
        response = requests.post(
            AGENT_URL,
            headers=api_headers(key),
            json={"url": url, "goal": goal, "browser_profile": "lite", "output_schema": AGENT_OUTPUT_SCHEMA},
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        if isinstance(exc, requests.RequestException):
            raise safe_api_error("Agent", exc) from exc
        raise TinyFishError("Agent", "TinyFish Agent returned an unreadable response.") from exc
    if not isinstance(payload, dict) or payload.get("status") != "COMPLETED":
        return []
    result = payload.get("result") or {}
    return result.get("listings", []) if isinstance(result, dict) else []


def location_code_for(location: str) -> str:
    value = location.lower()
    mapping = {
        "india": "IN",
        "delhi": "IN",
        "noida": "IN",
        "bengaluru": "IN",
        "bangalore": "IN",
        "mumbai": "IN",
        "united states": "US",
        "usa": "US",
        "new york": "US",
        "san francisco": "US",
        "united kingdom": "GB",
        "london": "GB",
        "canada": "CA",
        "germany": "DE",
        "france": "FR",
        "australia": "AU",
        "japan": "JP",
    }
    return next((code for hint, code in mapping.items() if hint in value), "")


def make_search_plans(preferences: dict[str, Any]) -> list[dict[str, str]]:
    role = preferences["role"]
    location = preferences.get("location", "")
    scope = preferences.get("locationScope", "preferred")
    place = "remote" if scope == "remote" else location if scope == "preferred" else ""
    opportunity = preferences.get("opportunityType", "Both")
    type_hint = "internship" if opportunity == "Internship" else "full-time" if opportunity == "Full-time" else "job"
    base_query = clean(f"{role} {place} {type_hint} apply")
    return [
        {"id": "open-web", "label": "Open web", "query": base_query, "domains": ""},
        {"id": "lever", "label": "Lever", "query": base_query, "domains": "jobs.lever.co"},
        {
            "id": "greenhouse",
            "label": "Greenhouse",
            "query": base_query,
            "domains": "boards.greenhouse.io,job-boards.greenhouse.io",
        },
        {"id": "ashby", "label": "Ashby", "query": base_query, "domains": "jobs.ashbyhq.com"},
        {
            "id": "workable-smartrecruiters",
            "label": "Workable + SmartRecruiters",
            "query": base_query,
            "domains": "apply.workable.com,jobs.smartrecruiters.com",
        },
        {
            "id": "enterprise-ats",
            "label": "Workday + iCIMS",
            "query": base_query,
            "domains": "myworkdayjobs.com,workdayjobs.com,careers.icims.com",
        },
    ]


def company_from_path(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    host = source_host(url)
    if not parts:
        return ""
    slug = parts[0]
    if "workdayjobs.com" in host:
        subdomain = host.split(".")[0]
        slug = subdomain if subdomain not in {"www", "wd1", "wd3", "wd5"} else ""
    if not slug or re.fullmatch(r"[a-f0-9-]{12,}", slug, re.I):
        return ""
    slug = re.sub(r"(?<=[A-Za-z])\d+$", "", slug)
    return re.sub(r"[-_]", " ", slug).title()


def split_title_company(raw_title: str, fallback_company: str) -> tuple[str, str]:
    title = clean(re.sub(r"\s*\|\s*LinkedIn\s*$", "", raw_title, flags=re.I))
    patterns = (
        r"^Job Application for (.+?) at (.+)$",
        r"^(.+?)\s+at\s+(.+)$",
        r"^(.+?)\s+[|–—-]\s+Careers?\s+(?:at|@)\s+(.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, title, re.I)
        if match:
            return clean(match.group(1)), clean(match.group(2))
    if fallback_company:
        escaped = re.escape(fallback_company)
        title = re.sub(rf"^{escaped}\s*[-–—|]\s*", "", title, flags=re.I)
        title = re.sub(rf"\s*[|–—-]\s*{escaped}$", "", title, flags=re.I)
    return title, clean(fallback_company)


def extract_location(content: str) -> str:
    flattened = re.sub(r"\r", "", content or "")
    patterns = (
        r"(?:^|\n)\s*(?:Location|Work location|Job location)\s*[:\-]\s*([^\n]{2,100})",
        r"(?:^|\n)\s*(Remote(?:\s*[-—,]\s*[^\n]{2,70})?)\s*(?:\n|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, flattened, re.I)
        if match:
            return clean(re.sub(r"[*#]", "", match.group(1)))[:100]
    return ""


def infer_employment_type(title: str, content: str) -> str:
    text = f"{title} {content[:3000]}".lower()
    if any(term in text for term in ("internship", "intern ", " intern,", "student intern")):
        return "Internship"
    if any(term in text for term in ("contract", "contractor", "fixed term")):
        return "Contract"
    if any(term in text for term in ("part-time", "part time")):
        return "Part-time"
    if any(term in text for term in ("full-time", "full time", "permanent")):
        return "Full-time"
    return "Not specified"


def extract_skills(content: str, requested: list[str]) -> list[str]:
    text = content.lower()
    requested_lower = {skill.lower() for skill in requested}
    ordered = requested + [skill for skill in KNOWN_SKILLS if skill.lower() not in requested_lower]
    return [skill for skill in ordered if skill.lower() in text][:6]


def concise_description(content: str, fallback: str = "") -> str:
    text = content or fallback
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"[#*_>`\[\]]", " ", text)
    text = clean(text)
    for marker in ("about the role", "job description", "the opportunity", "what you'll do"):
        position = text.lower().find(marker)
        if position >= 0:
            text = text[position + len(marker) :].lstrip(" :-")
            break
    if len(text) > 420:
        shortened = text[:420]
        boundary = max(shortened.rfind(". "), shortened.rfind("; "))
        text = shortened[: boundary + 1] if boundary > 180 else shortened.rstrip() + "…"
    return text


def enrich_candidate(candidate: dict[str, Any], page: dict[str, Any], preferences: dict[str, Any]) -> dict[str, Any]:
    content = str(page.get("text") or "")
    page_title = clean(page.get("title"))
    title, company = split_title_company(page_title or candidate["title"], candidate.get("company", ""))
    location = extract_location(content) or candidate.get("location", "")
    if (not location or location == "Location not specified") and preferences.get("locationScope") == "preferred":
        requested_places = [part.strip() for part in preferences.get("location", "").split(",") if part.strip()]
        evidenced_places = [place for place in requested_places if re.search(rf"\b{re.escape(place)}\b", content[:4000], re.I)]
        if evidenced_places:
            location = ", ".join(evidenced_places)
    employment_type = infer_employment_type(title, content)
    return {
        **candidate,
        "title": title,
        "company": company or company_from_path(candidate["apply_url"]) or "Company not identified",
        "location": location or "Location not specified",
        "remote": bool(re.search(r"\bremote\b", f"{location} {content[:2500]}", re.I)),
        "employmentType": employment_type,
        "description": concise_description(content, candidate.get("description", "")),
        "skills": extract_skills(content, preferences.get("skills", [])),
    }


def normalize_identity(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def verification_weight(job: dict[str, Any]) -> int:
    return {"fetch_verified": 3, "agent_verified": 2, "discovered": 1}.get(job.get("verification", ""), 0)


def deduplicate_jobs(jobs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    identity_to_key: dict[str, str] = {}
    for job in jobs:
        url_key = canonical_url(job.get("apply_url"))
        if not url_key:
            continue
        company = normalize_identity(job.get("company", ""))
        title = normalize_identity(job.get("title", ""))
        identity = f"{company}|{title}" if company and "not identified" not in company else ""
        key = identity_to_key.get(identity, url_key) if identity else url_key
        current = unique.get(key)
        if current is None or verification_weight(job) > verification_weight(current) or (
            verification_weight(job) == verification_weight(current)
            and len(job.get("description", "")) > len(current.get("description", ""))
        ):
            unique[key] = job
        if identity:
            identity_to_key[identity] = key
    return list(unique.values())


def preference_match(job: dict[str, Any], preferences: dict[str, Any]) -> bool:
    title = clean(job.get("title")).lower()
    body = clean(f"{job.get('title', '')} {job.get('description', '')} {job.get('location', '')}").lower()
    role_tokens = {token for token in re.findall(r"[a-z0-9+#.]+", preferences["role"].lower()) if len(token) > 2}
    title_tokens = {token for token in re.findall(r"[a-z0-9+#.]+", title) if len(token) > 2}
    if role_tokens and not (preferences["role"].lower() in title or len(role_tokens & title_tokens) >= max(1, len(role_tokens) // 2)):
        return False

    scope = preferences.get("locationScope", "preferred")
    if scope == "remote" and not job.get("remote"):
        return False
    if scope == "preferred" and preferences.get("location"):
        wanted = [part.strip().lower() for part in preferences["location"].split(",") if part.strip()]
        location = job.get("location", "").lower()
        if location != "location not specified" and not job.get("remote") and not any(place in location for place in wanted):
            return False

    opportunity = preferences.get("opportunityType", "Both")
    employment = job.get("employmentType", "").lower()
    if opportunity == "Internship" and "intern" not in f"{title} {employment} {body[:1200]}":
        return False
    if opportunity == "Full-time" and "intern" in f"{title} {employment}":
        return False

    experience = preferences.get("experienceLevel", "Any")
    if experience == "Entry-level" and any(term in title for term in ("senior", "staff", "principal", "lead ")):
        return False
    if experience == "Senior" and not any(term in body for term in ("senior", "staff", "principal", "lead", "5+ years", "7+ years")):
        return False
    return True


def relevance_score(job: dict[str, Any], preferences: dict[str, Any]) -> int:
    title = clean(job.get("title")).lower()
    body = clean(f"{job.get('title', '')} {job.get('description', '')} {job.get('location', '')}").lower()
    role = preferences["role"].lower()
    role_tokens = [token for token in re.findall(r"[a-z0-9+#.]+", role) if len(token) > 2]
    score = 12
    if role in title:
        score += 38
    else:
        score += min(30, sum(10 for token in role_tokens if token in title))
    score += min(20, sum(5 for skill in preferences.get("skills", []) if skill.lower() in body))
    if preferences.get("locationScope") == "remote" and job.get("remote"):
        score += 15
    elif preferences.get("locationScope") == "preferred" and preferences.get("location"):
        if any(place.strip().lower() in job.get("location", "").lower() for place in preferences["location"].split(",")):
            score += 15
    else:
        score += 5
    if job.get("verification") == "fetch_verified":
        score += 10
    elif job.get("verification") == "agent_verified":
        score += 8
    return min(100, score)


def candidate_from_search(item: dict[str, Any], source_id: str) -> dict[str, Any] | None:
    url = normalize_url(item.get("url"))
    raw_title = clean(item.get("title"))
    if not url or not title_looks_like_job(raw_title) or is_generic_page(url, raw_title) or not is_trusted_job_host(url):
        return None
    title, company = split_title_company(raw_title, "")
    return {
        "id": canonical_url(url),
        "title": title,
        "company": company or company_from_path(url) or "Company not identified",
        "location": "Location not specified",
        "remote": "remote" in f"{raw_title} {item.get('snippet', '')}".lower(),
        "employmentType": infer_employment_type(raw_title, clean(item.get("snippet"))),
        "description": concise_description("", clean(item.get("snippet"))),
        "skills": [],
        "apply_url": url,
        "source": source_host(url),
        "discoverySource": source_id,
        "verification": "discovered",
    }


def agent_job(raw: dict[str, Any], target_url: str, preferences: dict[str, Any], source_id: str) -> dict[str, Any] | None:
    url = normalize_url(raw.get("apply_url"))
    title = clean(raw.get("title"))
    if not url or not title_looks_like_job(title) or is_generic_page(url, title) or not is_trusted_job_host(url):
        return None
    if canonical_url(url) != canonical_url(target_url):
        return None
    description = clean(raw.get("description"))
    location = clean(raw.get("location")) or "Location not specified"
    return {
        "id": canonical_url(url),
        "title": title,
        "company": clean(raw.get("company")) or company_from_path(url) or "Company not identified",
        "location": location,
        "remote": "remote" in f"{location} {description}".lower(),
        "employmentType": clean(raw.get("employment_type")) or infer_employment_type(title, description),
        "description": concise_description(description),
        "skills": extract_skills(description, preferences.get("skills", [])),
        "apply_url": url,
        "source": source_host(url),
        "discoverySource": source_id,
        "verification": "agent_verified",
    }


def discover_jobs(preferences: dict[str, Any], progress: ProgressCallback) -> dict[str, Any]:
    key = os.getenv("TINYFISH_API_KEY", "").strip()
    if not key:
        raise TinyFishError("Configuration", "TINYFISH_API_KEY is not configured on the server.")

    context = DiscoveryContext(preferences=preferences, progress=progress)
    plans = make_search_plans(preferences)
    location_code = location_code_for(preferences.get("location", ""))
    raw_results: list[dict[str, Any]] = []

    context.phase("discovering", "active", "Searching live career sources", completed=0, total=len(plans))
    successful_searches = 0
    for index, plan in enumerate(plans, start=1):
        source = SourceState(plan["id"], plan["label"], status="active")
        context.source(source)
        try:
            results = tinyfish_search(key, plan, location_code)
            successful_searches += 1
            for item in results:
                if isinstance(item, dict):
                    raw_results.append({**item, "_source_id": plan["id"]})
            source.status = "complete"
            source.discovered_count = len(results)
        except TinyFishError as exc:
            source.status = "failed"
            source.error = str(exc)
            context.warnings.append(f"{plan['label']}: {exc}")
        context.source(source)
        context.phase(
            "discovering",
            "active",
            f"Searched {plan['label']}",
            completed=index,
            total=len(plans),
        )

    if successful_searches == 0:
        raise TinyFishError("Search", "No TinyFish Search source completed. Please retry in a moment.")
    context.phase(
        "discovering",
        "warning" if context.warnings else "complete",
        "Discovery finished" if not context.warnings else "Discovery finished with source warnings",
        completed=len(plans),
        total=len(plans),
    )

    candidates_by_url: dict[str, dict[str, Any]] = {}
    for item in raw_results:
        candidate = candidate_from_search(item, item.get("_source_id", "open-web"))
        if candidate:
            candidates_by_url.setdefault(canonical_url(candidate["apply_url"]), candidate)
    candidates = list(candidates_by_url.values())[:36]

    validated: list[dict[str, Any]] = []
    fetch_errors: list[dict[str, Any]] = []
    fetched_pages = 0
    if candidates:
        batches = [candidates[offset : offset + 10] for offset in range(0, len(candidates), 10)]
        context.phase("reading", "active", "Reading individual job listings", completed=0, total=len(batches))
        for index, batch in enumerate(batches, start=1):
            try:
                pages, errors = tinyfish_fetch(key, [job["apply_url"] for job in batch])
                fetched_pages += len(pages)
                fetch_errors.extend(errors)
                pages_by_url: dict[str, dict[str, Any]] = {}
                for page in pages:
                    for field_name in ("url", "final_url"):
                        page_url = canonical_url(page.get(field_name))
                        if page_url:
                            pages_by_url[page_url] = page
                for candidate in batch:
                    page = pages_by_url.get(canonical_url(candidate["apply_url"]))
                    if not page:
                        continue
                    enriched = enrich_candidate(candidate, page, preferences)
                    content = str(page.get("text") or "")
                    if has_individual_job_evidence(enriched["apply_url"], enriched["title"], content):
                        enriched["verification"] = "fetch_verified"
                        validated.append(enriched)
            except TinyFishError as exc:
                context.warnings.append(str(exc))
            context.phase(
                "reading",
                "active",
                f"Read listing batch {index} of {len(batches)}",
                completed=index,
                total=len(batches),
            )
        if fetch_errors:
            context.warnings.append(f"{len(fetch_errors)} listing page(s) could not be read; other results were preserved.")
        context.phase(
            "reading",
            "warning" if fetch_errors else "complete",
            "Listing review finished" if not fetch_errors else "Listing review finished with some unreadable pages",
            completed=len(batches),
            total=len(batches),
        )
    else:
        context.phase("reading", "skipped", "No individual pages were available to read")

    validated_urls = {canonical_url(job["apply_url"]) for job in validated}
    if preferences.get("useAgent"):
        target = next((job for job in candidates if canonical_url(job["apply_url"]) not in validated_urls), None)
        if target:
            context.phase("agent", "active", "Agent is checking one difficult listing")
            try:
                agent_results = tinyfish_agent(key, target["apply_url"], preferences)
                for raw in agent_results:
                    if isinstance(raw, dict):
                        parsed = agent_job(raw, target["apply_url"], preferences, target["discoverySource"])
                        if parsed:
                            validated.append(parsed)
                context.phase("agent", "complete", "Agent check finished")
            except TinyFishError as exc:
                context.warnings.append(str(exc))
                context.phase("agent", "warning", "Agent was unavailable; Search and Fetch results were kept")
        else:
            context.phase("agent", "skipped", "Agent was not needed for this search")
    else:
        context.phase("agent", "skipped", "Agent fallback was not requested")

    context.phase("deduplicating", "active", "Removing duplicate openings")
    discovered = [job for job in candidates if canonical_url(job["apply_url"]) not in validated_urls]
    unique = deduplicate_jobs([*validated, *discovered])
    context.phase("deduplicating", "complete", f"Reduced the feed to {len(unique)} unique openings")

    context.phase("matching", "active", "Matching roles to your preferences")
    eligible: list[dict[str, Any]] = []
    for job in unique:
        if not preference_match(job, preferences):
            continue
        job["score"] = relevance_score(job, preferences)
        job["id"] = canonical_url(job["apply_url"])
        eligible.append(job)
    eligible.sort(key=lambda job: (job["score"], verification_weight(job)), reverse=True)
    eligible = eligible[: int(preferences.get("maxResults", 16))]
    context.phase("matching", "complete", f"Ranked {len(eligible)} relevant openings")

    for source in context.sources.values():
        source.verified_count = sum(
            1
            for job in eligible
            if job.get("discoverySource") == source.id and job.get("verification") != "discovered"
        )
        if source.status == "complete" and source.discovered_count == 0:
            source.status = "empty"
        context.source(source)

    verified_count = sum(1 for job in eligible if job.get("verification") != "discovered")
    return {
        "jobs": eligible,
        "sources": [source.as_dict() for source in context.sources.values()],
        "warnings": list(dict.fromkeys(context.warnings)),
        "summary": {
            "uniqueResults": len(eligible),
            "verifiedResults": verified_count,
            "searchResultsScreened": len(raw_results),
            "pagesInspected": fetched_pages,
            "successfulSources": successful_searches,
            "failedSources": len(plans) - successful_searches,
        },
        "searchedAt": datetime.now(timezone.utc).isoformat(),
    }
