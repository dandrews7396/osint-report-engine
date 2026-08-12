<div style="text-align: center; margin-bottom: 30px;">

# ATTESTATION OF OSINT ASSESSMENT
**Formal Letter of Intelligence Investigation**

</div>

**Date:** {% if case.report_date %}{{ case.report_date }}{% else %}N/A{% endif %}  
**Case Reference:** {{ case.case_ref }}  
**Client:** {{ client.name }}  

---

### To Whom It May Concern,

This letter confirms that **{{ firm.name }}** was formally retained by **{{ client.name }}** to perform an Open Source Intelligence (OSINT) assessment under the following parameters:

> **Target Scope:** {{ case.target_scope or case.case_name }}  
> **Investigation Window:** {% if case.start_date %}{{ case.start_date }}{% else %}N/A{% endif %} through {% if case.end_date %}{{ case.end_date }}{% else %}N/A{% endif %}  
> **Assessment Category:** {{ case.case_type }}  

### Compliance & Methodology Statement
All collection and analysis procedures were conducted exclusively against publicly available information sources in accordance with OSINT standards and supported by a established **Legitimate Interest** framework. No invasive network penetration, illegal access, or non-public data intrusion took place.

### Summary
The assessment analyzed open digital footprints, public domain records, external exposure points, and associated risk factors. An executive intelligence report containing detailed evidence artifacts and recommended risk mitigations has been delivered directly to **{{ client.name }}**.

### Authorizing Investigator

**{{ investigator.name }}**  
{% if investigator.title %}{{ investigator.title }}<br>{% endif %}
*{{ firm.name }}*

{% if investigator.description %}
*Investigator Bio:*  
{{ investigator.description }}
{% endif %}

---

<div style="margin-top: 40px; font-size: 0.85em; color: #718096; text-align: center;">
This attestation letter verifies that an OSINT evaluation was executed for the specified scope. It does not represent a guarantee regarding undisclosed offline activities or unindexed threat vectors.
</div>