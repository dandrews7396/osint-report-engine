# OPEN SOURCE INTELLIGENCE REPORT

<div style="margin-top: 40px; margin-bottom: 50px;">

| **Case Name:** | {{ case.case_name }} |
| **Case Reference:** | {{ case.case_ref }} |
| **Investigation Type:** | {{ case.case_type }} |
| **Prepared For:** | {{ client.name }} |
| **Prepared By:** | {{ firm.name }} |
| **Lead Investigator:** | {{ investigator.name }}{% if investigator.title %} ({{ investigator.title }}){% endif %} |
| **Investigation Period:** | {{ case.start_date_formatted }} – {{ case.end_date_formatted }} |
| **Report Date:** | {{ case.report_date_formatted }} |

</div>

---

<div style="page-break-before: always;"></div>

## Executive Summary

{{ firm.executive_summary }}

### Key Findings Summary
{{ firm.key_findings_summary }}

---

## Scope & Legitimate Interest

**Target Scope:**  
{{ firm.target_scope }}

**Legitimate Interest / Legal Basis:**  
{{ firm.legitimate_interest }}

---

## Intelligence Findings Overview

{{ case.findings_chart | safe }}

{{ findings_table | safe }}

---

<div style="page-break-before: always;"></div>

## Methodology & Intelligence Tools

The following specialized open-source intelligence platforms, collection frameworks, and verification tools were utilized during this assessment:

{{ case.tools_used_table | safe }}

---

## Investigator Profile

**Lead Investigator:** {{ investigator.name }}  
{% if investigator.title %}**Title / Designation:** {{ investigator.title }}<br>{% endif %}

{{ investigator.description }}

---

<div style="page-break-before: always;"></div>

## Detailed Findings & Intelligence Analysis

{{ findings.detailed_findings }}