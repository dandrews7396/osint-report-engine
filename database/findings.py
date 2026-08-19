from __future__ import annotations

import json

DOMAIN_CATEGORIES = [
    "Identity & PII",
    "Corporate Governance & Ownership",
    "Infrastructure & Network Assets",
    "Social Media & Digital Footprint",
    "Financial & Asset Tracing",
    "Leaked Data",
    "Geopolitical & Physical Security",
    "Custom Category",
]

FINDING_CATEGORY_SCHEMAS = {
    "Identity & PII": {
        "fields": [
            {
                "key": "data_types_exposed",
                "label": "Data Type(s) Exposed",
                "kind": "textarea",
                "placeholder": "e.g., Full Name, Date of Birth, National ID/Passport Number, Biometric Data, Home Address",
            },
            {
                "key": "sensitivity_classification",
                "label": "Sensitivity Classification",
                "kind": "select",
                "options": ["Standard", "Special Category (GDPR Art. 9)"],
            },
            {
                "key": "source_of_exposure",
                "label": "Source of Exposure",
                "kind": "select",
                "options": ["Public Record", "Data Broker", "Social Media", "Breach Dataset", "Other"],
            },
            {
                "key": "date_first_observed",
                "label": "Date First Observed",
                "kind": "date",
                "max_date": "today",
            },
        ],
    },
    "Corporate Governance & Ownership": {
        "fields": [
            {"key": "entity_name", "label": "Entity Name", "kind": "text", "placeholder": "Registered company or entity name"},
            {
                "key": "registration_number_jurisdiction",
                "label": "Registration Number & Jurisdiction",
                "kind": "text",
                "placeholder": "e.g., 12345678 (England & Wales)",
            },
            {
                "key": "subjects_role",
                "label": "Subject's Role",
                "kind": "select",
                "options": ["Director", "Beneficial Owner", "Officer", "Shareholder", "Other"],
            },
            {"key": "ownership_percentage", "label": "Ownership Percentage", "kind": "text", "placeholder": "e.g., 25%"},
            {"key": "registry_source", "label": "Registry Source", "kind": "text", "placeholder": "e.g., Companies House, OpenCorporates"},
        ],
    },
    "Infrastructure & Network Assets": {
        "fields": [
            {
                "key": "asset_type",
                "label": "Asset Type",
                "kind": "select",
                "options": ["Domain", "IP Address", "Subdomain", "Cloud Storage", "Exposed Service"],
            },
            {"key": "asset_identifier", "label": "Asset Identifier", "kind": "text", "placeholder": "e.g., example.com or 203.0.113.10"},
            {"key": "hosting_provider_asn", "label": "Hosting Provider / ASN", "kind": "text", "placeholder": "e.g., Cloudflare / AS13335"},
            {"key": "registration_provider", "label": "Registration Provider", "kind": "text", "placeholder": "e.g., GoDaddy, Namecheap"},
            {"key": "dns_information", "label": "DNS Information", "kind": "textarea", "placeholder": "Nameservers, MX records, etc."},
            {"key": "website_technologies", "label": "Website Technologies", "kind": "text", "placeholder": "e.g., WordPress, nginx, Cloudflare"},
            {
                "key": "webpage_content_hash",
                "label": "Webpage Content Hash (SHA-256)",
                "kind": "text",
                "placeholder": "Hash of the captured page content",
            },
            {
                "key": "date_first_observed",
                "label": "First Observed Date",
                "kind": "date",
                "max_date": "today",
            },
        ],
    },
    "Social Media & Digital Footprint": {
        "fields": [
            {"key": "platform", "label": "Platform", "kind": "text", "placeholder": "e.g., X, LinkedIn, Telegram"},
            {"key": "username", "label": "Username", "kind": "text", "placeholder": "@handle or username"},
            {"key": "display_name", "label": "Display Name", "kind": "text", "placeholder": "Name shown on the profile"},
            {"key": "capture_date", "label": "Capture Date", "kind": "date"},
            {"key": "archive_method", "label": "Archive Method", "kind": "text", "placeholder": "e.g., Wayback Machine, manual screenshot"},
        ],
    },
    "Financial & Asset Tracing": {
        "fields": [
            {
                "key": "asset_type",
                "label": "Asset Type",
                "kind": "select",
                "options": ["Bank Account", "Property", "Vehicle", "Cryptocurrency Wallet", "Company Shares"],
            },
            {
                "key": "identifier",
                "label": "Identifier",
                "kind": "text",
                "placeholder": "e.g., partial account/IBAN, wallet address, property title number",
            },
            {
                "key": "transaction_date_period",
                "label": "Transaction Date / Period",
                "kind": "text",
                "placeholder": "e.g., Jan 2023 - Mar 2023",
            },
            {"key": "jurisdiction", "label": "Jurisdiction", "kind": "text", "placeholder": "Country or region"},
        ],
    },
    "Leaked Data": {
        "fields": [
            {
                "key": "breach_source_name",
                "label": "Breach / Source Name",
                "kind": "text",
                "placeholder": "Name of the original breach or compromised organization",
            },
            {"key": "breach_date", "label": "Breach Date", "kind": "date"},
            {
                "key": "data_types_exposed",
                "label": "Data Types Exposed",
                "kind": "textarea",
                "placeholder": "e.g., Credentials, Financial Data, PII, Documents",
            },
            {
                "key": "record_count",
                "label": "Record Count",
                "kind": "text",
                "placeholder": "Approximate number of records associated with the subject",
            },
        ],
    },
    "Geopolitical & Physical Security": {
        "fields": [
            {"key": "location_coordinates", "label": "Location / Coordinates", "kind": "text", "placeholder": "City, region, country, or lat/long"},
            {
                "key": "threat_type",
                "label": "Threat Type",
                "kind": "select",
                "options": ["Civil Unrest", "Sanctions Exposure", "Travel Risk", "Physical Surveillance", "Other"],
            },
            {
                "key": "sanctions_watchlist_reference",
                "label": "Sanctions/Watchlist Reference",
                "kind": "text",
                "placeholder": "e.g., OFAC SDN List, Entry #12345",
            },
            {"key": "date_of_observation", "label": "Date of Observation", "kind": "date"},
        ],
    },
    "Custom Category": {
        "fields": [],
    },
}


def get_domain_category_choices() -> list[str]:
    return list(DOMAIN_CATEGORIES)


def get_finding_schema(domain_category: str) -> dict:
    return FINDING_CATEGORY_SCHEMAS.get(domain_category, FINDING_CATEGORY_SCHEMAS["Custom Category"])


def blank_finding_data(domain_category: str) -> dict[str, str]:
    return {field["key"]: "" for field in get_finding_schema(domain_category)["fields"]}


def normalize_finding_data(domain_category: str, data: dict | None) -> dict[str, str]:
    schema = get_finding_schema(domain_category)
    normalized = blank_finding_data(domain_category)
    if not data:
        return normalized
    for field in schema["fields"]:
        value = data.get(field["key"], "")
        normalized[field["key"]] = "" if value is None else str(value)
    return normalized


def decode_finding_data(domain_category: str, payload: str | dict | None) -> dict[str, str]:
    if isinstance(payload, dict):
        return normalize_finding_data(domain_category, payload)
    if not payload:
        return blank_finding_data(domain_category)
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("Finding category data must be a JSON object.")
    return normalize_finding_data(domain_category, data)


def encode_finding_data(domain_category: str, data: dict | None) -> str:
    return json.dumps(normalize_finding_data(domain_category, data))


def finding_summary_lines(domain_category: str, data: str | dict | None) -> list[tuple[str, str]]:
    normalized = decode_finding_data(domain_category, data)
    lines: list[tuple[str, str]] = []
    for field in get_finding_schema(domain_category)["fields"]:
        value = normalized.get(field["key"], "").strip()
        if not value:
            continue
        lines.append((field["label"], value))
    return lines
