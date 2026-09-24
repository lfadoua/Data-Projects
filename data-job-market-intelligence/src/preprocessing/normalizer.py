"""Explicit normalization rules. Unknown information remains null."""

import re

ROLE_PATTERNS = [
    ("MLOps Engineer", r"mlops|ml ops"),
    ("Machine Learning Engineer", r"machine learning|\bml engineer"),
    ("Analytics Engineer", r"analytics engineer"),
    ("Data Engineer", r"data engineer|etl developer|big data engineer"),
    ("Data Scientist", r"data scien"),
    ("Data Architect", r"data architect"),
    ("BI Analyst", r"business intelligence|\bbi (?:analyst|developer)|power bi"),
    ("Data Analyst", r"data analy|analytics analyst"),
    ("AI Engineer", r"\bai engineer|artificial intelligence"),
]
COUNTRIES = {
    "us": "United States",
    "usa": "United States",
    "united states": "United States",
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
    "canada": "Canada",
    "france": "France",
    "germany": "Germany",
    "india": "India",
    "australia": "Australia",
}
US_STATES = set(
    (
        "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI"
        " MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX "
        "UT VT VA WA WV WI WY DC"
    ).split()
)


def normalize_title(title: str) -> str:
    for canonical, pattern in ROLE_PATTERNS:
        if re.search(pattern, title, re.I):
            return canonical
    return "Other / Unclassified"


def normalize_seniority(title: str, level: str = "") -> str:
    for label, pattern in [
        ("Intern", r"\bintern(?:ship)?\b"),
        ("Executive", r"\b(?:director|head|vp|chief)\b"),
        ("Lead", r"\b(?:lead|principal|staff|manager)\b"),
        ("Senior", r"\b(?:senior|sr\.?)\b"),
        ("Junior", r"\b(?:junior|jr\.?|entry|graduate)\b"),
    ]:
        if re.search(pattern, title, re.I):
            return label
    if "mid" in level.lower() and "senior" in level.lower():
        return "Mid/Senior (source)"
    for label in ("Senior", "Junior", "Intern", "Lead"):
        if label.lower() in level.lower():
            return label
    return "Unspecified"


def normalize_location(location: str, explicit_country: str = "", explicit_city: str = ""):
    parts = [p.strip() for p in location.split(",") if p.strip()]
    country = COUNTRIES.get(explicit_country.lower(), explicit_country.strip() or None)
    if not country and parts:
        country = COUNTRIES.get(parts[-1].lower())
        if not country and parts[-1] in US_STATES:
            country = "United States"
    city = explicit_city.strip() or None
    if not city and len(parts) > 1 and parts[0].lower() not in COUNTRIES:
        city = parts[0]
    return country, city


def normalize_workplace(value: str) -> str:
    value = value.lower()
    if "hybrid" in value:
        return "Hybrid"
    if "remote" in value:
        return "Remote"
    if "onsite" in value or "on-site" in value or "on site" in value:
        return "Onsite"
    return "Unspecified"


def normalize_employment(value: str) -> str | None:
    for label, pattern in [
        ("Full-time", r"full[ -]?time"),
        ("Part-time", r"part[ -]?time"),
        ("Contract", r"contract|freelance"),
        ("Internship", r"intern"),
    ]:
        if re.search(pattern, value, re.I):
            return label
    return None


def salary_number(value: str) -> float | None:
    value = str(value or "").strip().replace(",", "")
    if not value:
        return None
    match = re.fullmatch(r"(?:USD|EUR|GBP|CAD|[$€£])?\s*(\d+(?:\.\d+)?)\s*([kK])?", value)
    if not match:
        return None
    amount = float(match[1]) * (1000 if match[2] else 1)
    return amount if amount > 0 else None
