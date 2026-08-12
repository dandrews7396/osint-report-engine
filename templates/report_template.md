# OPEN SOURCE INTELLIGENCE REPORT

<div style="margin-top: 40px; margin-bottom: 50px;">

| **Case Name:** | {{ case.case_name }} |
| **Case Reference:** | {{ case.case_ref }} |
| **Investigation Type:** | {{ case.case_type }} |
| **Prepared For:** | {{ client.name }} |
| **Prepared By:** | {{ firm.name }} |
| **Lead Investigator:** | {{ investigator.name }}{% if investigator.title %} ({{ investigator.title }}){% endif %} |
| **Investigation Period:** | {% if case.start_date %}{{ case.start_date }}{% else %}N/A{% endif %} – {% if case.end_date %}{{ case.end_date }}{% else %}N/A{% endif %} |
| **Report Date:** | {% if case.report_date %}{{ case.report_date }}{% else %}N/A{% endif %} |

</div>

---

<div style="page-break-before: always;"></div>

## Executive Summary

{{ case.executive_summary }}

### Key Findings Summary
{{ case.key_findings_summary }}

---

## Scope & Legitimate Interest

**Target Scope:**  
{{ case.target_scope }}

**Legitimate Interest / Legal Basis:**  
{{ case.legitimate_interest }}

---

## Intelligence Findings Overview

{{ case.findings_chart | safe }}

{% if case.findings_table %}{{ case.findings_table | safe }}{% else %}{{ findings_table | safe }}{% endif %}

---

<div style="page-break-before: always;"></div>

## Methodology & Intelligence Tools

The following specialized open-source intelligence platforms, collection frameworks, and verification tools were utilized during this assessment:

{% if case.tools_used_table %}{{ case.tools_used_table | safe }}{% else %}{{ case.tools_used | safe }}{% endif %}

---

## Investigator Profile

**Lead Investigator:** {{ investigator.name }}  
{% if investigator.title %}**Title / Designation:** {{ investigator.title }}<br>{% endif %}

{{ investigator.description }}

---

<div style="page-break-before: always;"></div>

## Detailed Findings & Intelligence Analysis

{% if findings and findings.detailed_findings %}{{ findings.detailed_findings }}{% endif %}