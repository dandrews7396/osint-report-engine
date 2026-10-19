{% macro finding_card(finding) %}
<div class="brief-finding">
<div class="brief-finding-heading">
<div class="brief-eyebrow">{{ finding.category | e }}</div>
<h3>{{ finding.title | e }}</h3>
<span class="risk-badge {{ finding.risk_level | e }}">{{ finding.risk_level | e }}</span>
<span class="brief-confidence">{{ finding.confidence_level | default('Unspecified', true) | e }}</span>
{% if finding.summary %}<p class="brief-finding-summary">{{ finding.summary | e }}</p>{% endif %}
</div>
{% if finding.category_summary_lines %}
<dl class="brief-facts brief-finding-facts">
{% for label, value in finding.category_summary_lines %}
<div><dt>{{ label | e }}</dt><dd>{{ value | e }}</dd></div>
{% endfor %}
</dl>
{% endif %}
{% if finding.description %}
<div class="brief-analysis">
<div class="brief-eyebrow">Analysis &amp; evidence</div>
{{ finding.description }}
</div>
{% endif %}
{% if finding.source %}<div class="brief-source"><strong>Source</strong> {{ finding.source | e }}</div>{% endif %}
</div>
{% endmacro %}

<div class="brief-report">
<div class="brief-masthead">
<div class="brief-eyebrow">{{ firm.name | e }} / Intelligence brief</div>
<h1>{{ task.task_type | default('OSINT investigation', true) | e }}</h1>
<p class="brief-deck">{{ task.task_name | e }}</p>
<div class="brief-reference">{{ task.task_ref | e }} &nbsp; / &nbsp; {{ task.report_date | default('Date not supplied', true) | e }}</div>
</div>

<dl class="brief-facts brief-engagement">
<div><dt>Prepared for</dt><dd>{{ client.name | e }}</dd></div>
<div><dt>Lead investigator</dt><dd>{{ investigator.name | e }}{% if investigator.title %} / {{ investigator.title | e }}{% endif %}</dd></div>
<div><dt>Investigation period</dt><dd>{{ task.start_date | default('Not supplied', true) | e }} &ndash; {{ task.end_date | default('Not supplied', true) | e }}</dd></div>
<div><dt>Operation</dt><dd>{{ task.operation_name | default('Not supplied', true) | e }}</dd></div>
<div><dt>Persona reference</dt><dd>{{ task.covert_persona_reference | default('Not supplied', true) | e }}</dd></div>
</dl>

<div class="brief-section-heading"><span>01 / Overview</span><h2>The assessment at a glance</h2></div>
<div class="brief-metrics">
<div><strong>{{ subjects | length }}</strong><span>Subjects reviewed</span></div>
<div><strong>{{ findings | length }}</strong><span>Recorded findings</span></div>
<div><strong>{{ risk_counts['Critical'] + risk_counts['High'] }}</strong><span>High / critical findings</span></div>
</div>
<div class="brief-risk-strip">
{% for risk, count in risk_counts.items() %}
<span><span class="risk-badge {{ risk }}">{{ risk }}</span> <strong>{{ count }}</strong></span>
{% endfor %}
</div>
<div class="brief-callout"><div class="brief-eyebrow">Executive assessment</div><p>{{ task.executive_summary | default('No executive summary has been provided for this task.', true) | e }}</p></div>
<div class="brief-recommendations"><div class="brief-eyebrow">Key findings &amp; recommendations</div><p>{{ task.key_findings_summary | default('No key findings summary has been supplied for this task.', true) | e }}</p></div>

<div class="brief-section-heading"><span>02 / Mandate</span><h2>Scope &amp; collection boundaries</h2></div>
<div class="brief-mandate"><h3>Target scope</h3><p>{{ task.target_scope | default('No target scope supplied.', true) | e }}</p><h3>Legal authority</h3><p>{{ task.legitimate_interest | default('No lawful-basis statement supplied.', true) | e }}</p></div>

<div class="brief-subject-section">
<div class="brief-section-heading"><span>03 / Subject intelligence</span><h2>Profiles &amp; associated findings</h2></div>
<p class="brief-section-intro">Findings sit with the subject they concern, ordered by risk within each profile. Risk ratings apply to individual findings, not to the subject as a whole.</p>
{% for subject in subjects %}
<div class="brief-subject">
<div class="brief-profile">
<div class="brief-eyebrow">{{ subject.subject_type | e }} / Subject {{ loop.index }}</div>
<h2>{{ subject.display_name | e }}</h2>
<p class="brief-relationship">{{ subject.relationship_to_task | e }} <span>/ {{ subject.findings | length }} linked finding{% if subject.findings | length != 1 %}s{% endif %}</span></p>
{% if subject.summary_lines %}
<dl class="brief-facts">
{% for label, value in subject.summary_lines %}
<div><dt>{{ label | e }}</dt><dd>{{ value | e }}</dd></div>
{% endfor %}
</dl>
{% endif %}
{% if not subject.findings %}
<p class="brief-empty">No findings are linked to this subject. This does not establish the absence of risk.</p>
{% endif %}
</div>
{% for finding in subject.findings %}
{{ finding_card(finding) }}
{% endfor %}
</div>
{% else %}
<p class="brief-empty">No subjects have been recorded for this task.</p>
{% endfor %}
</div>

<div class="brief-section-heading"><span>04 / Wider context</span><h2>Unlinked findings</h2></div>
<p class="brief-section-intro">Task-wide observations and findings without a matching subject profile.</p>
{% for finding in unlinked_findings %}
{{ finding_card(finding) }}
{% else %}
<p class="brief-empty">No unlinked findings have been recorded.</p>
{% endfor %}

<div class="brief-methodology">
<div class="brief-section-heading"><span>05 / Methodology</span><h2>Tools &amp; sources</h2></div>
<p class="brief-section-intro">Collection methods and platforms recorded by the investigator.</p>
{% if task.tools_used_table %}{{ task.tools_used_table | safe }}{% else %}<p>No tools have been recorded.</p>{% endif %}
</div>
</div>
