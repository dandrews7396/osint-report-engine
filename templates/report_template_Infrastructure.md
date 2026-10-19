<div class="header-container">
  <div class="agency-title">{{ firm.name | upper }}</div>
  <div class="report-title">EXTERNAL THREAT SURFACE ASSESSMENT</div>
  <div class="report-subtitle">INFRASTRUCTURE & DIGITAL FOOTPRINT ANALYSIS</div>
</div>

<table class="edd-cover-grid">
  <tr>
    <td class="label">Task Ref:</td>
    <td class="value">{{ task.task_ref }}</td>
    <td class="label">Classification:</td>
    <td class="value highlight-red">RESTRICTED - TECHNICAL</td>
  </tr>
  <tr>
    <td class="label">Date:</td>
    <td class="value">{% if task.report_date %}{{ task.report_date }}{% else %}N/A{% endif %}</td>
    <td class="label">Target Scope:</td>
    <td class="value"><strong>{% if task.target_scope %}{{ task.target_scope }}{% else %}N/A{% endif %}</strong></td>
  </tr>
  <tr>
    <td class="label">Client Name:</td>
    <td class="value">{{ client.name }}</td>
    <td class="label">Assessment Type:</td>
    <td class="value">{{ task.task_type }}</td>
  </tr>
  <tr>
    <td class="label">Lead Analyst:</td>
    <td class="value">{% if task.investigator_name %}{{ task.investigator_name }}{% else %}N/A{% endif %}</td>
    <td class="label">Scanning Window:</td>
    <td class="value">{% if task.start_date %}{{ task.start_date }}{% else %}N/A{% endif %} – {% if task.end_date %}{{ task.end_date }}{% else %}N/A{% endif %}</td>
  </tr>
</table>

---

## 1. Technical Threat Overview

<div class="risk-summary-box {{ task.overall_risk_level | lower | replace(' ', '-') }}">
  <strong>External Exposure Profile:</strong> {% if task.overall_risk_classification %}{{ task.overall_risk_classification }}{% else %}N/A{% endif %}
</div>

### 1.1 Exposure Summary Matrix
{% if task.findings_matrix_table %}{{ task.findings_matrix_table | safe }}{% else %}{{ findings_table | safe }}{% endif %}

<div class="executive-assessment-block">
  <strong>Technical Assessment:</strong> {{ firm.executive_summary }}
</div>

---

<div style="page-break-before: always;"></div>

## 2. Infrastructure & Asset Discovery

### 2.1 Domain & Network Footprint
{% if task.infrastructure_details_md %}{{ task.infrastructure_details_md | safe }}{% endif %}

---

## 3. Threat Findings & Compromise Identifiers

{% if findings %}
{% for finding in findings %}
### {{ finding.title }}

- **Risk Level:** {{ finding.risk_level }}
- **Source Confidence:** {{ finding.confidence_level }}
{% if finding.subject_name %}- **Linked Subject:** {{ finding.subject_name }}{% endif %}
{% if finding.summary %}
**Executive Summary:** {{ finding.summary }}
{% endif %}
{% if finding.category_summary_lines %}
**Category Details:**
{% for label, value in finding.category_summary_lines %}
- **{{ label }}:** {{ value }}
{% endfor %}
{% endif %}
{% if finding.source %}- **Source:** {{ finding.source }}{% endif %}
{% if finding.description %}
**Detailed Findings & Intelligence Analysis:**
{{ finding.description }}
{% endif %}

{% endfor %}
{% else %}
No findings have been recorded for this task.
{% endif %}

---

<div style="page-break-before: always;"></div>

## 4. Tooling & OSINT Collection Frameworks

{% if task.tools_used_table %}{{ task.tools_used_table | safe }}{% else %}{{ task.tools_used | safe }}{% endif %}

<div class="hash-box">
  <code>SHA-256 Package Hash: {{ task.sha256_hash or "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991678526855" }}</code>
</div>