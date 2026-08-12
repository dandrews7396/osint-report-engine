<div class="header-container">
  <div class="agency-title">{{ firm.name | upper }}</div>
  <div class="report-title">EXTERNAL THREAT SURFACE ASSESSMENT</div>
  <div class="report-subtitle">INFRASTRUCTURE & DIGITAL FOOTPRINT ANALYSIS</div>
</div>

<table class="edd-cover-grid">
  <tr>
    <td class="label">Case Ref:</td>
    <td class="value">{{ case.case_ref }}</td>
    <td class="label">Classification:</td>
    <td class="value highlight-red">RESTRICTED - TECHNICAL</td>
  </tr>
  <tr>
    <td class="label">Date:</td>
    <td class="value">{% if case.report_date %}{{ case.report_date }}{% else %}N/A{% endif %}</td>
    <td class="label">Target Scope:</td>
    <td class="value"><strong>{% if case.target_scope %}{{ case.target_scope }}{% else %}N/A{% endif %}</strong></td>
  </tr>
  <tr>
    <td class="label">Client Name:</td>
    <td class="value">{{ client.name }}</td>
    <td class="label">Assessment Type:</td>
    <td class="value">{{ case.case_type }}</td>
  </tr>
  <tr>
    <td class="label">Lead Analyst:</td>
    <td class="value">{% if case.investigator_name %}{{ case.investigator_name }}{% else %}N/A{% endif %}</td>
    <td class="label">Scanning Window:</td>
    <td class="value">{% if case.start_date %}{{ case.start_date }}{% else %}N/A{% endif %} – {% if case.end_date %}{{ case.end_date }}{% else %}N/A{% endif %}</td>
  </tr>
</table>

---

## 1. Technical Threat Overview

<div class="risk-summary-box {{ case.overall_risk_level | lower | replace(' ', '-') }}">
  <strong>External Exposure Profile:</strong> {% if case.overall_risk_classification %}{{ case.overall_risk_classification }}{% else %}N/A{% endif %}
</div>

### 1.1 Exposure Summary Matrix
{% if case.findings_matrix_table %}{{ case.findings_matrix_table | safe }}{% else %}{{ findings_table | safe }}{% endif %}

<div class="executive-assessment-block">
  <strong>Technical Assessment:</strong> {{ firm.executive_summary }}
</div>

---

<div style="page-break-before: always;"></div>

## 2. Infrastructure & Asset Discovery

### 2.1 Domain & Network Footprint
{% if case.infrastructure_details_md %}{{ case.infrastructure_details_md | safe }}{% endif %}

---

## 3. Threat Findings & Compromise Identifiers

{{ findings.detailed_findings }}

---

<div style="page-break-before: always;"></div>

## 4. Tooling & OSINT Collection Frameworks

{% if case.tools_used_table %}{{ case.tools_used_table | safe }}{% else %}{{ case.tools_used | safe }}{% endif %}

<div class="hash-box">
  <code>SHA-256 Package Hash: {{ case.sha256_hash or "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991678526855" }}</code>
</div>