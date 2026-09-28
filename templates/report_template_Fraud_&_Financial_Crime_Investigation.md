<div class="header-container">
  <div class="agency-title">{{ firm.name | upper }}</div>
  <div class="report-title">{{ task.task_type | upper }} REPORT</div>
</div>

<div class="report-shell">
<table class="edd-cover-grid">
  <tr>
    <td class="label">Task Name:</td>
    <td class="value">{{ task.task_name }}</td>
    <td class="label">Task Reference:</td>
    <td class="value">{{ task.task_ref }}</td>
  </tr>
  <tr>
    <td class="label">Investigation Type:</td>
    <td class="value">{{ task.task_type }}</td>
    <td class="label">Prepared For:</td>
    <td class="value">{{ client.name }}</td>
  </tr>
  <tr>
    <td class="label">Covert Persona Reference:</td>
    <td class="value">{{ task.covert_persona_reference or 'N/A' }}</td>
    <td class="label">Lead Investigator:</td>
    <td class="value">{{ investigator.name }}{% if investigator.title %} ({{ investigator.title }}){% endif %}</td>
  </tr>
  <tr>
    <td class="label">Investigation Period:</td>
    <td class="value">{% if task.start_date %}{{ task.start_date }}{% else %}N/A{% endif %} – {% if task.end_date %}{{ task.end_date }}{% else %}N/A{% endif %}</td>
    <td class="label">Report Date:</td>
    <td class="value">{% if task.report_date %}{{ task.report_date }}{% else %}N/A{% endif %}</td>
  </tr>
</table>
</div>

---

**Operation:** {{ task.operation_name or "N/A" }}

## Scope, Legal Basis & Task Context

<div class="task-context-block">
  <div class="task-context-header">Task Instruction & Lawful Basis</div>
  <div class="task-context-row">
    <span class="task-context-label">Target Scope</span>
    <div class="task-context-value">{{ task.target_scope if task.target_scope else 'No target scope supplied.' }}</div>
  </div>
  <div class="task-context-row">
    <span class="task-context-label">Legitimate Interest / Legal Basis</span>
    <div class="task-context-value">{{ task.legitimate_interest if task.legitimate_interest else 'No lawful-basis statement supplied.' }}</div>
  </div>
</div>

---

## Executive Summary & Key Findings

{% if task.executive_summary %}
{{ task.executive_summary }}
{% else %}
No executive summary has been provided for this task.
{% endif %}

### Key Findings Summary
{% if task.key_findings_summary %}
{{ task.key_findings_summary }}
{% else %}
No key findings summary has been supplied for this task.
{% endif %}

{{ task.findings_chart | safe }}

---

## Intelligence Tools & Methodology

{% if task.tools_used_table %}{{ task.tools_used_table | safe }}{% else %}{{ task.tools_used | safe }}{% endif %}

---

## Subjects & Relevant Subject Findings

{% if subjects %}
{% for subject in subjects %}
### {{ subject.display_name }}{% if subject.subject_type %} ({{ subject.subject_type }}){% endif %}

- **Relationship to Task:** {{ subject.relationship_to_task }}

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
No subjects have been recorded for this task.
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
No findings have been recorded for this task.
{% endif %}
