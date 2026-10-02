"""LLM-driven extraction of a job description into structured requirements."""

from __future__ import annotations

from dataclasses import dataclass

from .llm import generate_json

SYSTEM_PROMPT = """You are a precise job-description analyst. You extract the explicit \
requirements, responsibilities, and expectations stated in a job description. You do not \
add requirements that are not stated or implied by the text. Output valid JSON only, no \
commentary, no markdown fences.
"""

SCHEMA_DESCRIPTION = """Return a single JSON object with this exact shape:
{
  "company": string|null,
  "role_title": string|null,
  "seniority": string|null,
  "domain": string|null,
  "must_have": [
    {"requirement": string, "category": "skill"|"experience"|"qualification"|"tool"|"domain"|"behavioral"|"leadership"}
  ],
  "nice_to_have": [
    {"requirement": string, "category": "skill"|"experience"|"qualification"|"tool"|"domain"|"behavioral"|"leadership"}
  ],
  "responsibilities": [string],
  "business_problems": [string],
  "keywords": [string]
}

"must_have" = requirements stated as required/mandatory ("must have", "required",
"X+ years of", listed under a "Requirements" heading). "nice_to_have" = requirements
described as a plus/preferred/bonus. If the JD doesn't clearly distinguish, use
reasonable judgment based on phrasing (e.g. "requirements" section = must_have,
"nice to have"/"bonus"/"preferred" section = nice_to_have), but do not invent
requirements that aren't stated.
"""


@dataclass
class ParsedJD:
    raw_text: str
    company: str | None
    role_title: str | None
    seniority: str | None
    domain: str | None
    must_have: list[dict]
    nice_to_have: list[dict]
    responsibilities: list[str]
    business_problems: list[str]
    keywords: list[str]


def parse_jd(raw_text: str) -> ParsedJD:
    user_prompt = f"{SCHEMA_DESCRIPTION}\n\nJob description text:\n---\n{raw_text}\n---"
    data = generate_json(SYSTEM_PROMPT, user_prompt, retries=1)
    return ParsedJD(
        raw_text=raw_text,
        company=data.get("company"),
        role_title=data.get("role_title"),
        seniority=data.get("seniority"),
        domain=data.get("domain"),
        must_have=data.get("must_have", []) or [],
        nice_to_have=data.get("nice_to_have", []) or [],
        responsibilities=data.get("responsibilities", []) or [],
        business_problems=data.get("business_problems", []) or [],
        keywords=data.get("keywords", []) or [],
    )
