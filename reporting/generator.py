import os
import re
import json
import logging
import markdown
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import uuid
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from jinja2.sandbox import SandboxedEnvironment
from weasyprint import HTML
from database import operations as db

logger = logging.getLogger(__name__)

def format_date_with_suffix(date_str):
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        day = dt.day
        if 11 <= day <= 13:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
        return dt.strftime(f'%B {day}{suffix}, %Y')
    except Exception:
        return date_str


def _normalize_report_text(value):
    if not value:
        return ''
    text = str(value).replace('&nbsp;', ' ')
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip().lower()


def generate_report(case, client, firm, findings, output_path, include_risk_graphs: bool = True):
    """
    Generates an OSINT Intelligence PDF report using Jinja2 + WeasyPrint.
    Dynamically renders case findings, risk distributions, and intelligence evidence.
    """
    try:
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
        
        case_type = case.get('case_type', '')
        safe_type = case_type.replace(' ', '_').replace('/', '_')
        custom_template_path = os.path.join(template_dir, f'report_template_{safe_type}.md')
        default_template_path = os.path.join(template_dir, 'report_template.md')
        md_template_path = custom_template_path if os.path.exists(custom_template_path) else default_template_path
        logger.info("Report template selection: case_type=%r, safe_type=%r, custom_exists=%s, chosen=%s", case_type, safe_type, os.path.exists(custom_template_path), md_template_path)
        
        with open(md_template_path, 'r', encoding='utf-8') as f:
            md_content = f.read()

        case['report_date_formatted'] = format_date_with_suffix(case.get('report_date', ''))
        case['start_date_formatted'] = format_date_with_suffix(case.get('start_date', ''))
        case['end_date_formatted'] = format_date_with_suffix(case.get('end_date', ''))

        risk_rank = {
            'Critical': 1,
            'High': 2,
            'Medium': 3,
            'Low': 4,
            'Informational': 5
        }
        
        # Sort findings strictly by risk_level primary
        findings.sort(key=lambda x: risk_rank.get(x.get('risk_level', 'Informational'), 99))

        subjects = db.get_case_subjects(case['id'])
        findings_by_subject = {}
        for finding in findings:
            subject_id = finding.get('subject_id')
            if subject_id:
                findings_by_subject.setdefault(subject_id, []).append(finding)
        for subject in subjects:
            subject['findings'] = findings_by_subject.get(subject['id'], [])

        risk_counts = { 'Critical': 0, 'High': 0, 'Medium': 0, 'Low': 0, 'Informational': 0 }
        
        for finding in findings:
            risk = finding.get('risk_level', 'Informational')
            if risk in risk_counts:
                risk_counts[risk] += 1
            else:
                risk_counts['Informational'] += 1
            
            finding['anchor'] = re.sub(r'[^a-z0-9]+', '-', (finding.get('title') or '').lower()).strip('-')
            
            description_raw = finding.get('description', '') or ''
            evidence_raw = finding.get('evidence', '') or ''
            normalized_description = _normalize_report_text(description_raw)
            normalized_evidence = _normalize_report_text(evidence_raw)
            finding['include_evidence_section'] = bool(
                evidence_raw and not (
                    normalized_description and normalized_evidence and normalized_description == normalized_evidence
                )
            )
            finding['evidence_html'] = markdown.markdown(
                evidence_raw,
                extensions=['fenced_code', 'tables', 'md_in_html', 'toc', 'attr_list']
            ) if finding['include_evidence_section'] else ''

        # Summary Table Construction
        table_html = '<div style="page-break-inside: avoid; margin-bottom: 20px;">\n'
        table_html += '<table style="width: 100%; border-collapse: collapse; border: 1px solid #333;">\n'
        table_html += '  <thead>\n'
        table_html += '    <tr>\n'
        table_html += '      <th style="border: 1px solid #333; background-color: #555; color: white; padding: 10px; font-weight: bold; width: 28%; text-align: center;">Intelligence Finding</th>\n'
        table_html += '      <th style="border: 1px solid #333; background-color: #555; color: white; padding: 10px; font-weight: bold; width: 16%; text-align: center;">Risk Rating</th>\n'
        table_html += '      <th style="border: 1px solid #333; background-color: #555; color: white; padding: 10px; font-weight: bold; width: 30%; text-align: center;">Category / Target Scope</th>\n'
        table_html += '      <th style="border: 1px solid #333; background-color: #555; color: white; padding: 10px; font-weight: bold; width: 26%; text-align: center;">Linked Subject</th>\n'
        table_html += '    </tr>\n'
        table_html += '  </thead>\n'
        table_html += '  <tbody>\n'
        
        color_map = {
            'Critical': '#9b2c2c',
            'High': '#c53030',
            'Medium': '#dd6b20',
            'Low': '#38a169',
            'Informational': '#3182ce'
        }
        
        for finding in findings:
            risk = finding.get('risk_level', 'Informational')
            bg_color = color_map.get(risk, '#555')
            
            scope_or_cat = finding.get('category') or finding.get('target') or 'N/A'
            if scope_or_cat != 'N/A':
                items = [i.strip() for i in scope_or_cat.split(',') if i.strip()]
                item_links = []
                for item in items:
                    if item.startswith('http'):
                        item_links.append(f'<a href="{item}" style="color: #fff; text-decoration: underline;">{item}</a>')
                    else:
                        item_links.append(item)
                target_html = '<br>'.join(item_links) if item_links else 'N/A'
            else:
                target_html = 'N/A'
                
            title_slug = finding['anchor']
            title_html = f'<a href="#{title_slug}" style="color: #6b46c1; text-decoration: underline;">{finding["title"]}</a>'
            subject_html = finding.get('subject_name') or 'Unassigned'
            
            table_html += f'    <tr>\n'
            table_html += f'      <td style="border: 1px solid #333; padding: 10px; text-align: center; background-color: white;">{title_html}</td>\n'
            table_html += f'      <td style="border: 1px solid #333; padding: 10px; background-color: {bg_color}; color: white; font-weight: bold; text-align: center;">{risk}</td>\n'
            table_html += f'      <td style="border: 1px solid #333; padding: 10px; text-align: center; color: #fff; background-color: #2c3e50;">{target_html}</td>\n'
            table_html += f'      <td style="border: 1px solid #333; padding: 10px; text-align: center; background-color: #1f2933; color: #fff;">{subject_html}</td>\n'
            table_html += f'    </tr>\n'
            
        table_html += '  </tbody>\n</table>\n</div>'
        
        md_content = md_content.replace('{{ findings.table }}', '{{ findings_table }}')
        
        # --- Risk Level Chart Generation ---
        if include_risk_graphs:
            labels = ['Critical', 'High', 'Medium', 'Low', 'Informational']
            counts = [risk_counts.get(risk, 0) for risk in labels]
            
            max_count = max(counts) if counts else 0
            if max_count <= 7:
                y_max = 7
                y_step = 1
            else:
                y_max = max_count + (5 - (max_count % 5)) if max_count % 5 != 0 else max_count
                y_step = max(1, y_max // 5)
                
            fig, ax = plt.subplots(figsize=(7, 4))
            colors = ['#c00000', '#ff0000', '#ff9933', '#ffcc00', '#99cc00']
            bars = ax.bar(labels, counts, color=colors, width=0.5)
            
            ax.set_title('Intelligence Findings by Risk Rating', fontsize=16, fontweight='bold', pad=20)
            ax.set_ylim(0, y_max)
            ax.set_yticks(list(range(0, y_max + 1, y_step)))
            
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_color('#333')
            ax.spines['left'].set_color('#333')
            
            for bar in bars:
                yval = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2.0, yval + (y_max * 0.02), int(yval), ha='center', va='bottom', fontweight='bold', fontsize=12)
                
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            chart_filename = f"chart_{uuid.uuid4().hex}.png"
            chart_path = os.path.join(os.path.dirname(output_path), chart_filename)
            
            plt.tight_layout()
            plt.savefig(chart_path, dpi=150)
            plt.close(fig)
            
            chart_html = f'<div style="text-align: center; margin: 40px 0; page-break-inside: avoid;"><img src="file://{os.path.abspath(chart_path)}" style="max-width: 600px; width: 100%;"></div>'
            case['findings_chart'] = chart_html
        else:
            case['findings_chart'] = ''
        
        detailed_findings_md = """
{% for finding in findings %}
{% if not loop.first %}
<div style="page-break-before: always;"></div>
{% endif %}

<div style="page-break-inside: avoid;" markdown="1">
### <a name="{{ finding.anchor }}"></a>{{ finding.title }}

<div style="margin-bottom: 10px;">
    <span class="risk-badge {{ finding.risk_level }}">{{ finding.risk_level }}</span>
    {% if finding.confidence_level %}&nbsp; <strong>Confidence Level:</strong> {{ finding.confidence_level }}{% endif %}
    {% if finding.category %}&nbsp; | <strong>Category:</strong> {{ finding.category }}{% endif %}
</div>

{% if finding.target %}**Target / Subject:** {{ finding.target }}<br>{% endif %}
{% if finding.location %}**Location / Source URL:** {{ finding.location }}<br>{% endif %}
{% if finding.subject_name %}**Linked Subject:** {{ finding.subject_name }}<br>{% endif %}

<div style="page-break-after: avoid; font-weight: bold; margin-bottom: 10px; margin-top: 20px;">Finding Description & Analysis:</div>
</div>

{{ finding.description }}

{% if finding.remediation %}
<div style="page-break-after: avoid; font-weight: bold; margin-bottom: 10px; margin-top: 20px;">Recommended Action / Mitigation:</div>

{{ finding.remediation }}
{% endif %}

{% if finding.include_evidence_section and finding.evidence_html and finding.evidence_html.strip() %}
<div style="page-break-after: avoid; font-weight: bold; margin-bottom: 10px; margin-top: 20px;">Intelligence Evidence & Collected Data:</div>

<div class="markdown-content">{{ finding.evidence_html | safe }}</div>
{% endif %}

{% if finding.refs %}
<div style="page-break-after: avoid; font-weight: bold; margin-bottom: 10px; margin-top: 20px;">Sources & References:</div>

{% for ref in finding.refs.splitlines() %}
{% if ref.strip() %}
- <a href="{{ ref.strip() }}" target="_blank" style="word-break: break-all;">{{ ref.strip() }}</a>
{% endif %}
{% endfor %}
{% endif %}
{% endfor %}
"""
        md_content = md_content.replace('{% if findings and findings.detailed_findings %}{{ findings.detailed_findings }}{% endif %}', detailed_findings_md)
        md_content = md_content.replace('{{ findings.detailed_findings }}', detailed_findings_md)
        env = SandboxedEnvironment()
        template = env.from_string(md_content)
        
        firm_dict = dict(firm)
        firm_dict['executive_summary'] = case.get('executive_summary', firm_dict.get('executive_summary', ''))
        firm_dict['key_findings_summary'] = case.get('key_findings_summary', firm_dict.get('key_findings_summary', ''))
        firm_dict['legitimate_interest'] = case.get('legitimate_interest', firm_dict.get('legitimate_interest', ''))
        firm_dict['target_scope'] = case.get('target_scope', firm_dict.get('target_scope', ''))
        firm_dict['tools_used'] = case.get('tools_used', firm_dict.get('tools_used', ''))
        
        investigator = {
            'name': case.get('investigator_name', ''),
            'description': case.get('investigator_description', ''),
            'title': ''
        }
        
        for inv in db.get_investigators():
            if inv['name'] == investigator['name']:
                investigator['description'] = inv.get('bio', '')
                investigator['title'] = inv.get('title', '')
                break
        
        tools_str = case.get('tools_used', '[]')
        try:
            tools_list = json.loads(tools_str)
            if tools_list and isinstance(tools_list, list):
                tools_html = "<div style=\"page-break-inside: avoid;\">\n<table class=\"tools-table\">\n<tr><th>OSINT Tool / Platform</th><th>Usage Description</th></tr>\n"
                for t in tools_list:
                    name = t.get('Name', '')
                    desc = t.get('Description', '').replace('\n', '<br>')
                    tools_html += f"<tr><td>{name}</td><td>{desc}</td></tr>\n"
                tools_html += "</table>\n</div>"
                case['tools_used_table'] = tools_html
            else:
                case['tools_used_table'] = tools_str.replace('\n', '<br>')
        except Exception:
            case['tools_used_table'] = tools_str.replace('\n', '<br>')
            
        rendered_md = template.render(
            case=case,
            client=client,
            firm=firm_dict,
            investigator=investigator,
            findings=findings,
            subjects=subjects,
            findings_table=table_html
        )
        
        report_html_body = markdown.markdown(rendered_md, extensions=['fenced_code', 'tables', 'md_in_html', 'toc', 'attr_list'])
        
        html_env = Environment(loader=FileSystemLoader(template_dir))
        html_template = html_env.get_template('report_template.html')
        final_html = html_template.render(body=report_html_body, firm=firm_dict, case=case, client=client)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        project_root = os.path.dirname(os.path.dirname(__file__))
        HTML(string=final_html, base_url=project_root).write_pdf(output_path)
        
        logger.info(f"Successfully generated OSINT PDF report at {output_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        raise

def generate_attestation(case, client, firm, output_path, custom_bio=None):
    """
    Generates an OSINT Investigation Attestation Letter PDF.
    """
    try:
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
        md_template_path = os.path.join(template_dir, 'attestation_template.md')
        
        with open(md_template_path, 'r', encoding='utf-8') as f:
            md_content = f.read()

        case['report_date_formatted'] = format_date_with_suffix(case.get('report_date', ''))
        case['start_date_formatted'] = format_date_with_suffix(case.get('start_date', ''))
        case['end_date_formatted'] = format_date_with_suffix(case.get('end_date', ''))

        firm_dict = {f.get('key'): f.get('value') for f in firm} if isinstance(firm, list) else firm

        investigator = {
            'name': case.get('investigator_name', ''),
            'description': case.get('investigator_description', ''),
            'title': ''
        }
        if investigator['name']:
            db_investigators = db.get_investigators()
            db_inv = next((i for i in db_investigators if i['name'] == investigator['name']), None)
            if db_inv:
                investigator['description'] = custom_bio if custom_bio is not None else db_inv.get('bio', '')
                investigator['title'] = db_inv.get('title', '')
                
        env = SandboxedEnvironment()
        template = env.from_string(md_content)
        
        rendered_md = template.render(
            case=case,
            client=client,
            firm=firm_dict,
            investigator=investigator
        )
        
        report_html_body = markdown.markdown(rendered_md, extensions=['fenced_code', 'tables', 'md_in_html', 'attr_list'])
        
        html_env = Environment(loader=FileSystemLoader(template_dir))
        html_template = html_env.get_template('attestation_wrapper.html')
        project_root = os.path.dirname(os.path.dirname(__file__))
        
        final_html = html_template.render(
            content=report_html_body, 
            firm=firm_dict, 
            case=case, 
            client=client, 
            base_dir=project_root
        )

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        HTML(string=final_html, base_url=project_root).write_pdf(output_path)
        
        logger.info(f"Successfully generated Attestation Letter at {output_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to generate attestation: {e}")
        raise