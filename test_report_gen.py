import os
import json
import logging
from unittest.mock import MagicMock

# Optional: Silence verbose Matplotlib / Weasyprint logs during test run
logging.basicConfig(level=logging.INFO)

# Mock database.operations if the database isn't fully seeded locally
import sys
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

from reporting.generator import generate_report, generate_attestation

# Mock OSINT Case Data
case_data = {
    'case_name': 'Project Apex External Intelligence Assessment',
    'case_ref': 'OSINT-2026-0812',
    'case_type': 'Corporate Due Diligence',
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
        'category': 'Cloud Leakage',
        'target': 's3://apex-backup-archive-2025',
        'location': 'https://apex-backup-archive-2025.s3.amazonaws.com',
        'description': 'A listable AWS S3 storage bucket was discovered containing unencrypted database dumps, internal financial audits, and employee HR exports.',
        'remediation': 'Apply AWS S3 Block Public Access restrictions, enforce IAM role-based access control, and conduct an access log audit.',
        'evidence': '### Discovered Bucket Objects\n\n| Object Key | File Size | Permissions |\n| --- | --- | --- |\n| `Q4_Financial_Audit.xlsx` | 14.2 MB | Public Read |\n| `db_dump_users.sql` | 112.8 MB | Public Read |\n| `vpn_client_keys.zip` | 2.1 MB | Public Read |\n\n```text\n$ aws s3 ls s3://apex-backup-archive-2025 --no-sign-request\n2025-11-12 14:02:11 14889201 Q4_Financial_Audit.xlsx\n2026-01-05 09:15:33 118281044 db_dump_users.sql\n```',
        'refs': 'https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html'
    },
    {
        'title': 'Exposed Corporate Credentials in Public Breach Aggregators',
        'risk_level': 'High',
        'confidence_level': 'High',
        'category': 'Credential Exposure',
        'target': 'apex-corp-global.com',
        'location': 'Dehashed / Dark Web Breach Archives',
        'description': 'Multiple corporate email accounts and associated plaintext/hashed passwords were verified across recent third-party breach datasets.',
        'remediation': 'Mandate global password resets for compromised users, enforce hardware token/MFA, and establish breach monitoring alerts.',
        'evidence': '### Exposed Accounts Summary\n\n- **Identified Compromised Accounts:** 12\n- **Exposed Hash Algorithms:** bcrypt, MD5, Plaintext\n\n```text\nexec.leadership@apex-corp-global.com : [Plaintext Password Exposed]\nadmin.sys@apex-corp-global.com : $2a$10$e8... (bcrypt)\n```',
        'refs': 'https://haveibeenpwned.com\nhttps://dehashed.com'
    },
    {
        'title': 'Executive Footprint & Social Engineering Target Vectors',
        'risk_level': 'Medium',
        'confidence_level': 'Medium',
        'category': 'HUMINT Exposure',
        'target': 'Executive Leadership Group',
        'location': 'LinkedIn / Public Media Profiles',
        'description': 'Excessive operational metadata and security information regarding executive personnel were identified on public social platforms.',
        'remediation': 'Conduct executive digital hygiene training and institute strict out-of-band validation requirements for high-value operations.',
        'evidence': '### Risk Factors\n\n- **ID Badge Exposure:** High-resolution photograph posted online reveals security badge format and clearance codes.\n- **Tech Infrastructure Details:** Technical posts disclose corporate SIEM and internal VPN suppliers.',
        'refs': 'https://www.cisa.gov/resources-tools/resources/avoiding-social-engineering-and-phishing-attacks'
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