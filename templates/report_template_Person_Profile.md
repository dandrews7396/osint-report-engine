<div class="header-container">
  <div class="agency-title">{{ firm.name | upper }}</div>
  <div class="report-title">{{ case.case_type | upper }} REPORT</div>
</div>

<div class="report-shell">
<table class="edd-cover-grid">
  <tr>
    <td class="label">Case Name:</td>
    <td class="value">{{ case.case_name }}</td>
    <td class="label">Case Reference:</td>
    <td class="value">{{ case.case_ref }}</td>
  </tr>
  <tr>
    <td class="label">Investigation Type:</td>
    <td class="value">{{ case.case_type }}</td>
    <td class="label">Prepared For:</td>
    <td class="value">{{ client.name }}</td>
  </tr>
  <tr>
    <td class="label">Covert Persona Reference:</td>
    <td class="value">{{ case.covert_persona_reference or 'N/A' }}</td>
    <td class="label">Lead Investigator:</td>
    <td class="value">{{ investigator.name }}{% if investigator.title %} ({{ investigator.title }}){% endif %}</td>
  </tr>
  <tr>
    <td class="label">Investigation Period:</td>
    <td class="value">{% if case.start_date %}{{ case.start_date }}{% else %}N/A{% endif %} – {% if case.end_date %}{{ case.end_date }}{% else %}N/A{% endif %}</td>
    <td class="label">Report Date:</td>
    <td class="value">{% if case.report_date %}{{ case.report_date }}{% else %}N/A{% endif %}</td>
  </tr>
</table>
</div>

---

## Scope, Legal Basis & Case Context

<div class="case-context-block">
  <div class="case-context-header">Case Instruction & Lawful Basis</div>
  <div class="case-context-row">
    <span class="case-context-label">Target Scope</span>
    <div class="case-context-value">{{ case.target_scope if case.target_scope else 'No target scope supplied.' }}</div>
  </div>
  <div class="case-context-row">
    <span class="case-context-label">Legitimate Interest / Legal Basis</span>
    <div class="case-context-value">{{ case.legitimate_interest if case.legitimate_interest else 'No lawful-basis statement supplied.' }}</div>
  </div>
</div>

---

## Executive Summary & Key Findings

{% if case.executive_summary %}
{{ case.executive_summary }}
{% else %}
No executive summary has been provided for this case.
{% endif %}

### Key Findings Summary
{% if case.key_findings_summary %}
{{ case.key_findings_summary }}
{% else %}
No key findings summary has been supplied for this case.
{% endif %}

{{ case.findings_chart | safe }}

---

## Intelligence Tools & Methodology

{% if case.tools_used_table %}{{ case.tools_used_table | safe }}{% else %}{{ case.tools_used | safe }}{% endif %}

---

## Subjects & Relevant Subject Findings

{% if subjects %}
{% for subject in subjects %}
### {{ subject.display_name }}{% if subject.subject_type %} ({{ subject.subject_type }}){% endif %}

- **Relationship to Case:** {{ subject.relationship_to_case }}

{% if subject.summary_lines %}
**Subject Details:**
{% for label, value in subject.summary_lines %}
- **{{ label }}:** {{ value }}
{% endfor %}
{% endif %}

{% if subject.findings %}
**Relevant Subject Findings:**
{% for finding in subject.findings %}
- **{{ finding.title }}**{% if finding.risk_level %} — {{ finding.risk_level }}{% endif %}{% if finding.confidence_level %} — {{ finding.confidence_level }}{% endif %}
{% endfor %}
{% else %}
No linked findings recorded for this subject.
{% endif %}

{% endfor %}
{% else %}
No subjects have been recorded for this case.
{% endif %}

---

## General Findings & Intelligence Analysis

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
No findings have been recorded for this case.
{% endif %}
