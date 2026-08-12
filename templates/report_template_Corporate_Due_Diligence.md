<div class="header-container">
  <div class="agency-title">{{ firm.name | upper }}</div>
  <div class="report-title">ENHANCED DUE DILIGENCE REPORT</div>
  <div class="report-subtitle">CORPORATE INTELLIGENCE & RISK ASSESSMENT</div>
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
    <td class="label">Subject Entity:</td>
    <td class="value"><strong>{% if case.target_company_name %}{{ case.target_company_name }}{% else %}N/A{% endif %}</strong></td>
  </tr>
  <tr>
    <td class="label">Client Name:</td>
    <td class="value">{{ client.name }}</td>
    <td class="label">Company No:</td>
    <td class="value">{% if case.company_number %}{{ case.company_number }}{% else %}N/A{% endif %}</td>
  </tr>
  <tr>
    <td class="label">Instructing Ref:</td>
    <td class="value">{% if case.instructing_ref %}{{ case.instructing_ref }}{% else %}N/A{% endif %}</td>
    <td class="label">Primary Target / UBO:</td>
    <td class="value">{% if case.primary_target_name %}{{ case.primary_target_name }}{% else %}N/A{% endif %}</td>
  </tr>
  <tr>
    <td class="label">Lead Investigator:</td>
    <td class="value">{% if case.investigator_name %}{{ case.investigator_name }}{% else %}N/A{% endif %}</td>
    <td class="label">Investigation Period:</td>
    <td class="value">{% if case.start_date %}{{ case.start_date }}{% else %}N/A{% endif %} – {% if case.end_date %}{{ case.end_date }}{% else %}N/A{% endif %}</td>
  </tr>
</table>

---

## 1. Executive Summary & Overall Risk Rating

<div class="risk-summary-box {{ case.overall_risk_level | lower | replace(' ', '-') }}">
  <strong>Overall Risk Classification:</strong> {% if case.overall_risk_classification %}{{ case.overall_risk_classification }}{% else %}N/A{% endif %}
</div>

### 1.1 Instruction & Scope
{{ firm.name }} was instructed by {{ client.name }} on {% if case.start_date %}{{ case.start_date }}{% else %}N/A{% endif %} to conduct an Enhanced Due Diligence (EDD) background investigation into **{% if case.target_company_name %}{{ case.target_company_name }}{% else %}N/A{% endif %}** and its key controlling officers, specifically **{% if case.primary_target_name %}{{ case.primary_target_name }}{% else %}N/A{% endif %}**. The objective of this report is to evaluate corporate integrity, identify undisclosed financial risks, map beneficial ownership structures, and detect adverse media or legal regulatory flags.

### 1.2 Key Findings Matrix
A summary of critical risk indicators identified during open-source intelligence gathering is detailed below:

{% if case.findings_matrix_table %}{{ case.findings_matrix_table | safe }}{% else %}{{ findings_table | safe }}{% endif %}

<div class="executive-assessment-block">
  <strong>Executive Assessment:</strong> {% if firm.executive_summary %}{{ firm.executive_summary }}{% else %}N/A{% endif %}
</div>

---

<div style="page-break-before: always;"></div>

## 2. Corporate Entity Analysis

### 2.1 Corporate Profile

<table class="edd-keyvalue-table">
  <tr>
    <td class="kv-label">Registered Legal Name:</td>
    <td class="kv-value">{% if case.target_company_name %}{{ case.target_company_name }}{% else %}N/A{% endif %}</td>
  </tr>
  <tr>
    <td class="kv-label">Company Registration No:</td>
    <td class="kv-value">{% if case.company_number %}{{ case.company_number }}{% else %}N/A{% endif %}</td>
  </tr>
  <tr>
    <td class="kv-label">Date of Incorporation:</td>
    <td class="kv-value">{% if case.incorporation_date %}{{ case.incorporation_date }}{% else %}N/A{% endif %}</td>
  </tr>
  <tr>
    <td class="kv-label">Registered Office Address:</td>
    <td class="kv-value">{% if case.registered_address %}{{ case.registered_address }}{% else %}N/A{% endif %}</td>
  </tr>
  <tr>
    <td class="kv-label">Company Type & SIC Code:</td>
    <td class="kv-value">{% if case.company_type_sic %}{{ case.company_type_sic }}{% else %}N/A{% endif %}</td>
  </tr>
  <tr>
    <td class="kv-label">Current Filing Status:</td>
    <td class="kv-value">{% if case.filing_status %}{{ case.filing_status }}{% else %}N/A{% endif %}</td>
  </tr>
</table>

### 2.2 Ownership & PSC (Persons with Significant Control) Mapping
Analysis of official statutory registers and corporate filings reveals the following beneficial ownership structure:

{% if case.psc_mapping_table %}{{ case.psc_mapping_table | safe }}{% endif %}

---

## 3. Key Person Analysis (Directors & Officers)

Background analysis was conducted on primary officers to identify corporate track records, overlapping directorships, and personal financial integrity flags.

{% if case.primary_target_name %}### 3.1 Director Profile: {{ case.primary_target_name }}{% endif %}

<table class="edd-keyvalue-table">
  <tr>
    <td class="kv-label">Full Name & Aliases:</td>
    <td class="kv-value">{% if case.target_aliases %}{{ case.target_aliases }}{% else %}N/A{% endif %}</td>
  </tr>
  <tr>
    <td class="kv-label">Date of Birth & Nationality:</td>
    <td class="kv-value">{% if case.target_dob_nationality %}{{ case.target_dob_nationality }}{% else %}N/A{% endif %}</td>
  </tr>
  <tr>
    <td class="kv-label">Appointed Roles:</td>
    <td class="kv-value">{% if case.target_appointed_roles %}{{ case.target_appointed_roles }}{% else %}N/A{% endif %}</td>
  </tr>
  <tr>
    <td class="kv-label">Historic Directorships:</td>
    <td class="kv-value">{% if case.target_historic_directorships %}{{ case.target_historic_directorships }}{% else %}N/A{% endif %}</td>
  </tr>
  <tr>
    <td class="kv-label">Adverse Regulatory Checks:</td>
    <td class="kv-value">{% if case.target_regulatory_checks %}{{ case.target_regulatory_checks }}{% else %}N/A{% endif %}</td>
  </tr>
</table>

{% if case.directorship_track_record_notice %}
<div class="callout-warning">
  <strong>Directorship Track Record Notice:</strong> {{ case.directorship_track_record_notice }}
</div>
{% endif %}

---

<div style="page-break-before: always;"></div>

## 4. Litigation, Asset Mapping & Financial Integrity

### 4.1 Court Judgments & Legal Proceedings
Searches across the Registry Trust (CCJs & High Court Judgments) and official UK insolvency gazettes identified the following:

{% if case.litigation_details_md %}{{ case.litigation_details_md | safe }}{% endif %}

### 4.2 Real Estate & Asset Footprint
{% if case.real_estate_details_md %}{{ case.real_estate_details_md | safe }}{% endif %}

---

## 5. Digital Footprint & Adverse Media Audit

### 5.1 Infrastructure & Domain Analysis
{% if case.infrastructure_details_md %}{{ case.infrastructure_details_md | safe }}{% endif %}

### 5.2 Media & Social Media Exposure
{% if case.media_exposure_details_md %}{{ case.media_exposure_details_md | safe }}{% endif %}

---

<div style="page-break-before: always;"></div>

## 6. Methodology & Intelligence Standards

This investigation utilized structured open-source intelligence (OSINT) analytical frameworks. Information was sourced exclusively from open, legally accessible public domain records, official government registries, and proprietary intelligence databases.

<table class="confidence-table">
  <thead>
    <tr>
      <th>Confidence Rating</th>
      <th>Evaluation Criteria</th>
      <th>Applied Sources in This Report</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><span class="badge badge-high">HIGH CONFIDENCE</span></td>
      <td>Corroborated by official government bodies, land registers, or statutory court databases.</td>
      <td>Companies House API, HM Land Registry, Registry Trust, OFSI Sanctions List.</td>
    </tr>
    <tr>
      <td><span class="badge badge-med">MODERATE CONFIDENCE</span></td>
      <td>Sourced from reputable trade media, verified third-party databases, or single primary filings.</td>
      <td>National news archives, domain WHOIS history, corporate PR releases.</td>
    </tr>
    <tr>
      <td><span class="badge badge-low">LOW CONFIDENCE</span></td>
      <td>Unverified public forums, anonymous social media accounts, or uncorroborated leaks.</td>
      <td>Online forum comments, unverified employee reviews.</td>
    </tr>
  </tbody>
</table>

<div class="callout-note">
  <strong>Analytical Limitations:</strong> {{ case.analytical_limitations or "Offshore corporate entities registered in secrecy jurisdictions were assessed solely via publicly available cross-border leaks and UK cross-referencing." }}
</div>

---

## 7. Compliance Disclaimers & Legal Notice

1. **UK GDPR & Data Protection Compliance Notice:**  
   This document has been prepared in strict compliance with the UK General Data Protection Regulation (UK GDPR) and the Data Protection Act 2018. All personal data contained herein was processed under the lawful basis of **Legitimate Interest** (Art. 6(1)(f) UK GDPR) for the express purpose of legal dispute resolution, corporate fraud prevention, and risk mitigation.

2. **Limitation of Liability & Third-Party Reliance:**  
   This report was prepared solely for the use of **{{ client.name }}** for the specific purpose stated in Section 1. No third party may rely upon this report without express written consent from **{{ firm.name }}**.

3. **Civil Procedure Rules (CPR Part 35 Disclosure Warning):**  
   If this report or its underlying evidentiary artifacts are intended for submission in court proceedings, the instructing client must ensure appropriate evidentiary disclosure rules and chain-of-custody verification are adhered to.

<div class="hash-box">
  <strong>Evidentiary Chain of Custody Package Reference:</strong><br>
  <code>SHA-256 Case Archive Hash: {{ case.sha256_hash or "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991678526855" }}</code>
</div>

<table class="signoff-table">
  <tr>
    <td style="width: 50%;">
      <strong>Report Compiled By:</strong><br><br>
      ____________________________________<br>
      Senior Corporate Intelligence Analyst<br>
      <em>{{ firm.name }} OSINT Practice</em>
    </td>
    <td style="width: 50%;">
      <strong>Approved By:</strong><br><br>
      ____________________________________<br>
      Director of Investigations<br>
      <em>ICO Reg No: {{ firm.ico_number or "ZX123456789" }}</em>
    </td>
  </tr>
</table>