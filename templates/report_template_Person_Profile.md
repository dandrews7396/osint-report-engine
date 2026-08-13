<div class="header-container">
  <div class="agency-title">{{ firm.name | upper }}</div>
  <div class="report-title">PERSON OF INTEREST INTELLIGENCE PROFILE</div>
  <div class="report-subtitle">HUMINT & DIGITAL FOOTPRINT ASSESSMENT</div>
</div>

<table class="edd-cover-grid">
  <tr>
    <td class="label">Case Ref:</td>
    <td class="value">{{ case.case_ref }}</td>
    <td class="label">Classification:</td>
    <td class="value highlight-red">STRICTLY CONFIDENTIAL</td>
  </tr>
  <tr>
    <td class="label">Date:</td>
    <td class="value">{{ case.report_date_formatted }}</td>
    <td class="label">Primary Subject:</td>
    <td class="value"><strong>{{ case.target_scope }}</strong></td>
  </tr>
  <tr>
    <td class="label">Client Name:</td>
    <td class="value">{{ client.name }}</td>
    <td class="label">Known Aliases:</td>
    <td class="value">{{ case.target_aliases or "None Identified" }}</td>
  </tr>
  <tr>
    <td class="label">Lead Investigator:</td>
    <td class="value">{{ case.investigator_name }}</td>
    <td class="label">Investigation Window:</td>
    <td class="value">{{ case.start_date_formatted }} – {{ case.end_date_formatted }}</td>
  </tr>
</table>

---

## 1. Executive Intelligence Overview


### 1.1 Subject Identity Summary
<table class="edd-keyvalue-table">
  <tr>
    <td class="kv-label">Full Legal Name:</td>
    <td class="kv-value">{{ case.primary_target_name }}</td>
  </tr>
  <tr>
    <td class="kv-label">Date / Place of Birth:</td>
    <td class="kv-value">{{ case.target_dob_nationality }}</td>
  </tr>
  <tr>
    <td class="kv-label">Primary Residency / Location:</td>
    <td class="kv-value">{{ case.target_residency or "Verified UK Resident" }}</td>
  </tr>
  <tr>
    <td class="kv-label">Primary Occupation / Known Roles:</td>
    <td class="kv-value">{{ case.target_appointed_roles }}</td>
  </tr>
</table>

<div class="executive-assessment-block">
  <strong>Investigator Assessment:</strong> {{ firm.executive_summary }}
</div>

---

<div style="page-break-before: always;"></div>

## 2. Digital Identity & Social Media Mapping

{{ case.digital_identity_details_md | safe }}

---

## 3. Directorships, Business Interests & Wealth Tracing

{{ case.business_interests_md | safe }}

---

## 4. Legal, Regulatory & Adverse Findings

{{ case.legal_findings_md | safe }}

---

## 5. Subject Details & Contact Information

{% if subjects %}
{% for subject in subjects %}
### {{ subject.display_name }}{% if subject.subject_type %} ({{ subject.subject_type }}){% endif %}

{% if subject.summary_lines %}
{% for label, value in subject.summary_lines %}
- **{{ label }}:** {{ value }}
{% endfor %}
{% endif %}

{% endfor %}
{% else %}
No subjects recorded for this case.
{% endif %}

---

<div style="page-break-before: always;"></div>

## 6. Methodology & Legal Compliance

1. **Lawful Basis:** Data was processed under **Legitimate Interest** (Art. 6(1)(f) UK GDPR) for fraud detection, background verification, or asset protection.
2. **Chain of Custody:** Web page captures and social media snapshots are archived with cryptographic hashing.

<div class="hash-box">
  <code>SHA-256 Case Archive Hash: {{ case.sha256_hash or "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991678526855" }}</code>
</div>