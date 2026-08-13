from __future__ import annotations

import json

SUBJECT_RELATIONSHIP_OPTIONS = [
    "Principal Subject",
    "Linked Subject",
    "Associate / Contact",
    "Family Member",
    "Employee / Contractor",
    "Director / Officer",
    "Beneficial Owner",
    "Domain / Asset Owner",
    "Witness / Source",
    "Unknown / Unconfirmed",
]

SUBJECT_TYPE_SCHEMAS = {
    "Person": {
        "primary_fields": ["full_name"],
        "fields": [
            {"key": "full_name", "label": "Full Name", "kind": "text", "placeholder": "e.g., Jane Alexandra Doe"},
            {"key": "aliases", "label": "Aliases / Known As", "kind": "text", "placeholder": "Comma-separated aliases"},
            {"key": "date_of_birth", "label": "Date of Birth", "kind": "text", "placeholder": "YYYY-MM-DD or approximate"},
            {"key": "nationality", "label": "Nationality", "kind": "text", "placeholder": "e.g., British"},
            {"key": "current_location", "label": "Current / Last Known Location", "kind": "text", "placeholder": "City, region, country"},
            {"key": "occupation", "label": "Occupation / Role", "kind": "text", "placeholder": "e.g., Director, consultant"},
            {"key": "identifiers", "label": "Identifiers / Notes", "kind": "textarea", "placeholder": "Passport, social handles, company links, etc."},
        ],
    },
    "Organization": {
        "primary_fields": ["legal_name"],
        "fields": [
            {"key": "legal_name", "label": "Legal Name", "kind": "text", "placeholder": "Registered company or entity name"},
            {"key": "trading_names", "label": "Trading Names / Aliases", "kind": "text", "placeholder": "Comma-separated trading names"},
            {"key": "registration_number", "label": "Registration Number", "kind": "text", "placeholder": "Company / charity / entity registration number"},
            {"key": "jurisdiction", "label": "Jurisdiction", "kind": "text", "placeholder": "Country or registry jurisdiction"},
            {"key": "website", "label": "Website", "kind": "text", "placeholder": "Primary website or portal"},
            {"key": "head_office", "label": "Head Office / Address", "kind": "text", "placeholder": "Primary address or city"},
            {"key": "identifiers", "label": "Identifiers / Notes", "kind": "textarea", "placeholder": "Parent companies, directors, tax ids, etc."},
        ],
    },
    "Domain / Website": {
        "primary_fields": ["domain_name"],
        "fields": [
            {"key": "domain_name", "label": "Domain Name", "kind": "text", "placeholder": "e.g., example.com"},
            {"key": "related_urls", "label": "Related URLs", "kind": "text", "placeholder": "Comma-separated URLs"},
            {"key": "registrar", "label": "Registrar", "kind": "text", "placeholder": "e.g., Namecheap"},
            {"key": "registration_date", "label": "Registration Date", "kind": "text", "placeholder": "YYYY-MM-DD"},
            {"key": "hosting_provider", "label": "Hosting Provider", "kind": "text", "placeholder": "e.g., Cloudflare"},
            {"key": "ip_addresses", "label": "Associated IP Addresses", "kind": "text", "placeholder": "Comma-separated IPs"},
            {"key": "notes", "label": "Notes", "kind": "textarea", "placeholder": "DNS, NS, SSL, WHOIS notes, etc."},
        ],
    },
    "Email Address": {
        "primary_fields": ["email_address"],
        "fields": [
            {"key": "email_address", "label": "Email Address", "kind": "text", "placeholder": "name@example.com"},
            {"key": "display_name", "label": "Display Name", "kind": "text", "placeholder": "Name or alias on the mailbox"},
            {"key": "associated_usernames", "label": "Associated Usernames / Handles", "kind": "text", "placeholder": "Comma-separated usernames"},
            {"key": "associated_domains", "label": "Associated Domains", "kind": "text", "placeholder": "Comma-separated domains"},
            {"key": "notes", "label": "Notes", "kind": "textarea", "placeholder": "Compromise context, provider, metadata, etc."},
        ],
    },
    "Username / Handle": {
        "primary_fields": ["handle"],
        "fields": [
            {"key": "handle", "label": "Handle / Username", "kind": "text", "placeholder": "@handle or username"},
            {"key": "platform", "label": "Platform", "kind": "text", "placeholder": "e.g., X, LinkedIn, Telegram"},
            {"key": "profile_url", "label": "Profile URL", "kind": "text", "placeholder": "https://..."},
            {"key": "associated_emails", "label": "Associated Emails", "kind": "text", "placeholder": "Comma-separated emails"},
            {"key": "notes", "label": "Notes", "kind": "textarea", "placeholder": "Activity, aliases, linked accounts, etc."},
        ],
    },
    "Phone Number": {
        "primary_fields": ["phone_number"],
        "fields": [
            {"key": "phone_number", "label": "Phone Number", "kind": "text", "placeholder": "+44 ..."},
            {"key": "country", "label": "Country", "kind": "text", "placeholder": "Country / dialling region"},
            {"key": "carrier", "label": "Carrier / Network", "kind": "text", "placeholder": "Mobile network or provider"},
            {"key": "associated_accounts", "label": "Associated Accounts / Handles", "kind": "text", "placeholder": "Comma-separated accounts"},
            {"key": "notes", "label": "Notes", "kind": "textarea", "placeholder": "Lookup results, VoIP, messaging apps, etc."},
        ],
    },
    "IP Address / Host": {
        "primary_fields": ["ip_address"],
        "fields": [
            {"key": "ip_address", "label": "IP Address", "kind": "text", "placeholder": "e.g., 203.0.113.10"},
            {"key": "hostnames", "label": "Hostnames", "kind": "text", "placeholder": "Comma-separated hostnames"},
            {"key": "asn", "label": "ASN", "kind": "text", "placeholder": "e.g., AS13335"},
            {"key": "geolocation", "label": "Geolocation", "kind": "text", "placeholder": "City, region, country"},
            {"key": "notes", "label": "Notes", "kind": "textarea", "placeholder": "Services, ports, ownership, threat context, etc."},
        ],
    },
    "Physical Address": {
        "primary_fields": ["address_line"],
        "fields": [
            {"key": "address_line", "label": "Address Line", "kind": "text", "placeholder": "Street address"},
            {"key": "city", "label": "City / Town", "kind": "text", "placeholder": "City"},
            {"key": "region", "label": "Region / State", "kind": "text", "placeholder": "Region / state / county"},
            {"key": "country", "label": "Country", "kind": "text", "placeholder": "Country"},
            {"key": "coordinates", "label": "Coordinates", "kind": "text", "placeholder": "Lat, long"},
            {"key": "notes", "label": "Notes", "kind": "textarea", "placeholder": "Occupancy, site observations, etc."},
        ],
    },
    "Vehicle": {
        "primary_fields": ["registration_plate"],
        "fields": [
            {"key": "registration_plate", "label": "Registration Plate", "kind": "text", "placeholder": "Vehicle registration"},
            {"key": "make", "label": "Make", "kind": "text", "placeholder": "Manufacturer"},
            {"key": "model", "label": "Model", "kind": "text", "placeholder": "Model name"},
            {"key": "colour", "label": "Colour", "kind": "text", "placeholder": "Primary colour"},
            {"key": "year", "label": "Year", "kind": "text", "placeholder": "Model year"},
            {"key": "vin", "label": "VIN / Chassis Number", "kind": "text", "placeholder": "Vehicle identification number"},
            {"key": "owner_keeper", "label": "Owner / Keeper", "kind": "text", "placeholder": "Registered owner or keeper"},
            {"key": "location", "label": "Known Location / Activity", "kind": "text", "placeholder": "Last seen location or area"},
            {"key": "notes", "label": "Notes", "kind": "textarea", "placeholder": "Insurance, sightings, plates, etc."},
        ],
    },
    "Other Subject": {
        "primary_fields": ["display_name"],
        "fields": [
            {"key": "display_name", "label": "Display Name", "kind": "text", "placeholder": "Subject label"},
            {"key": "description", "label": "Description", "kind": "textarea", "placeholder": "Describe the subject and why it matters"},
            {"key": "identifiers", "label": "Identifiers / Notes", "kind": "textarea", "placeholder": "Any other relevant details"},
        ],
    },
}


def get_subject_type_choices() -> list[str]:
    return list(SUBJECT_TYPE_SCHEMAS.keys())


def get_subject_schema(subject_type: str) -> dict:
    return SUBJECT_TYPE_SCHEMAS.get(subject_type, SUBJECT_TYPE_SCHEMAS["Other Subject"])


def blank_subject_data(subject_type: str) -> dict[str, str]:
    return {field["key"]: "" for field in get_subject_schema(subject_type)["fields"]}


def normalize_subject_data(subject_type: str, data: dict | None) -> dict[str, str]:
    schema = get_subject_schema(subject_type)
    normalized = blank_subject_data(subject_type)
    if not data:
        return normalized
    for field in schema["fields"]:
        value = data.get(field["key"], "")
        normalized[field["key"]] = "" if value is None else str(value)
    return normalized


def decode_subject_data(subject_type: str, payload: str | dict | None) -> dict[str, str]:
    if isinstance(payload, dict):
        return normalize_subject_data(subject_type, payload)
    if not payload:
        return blank_subject_data(subject_type)
    try:
        data = json.loads(payload)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return normalize_subject_data(subject_type, data)


def encode_subject_data(subject_type: str, data: dict | None) -> str:
    return json.dumps(normalize_subject_data(subject_type, data))


def subject_display_name(subject_type: str, data: dict | None, fallback: str = "") -> str:
    normalized = normalize_subject_data(subject_type, data)
    schema = get_subject_schema(subject_type)
    for key in schema.get("primary_fields", []):
        value = normalized.get(key, "").strip()
        if value:
            return value
    return fallback or subject_type


def subject_summary_lines(subject_type: str, data: dict | None) -> list[tuple[str, str]]:
    normalized = normalize_subject_data(subject_type, data)
    lines: list[tuple[str, str]] = []
    for field in get_subject_schema(subject_type)["fields"]:
        value = normalized.get(field["key"], "").strip()
        if value:
            lines.append((field["label"], value))
    return lines
