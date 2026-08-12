# Template Cleanup Plan

## Keep

- [report_template.md](/drive/kairos-report-engine/templates/report_template.md)
- [attestation_template.md](/drive/kairos-report-engine/templates/attestation_template.md)
- DB-backed fields already aligned in [database/operations.py](/drive/kairos-report-engine/database/operations.py)

## Remove or Simplify Now

- Specialized corporate/person/infrastructure-only blocks in:
  - [report_template_Corporate_Due_Diligence.md](/drive/kairos-report-engine/templates/report_template_Corporate_Due_Diligence.md)
  - [report_template_Person_Profile.md](/drive/kairos-report-engine/templates/report_template_Person_Profile.md)
  - [report_template_Infrastructure.md](/drive/kairos-report-engine/templates/report_template_Infrastructure.md)
- Any section that depends on fields not currently in the DB and not computed by the generator

## Later

- Add "targets" into the workflow
- Reintroduce richer template sections around target data
- If needed, generate those report sections from a dedicated target model instead of the current case record

## Suggested Testing Focus

- Create a case
- Add a finding
- Generate report
- Generate attestation
- Compare output quality before simplifying templates further
