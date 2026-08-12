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
    <td class="value">{% if case.report_date %}{{ case.report_date }}{% else %}N/A{% endif %}</td>
    <td class="label">Primary Subject:</td>
    <td class="value"><strong>{% if case.primary_target_name %}{{ case.primary_target_name }}{% else %}N/A{% endif %}</strong></td>
  </tr>
  <tr>
    <td class="label">Client Name:</td>
    <td class="value">{{ client.name }}</td>
    <td class="label">Known Aliases:</td>
    <td class="value">{{ case.target_aliases or "None Identified" }}</td>
  </tr>
  <tr>
    <td class="label">Lead Investigator:</td>
    <td class="value">{% if case.investigator_name %}{{ case.investigator_name }}{% else %}N/A{% endif %}</td>
    <td class="label">Investigation Window:</td>
    <td class="value">{% if case.start_date %}{{ case.start_date }}{% else %}N/A{% endif %} – {% if case.end_date %}{{ case.end_date }}{% else %}N/A{% endif %}</td>
  </tr>
</table>

---

## 1. Executive Intelligence Overview

<div class="risk-summary-box {{ case.overall_risk_level | lower | replace(' ', '-') }}">
  <strong>Subject Risk Assessment:</strong> {% if case.overall_risk_classification %}{{ case.overall_risk_classification }}{% else %}N/A{% endif %}
</div>

### 1.1 Subject Identity Summary
<table class="edd-keyvalue-table">
  <tr>
    <td class="kv-label">Full Legal Name:</td>
    <td class="kv-value">{% if case.primary_target_name %}{{ case.primary_target_name }}{% else %}N/A{% endif %}</td>
  </tr>
  <tr>
    <td class="kv-label">Date / Place of Birth:</td>
    <td class="kv-value">{% if case.target_dob_nationality %}{{ case.target_dob_nationality }}{% else %}N/A{% endif %}</td>
  </tr>
  <tr>
    <td class="kv-label">Primary Residency / Location:</td>
    <td class="kv-value">{{ case.target_residency or "Verified UK Resident" }}</td>
  </tr>
  <tr>
    <td class="kv-label">Primary Occupation / Known Roles:</td>
    <td class="kv-value">{% if case.target_appointed_roles %}{{ case.target_appointed_roles }}{% else %}N/A{% endif %}</td>
  </tr>
</table>

<div class="executive-assessment-block">
  <strong>Investigator Assessment:</strong> {{ firm.executive_summary }}
</div>

---

<div style="page-break-before: always;"></div>

## 2. Digital Identity & Social Media Mapping

{% if case.digital_identity_details_md %}{{ case.digital_identity_details_md | safe }}{% endif %}

---

## 3. Directorships, Business Interests & Wealth Tracing

{% if case.business_interests_md %}{{ case.business_interests_md | safe }}{% endif %}

---

## 4. Legal, Regulatory & Adverse Findings

{% if case.legal_findings_md %}{{ case.legal_findings_md | safe }}{% endif %}

---

<div style="page-break-before: always;"></div>

## 5. Methodology & Legal Compliance

1. **Lawful Basis:** Data was processed under **Legitimate Interest** (Art. 6(1)(f) UK GDPR) for fraud detection, background verification, or asset protection.
2. **Chain of Custody:** Web page captures and social media snapshots are archived with cryptographic hashing.

<div class="hash-box">
  <code>SHA-256 Case Archive Hash: {{ case.sha256_hash or "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991678526855" }}</code>
</div>