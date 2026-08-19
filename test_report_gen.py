import os
import json
import logging
from unittest.mock import MagicMock

# Optional: Silence verbose Matplotlib / Weasyprint logs during test run
logging.basicConfig(level=logging.INFO)

# Mock database.operations if the database isn't fully seeded locally
import sys
from database import findings as finding_schema

mock_db = MagicMock()
mock_db.get_investigators.return_value = [
    {
        'name': 'Alex Mercer',
        'title': 'Principal OSINT Investigator',
        'bio': 'Senior Intelligence Analyst specializing in dark web intelligence, cloud footprint mapping, and OSINT risk analysis.'
    }
]
sys.modules['database'] = MagicMock()
sys.modules['database.operations'] = mock_db
sys.modules['database.findings'] = finding_schema

from reporting.generator import generate_report, generate_attestation

# Mock OSINT Case Data
case_data = {
    'case_name': 'Project Apex External Intelligence Assessment',
    'case_ref': 'OSINT-2026-0812',
    'case_type': 'Enhanced Due Diligence',
    'report_date': '2026-08-12',
    'start_date': '2026-08-01',
    'end_date': '2026-08-10',
    'investigator_name': 'Alex Mercer',
    'investigator_description': 'Senior Intelligence Analyst specializing in dark web intelligence, cloud footprint mapping, and OSINT risk analysis.',
    'executive_summary': 'During the assessment period, an extensive open-source intelligence analysis was conducted against target infrastructure and digital footprints. Primary threats identified include unauthenticated cloud storage exposing sensitive financial backups, executive credential leaks across breach data aggregators, and social engineering vectors.',
    'key_findings_summary': 'Identified 1 Critical cloud storage leak, 1 High risk corporate credential compromise, and 1 Medium risk executive digital exposure vector.',
    'target_scope': 'apex-corp-global.com (*.apex-corp-global.com) and associated primary digital assets.',
    'legitimate_interest': 'Authorized security evaluation and threat surface evaluation executed under formal client engagement terms.',
    'tools_used': json.dumps([
        {'Name': 'Amass / Sublist3r', 'Description': 'Domain enumeration and subdomain surface mapping.'},
        {'Name': 'Dehashed / BreachDirectory', 'Description': 'Historical credential compromise analysis and verification.'},
        {'Name': 'Sherlock / SpiderFoot', 'Description': 'Cross-platform digital identity and social footprint tracking.'}
    ])
}

client_data = {
    'name': 'Apex Global Holdings Inc.'
}

firm_data = {
    'name': 'OSINT Intelligence Group',
    'executive_summary': case_data['executive_summary'],
    'key_findings_summary': case_data['key_findings_summary'],
    'target_scope': case_data['target_scope'],
    'legitimate_interest': case_data['legitimate_interest']
}

# Sample OSINT Findings Dataset
findings_data = [
    {
        'title': 'Unauthenticated S3 Bucket Exposing Corporate Financial Backups',
        'risk_level': 'Critical',
        'confidence_level': 'High',
        'category': 'Infrastructure & Network Assets',
        'category_data': {
            'asset_type': 'Cloud Storage',
            'asset_identifier': 's3://apex-backup-archive-2025',
            'hosting_provider_asn': 'Amazon Web Services',
            'website_technologies': 'AWS S3',
        },
        'source': 'https://apex-backup-archive-2025.s3.amazonaws.com',
        'description': 'A listable AWS S3 storage bucket was discovered containing unencrypted database dumps, internal financial audits, and employee HR exports.',
    },
    {
        'title': 'Exposed Corporate Credentials in Public Breach Aggregators',
        'risk_level': 'High',
        'confidence_level': 'High',
        'category': 'Leaked Data',
        'category_data': {
            'breach_source_name': 'Apex Global Holdings credential breach',
            'breach_date': '2026-01-05',
            'data_types_exposed': 'Credentials',
            'record_count': '12',
        },
        'source': 'Dehashed / breach-data analysis',
        'description': 'Multiple corporate email accounts and associated plaintext/hashed passwords were verified across recent third-party breach datasets.',
    },
    {
        'title': 'Executive Footprint & Social Engineering Target Vectors',
        'risk_level': 'Medium',
        'confidence_level': 'Medium',
        'category': 'Social Media & Digital Footprint',
        'category_data': {
            'platform': 'LinkedIn',
            'username': 'apex-executive',
            'display_name': 'Apex Executive',
            'capture_date': '2026-08-10',
            'archive_method': 'Manual screenshot',
        },
        'source': 'LinkedIn public profile',
        'description': 'Excessive operational metadata and security information regarding executive personnel were identified on public social platforms.',
    }
]

output_dir = os.path.join(os.path.dirname(__file__), 'output')
output_report_path = os.path.join(output_dir, 'Sample_OSINT_Intelligence_Report.pdf')
output_attestation_path = os.path.join(output_dir, 'Sample_OSINT_Attestation_Letter.pdf')

print("Starting PDF generation test...")

# 1. Generate OSINT Intelligence Report
generate_report(case_data, client_data, firm_data, findings_data, output_report_path)
print(f"✓ OSINT Intelligence Report generated at: {os.path.abspath(output_report_path)}")

# 2. Generate OSINT Attestation Letter
generate_attestation(case_data, client_data, firm_data, output_attestation_path)
print(f"✓ OSINT Attestation Letter generated at: {os.path.abspath(output_attestation_path)}")

print("\nTest completed successfully!")