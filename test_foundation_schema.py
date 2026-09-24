"""Focused fresh-install tests for the three-role database foundation."""

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from database import db
from database import operations
from utils.helpers import format_lifecycle_status


class FoundationSchemaTests(unittest.TestCase):
    db_path = "foundation-schema-test.db"

    @classmethod
    def setUpClass(cls):
        cls.original_path = db.DB_PATH
        db.DB_PATH = cls.db_path

    def setUp(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        db.init_db()

    @classmethod
    def tearDownClass(cls):
        db.DB_PATH = cls.original_path
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)

    def test_roles_profiles_case_lifecycle_and_audit(self):
        administrator_id = db.add_user("admin", "hash")
        db.update_user_identity("admin", "Admin User", "Operations Manager")
        investigator_id = db.add_user(
            "invest", "hash", created_by_username="admin", role="investigator", display_name="I. Vest"
        )
        operations.upsert_investigator_profile(
            investigator_id, completion_status="complete", credentials="CII"
        )
        profile = operations.get_investigator_profile(investigator_id)
        self.assertEqual(profile["completion_status"], "complete")

        with db.get_connection() as conn:
            client_id = conn.execute("INSERT INTO clients (name) VALUES (?)", ("Client",)).lastrowid
            case_id = conn.execute(
                "INSERT INTO cases (case_ref, case_name, client_id) VALUES (?, ?, ?)",
                ("REF-1", "Case", client_id),
            ).lastrowid
            conn.commit()
        operations.assign_case_lead_investigator(case_id, investigator_id, actor_user_id=administrator_id)
        self.assertEqual(
            operations.create_assigned_case(
                "REF-2", "Self assigned", client_id, actor_user_id=investigator_id
            ),
            case_id + 1,
        )
        self.assertEqual(len(operations.get_cases_with_workflow("invest", "investigator")), 2)
        self.assertEqual(len(operations.get_cases_with_workflow("admin", "administrator")), 2)
        operations.transition_case_lifecycle(case_id, "in_progress", actor_user_id=investigator_id)
        report_version_id = operations.create_report_version(
            case_id, 1, actor_user_id=administrator_id, status="final", content_hash="a" * 64,
            storage_reference="reports/REF-1_v0001_final.pdf", case_start_date="2026-01-01",
            approval_data={"approved_by": "A. Approver", "approved_at": "2026-01-31"},
        )
        with db.get_connection() as conn:
            case = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
            self.assertEqual(case["lifecycle_status"], "in_progress")
            self.assertIsNotNone(case["investigation_started_at"])
            self.assertEqual(case["investigation_started_by_user_id"], investigator_id)
            self.assertGreater(conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0], 0)
        report_version = operations.get_report_versions(case_id)[0]
        self.assertEqual(report_version["status"], "final")
        self.assertEqual(report_version["approved_by"], "A. Approver")
        self.assertEqual(report_version["review_status"], "approved")

        def reserve_draft(_):
            return operations.reserve_report_version(case_id, status="draft", actor_user_id=investigator_id)

        with ThreadPoolExecutor(max_workers=4) as executor:
            reservations = list(executor.map(reserve_draft, range(4)))
        self.assertEqual(len({item["version_number"] for item in reservations}), 4)
        self.assertEqual(len({item["storage_safe_token"] for item in reservations}), 4)
        draft = operations.finalize_report_version_reservation(
            reservations[0]["reservation_id"], actor_user_id=investigator_id, content_hash="b" * 64,
            storage_reference="reports/reserved-draft.pdf",
        )
        operations.submit_report_version(draft["id"], actor_user_id=investigator_id)
        claimed = operations.claim_report_review(
            draft["id"], manager_user_id=administrator_id
        )
        self.assertEqual(claimed["assigned_manager_user_id"], administrator_id)
        self.assertEqual(claimed["response_required_by_user_id"], administrator_id)
        operations.add_report_review_message(
            draft["id"], sender_user_id=administrator_id, message="Please confirm the source."
        )
        awaiting_investigator = next(
            version for version in operations.get_report_versions(case_id)
            if version["id"] == draft["id"]
        )
        self.assertEqual(awaiting_investigator["response_required_by_user_id"], investigator_id)
        operations.add_report_review_message(
            draft["id"], sender_user_id=investigator_id, message="Source confirmed."
        )
        self.assertEqual(
            next(
                version for version in operations.get_report_versions(case_id)
                if version["id"] == draft["id"]
            )["response_required_by_user_id"],
            administrator_id,
        )
        self.assertEqual(len(operations.get_report_review_messages(draft["id"])), 2)
        reviewed = operations.review_report_version(
            draft["id"], "approve", reviewer_user_id=administrator_id, reviewer_notes="Looks good"
        )
        self.assertEqual(reviewed["review_status"], "approved")
        for reservation in reservations[1:]:
            operations.abandon_report_version_reservation(
                reservation["reservation_id"], actor_user_id=investigator_id
            )
        self.assertGreaterEqual(len(operations.get_audit_events(10)), 3)
        self.assertIn(report_version_id, [row["id"] for row in operations.get_case_report_versions(case_id)])
        activity = operations.get_management_activity(
            date.today().isoformat(), actor_username="admin", actor_role="administrator"
        )
        self.assertEqual(len(activity), 2)
        rolling_activity = operations.get_management_activity_range(
            "2000-01-01", "2100-01-01", actor_username="admin", actor_role="administrator"
        )
        self.assertEqual(len(rolling_activity), 2)
        lifecycle_metrics = operations.get_management_lifecycle_metrics(
            "2000-01-01", "2100-01-01", actor_username="admin", actor_role="administrator"
        )
        self.assertEqual(lifecycle_metrics["in_progress"], 1)
        monthly_activity = operations.get_management_lifecycle_activity_by_month(
            "2000-01-01", "2100-01-01", actor_username="admin", actor_role="administrator"
        )
        self.assertEqual(monthly_activity[date.today().strftime("%Y-%m")]["in_progress"], 1)
        annual = operations.get_annual_management_summary(
            date.today().year, actor_username="admin", actor_role="administrator"
        )
        self.assertEqual(annual[0], {"metric_name": "cases_total", "metric_value": 2})

    def test_investigator_directory_tracks_profile_completion_and_account_status(self):
        db.add_user("admin", "hash")
        investigator_id = db.add_user(
            "invest", "hash", created_by_username="admin", role="investigator",
            display_name="I. Vest", title="Investigator",
        )

        operations.upsert_investigator_profile(
            investigator_id,
            completion_status="incomplete",
            credentials="CII",
            professional_bio="Professional biography",
        )
        self.assertEqual(operations.get_investigators(), [])

        operations.upsert_investigator_profile(
            investigator_id,
            completion_status="complete",
            credentials="CII",
            professional_bio="Professional biography",
        )
        self.assertEqual(
            operations.get_investigators(),
            [{
                "id": 1,
                "user_id": investigator_id,
                "name": "I. Vest",
                "title": "Investigator",
                "credentials": "CII",
                "bio": "Professional biography",
            }],
        )

        with db.get_connection() as conn:
            client_id = conn.execute("INSERT INTO clients (name) VALUES (?)", ("Client",)).lastrowid
            case_id = conn.execute(
                "INSERT INTO cases (case_ref, case_name, client_id) VALUES (?, ?, ?)",
                ("REF-DIRECTORY", "Directory Case", client_id),
            ).lastrowid
            conn.commit()
        operations.assign_case_lead_investigator(
            case_id, investigator_id, actor_user_id=1
        )
        workflow_case = next(
            case
            for case in operations.get_cases_with_workflow("admin", "administrator")
            if case["id"] == case_id
        )
        self.assertEqual(workflow_case["investigator_name"], "I. Vest")
        self.assertEqual(workflow_case["investigator_description"], "Professional biography")
        with db.get_connection() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT lead_investigator_id FROM cases WHERE id = ?", (case_id,)
                ).fetchone()["lead_investigator_id"],
                investigator_id,
            )
        operations.assign_case_lead_investigator(case_id, None, actor_user_id=1)
        with db.get_connection() as conn:
            self.assertIsNone(
                conn.execute(
                    "SELECT lead_investigator_id FROM cases WHERE id = ?", (case_id,)
                ).fetchone()["lead_investigator_id"]
            )

        db.set_user_active("invest", False)
        self.assertEqual(operations.get_investigators(), [])
        db.set_user_active("invest", True)
        self.assertEqual(len(operations.get_investigators()), 1)

    def test_lifecycle_status_labels_are_user_facing(self):
        self.assertEqual(format_lifecycle_status("in_progress"), "In Progress")
        self.assertEqual(format_lifecycle_status("submitted"), "Submitted")
        self.assertEqual(format_lifecycle_status(None), "Unknown")

    def test_investigator_can_accept_feedback_for_assigned_report(self):
        administrator_id = db.add_user("admin", "hash")
        manager_id = db.add_user(
            "manager", "hash", created_by_username="admin", role="manager"
        )
        investigator_id = db.add_user(
            "invest", "hash", created_by_username="admin", role="investigator"
        )
        operations.upsert_investigator_profile(
            investigator_id, completion_status="complete", credentials="CII"
        )
        with db.get_connection() as conn:
            client_id = conn.execute("INSERT INTO clients (name) VALUES (?)", ("Client",)).lastrowid
            case_id = conn.execute(
                "INSERT INTO cases (case_ref, case_name, client_id) VALUES (?, ?, ?)",
                ("REF-FEEDBACK", "Feedback Case", client_id),
            ).lastrowid
            conn.commit()
        operations.assign_case_lead_investigator(
            case_id, investigator_id, actor_user_id=administrator_id
        )
        report_id = operations.create_report_version(
            case_id, 1, actor_user_id=investigator_id, content_hash="a" * 64
        )
        operations.submit_report_version(report_id, actor_user_id=investigator_id)
        operations.claim_report_review(report_id, manager_user_id=manager_id)
        operations.add_report_review_message(
            report_id, sender_user_id=manager_id, message="Please revise this finding."
        )

        returned = operations.accept_report_feedback(
            report_id, investigator_user_id=investigator_id
        )

        self.assertEqual(returned["review_status"], "rejected")
        self.assertIsNone(returned["response_required_by_user_id"])
        self.assertEqual(
            returned["rejection_reason"], "Feedback accepted by investigator."
        )

    def test_subjects_include_bidirectional_link_counts(self):
        db.add_user("admin", "hash")
        with db.get_connection() as conn:
            client_id = conn.execute("INSERT INTO clients (name) VALUES (?)", ("Client",)).lastrowid
            case_id = conn.execute(
                "INSERT INTO cases (case_ref, case_name, client_id) VALUES (?, ?, ?)",
                ("REF-SUBJECTS", "Subject Case", client_id),
            ).lastrowid
            conn.commit()

        operations.add_case_subject(
            case_id, "Individual", "Principal Subject", "Alex Principal", {}
        )
        operations.add_case_subject(
            case_id, "Organisation", "Alex Principal", "Example Organisation", {}
        )
        operations.add_case_subject(
            case_id, "Individual", "Principal Subject", "Unrelated Subject", {}
        )

        counts = {
            subject["display_name"]: subject["linked_subject_count"]
            for subject in operations.get_case_subjects(case_id)
        }
        self.assertEqual(counts["Alex Principal"], 1)
        self.assertEqual(counts["Example Organisation"], 1)
        self.assertEqual(counts["Unrelated Subject"], 0)

    def test_risk_revision_rejects_stale_write(self):
        administrator_id = db.add_user("owner", "hash")
        operations.add_risk_library_item("Category", "Risk", "High", actor_user_id=administrator_id)
        with db.get_connection() as conn:
            risk_id, revision = conn.execute("SELECT id, revision FROM risk_library").fetchone()
        operations.update_risk_library_item(
            risk_id, "Category", "Risk", "High", "", "", "High Confidence", "",
            expected_revision=revision, actor_user_id=administrator_id,
        )
        with self.assertRaises(ValueError):
            operations.update_risk_library_item(
                risk_id, "Category", "Risk", "High", "", "", "High Confidence", "",
                expected_revision=revision, actor_user_id=administrator_id,
            )
        operations.retire_risk_library_item(risk_id, "owner")
        self.assertEqual(len(operations.get_risk_library_entries()), 0)
        self.assertEqual(len(operations.get_risk_library_entries(include_retired=True)), 1)
        operations.restore_risk_library_item(risk_id, "owner")
        self.assertEqual(len(operations.get_risk_library_entries()), 1)

    def test_persona_references_are_permanent_and_case_unique(self):
        administrator_id = db.add_user("admin", "hash")
        with db.get_connection() as conn:
            client_id = conn.execute("INSERT INTO clients (name) VALUES (?)", ("Client",)).lastrowid
            case_id = conn.execute(
                "INSERT INTO cases (case_ref, case_name, client_id) VALUES (?, ?, ?)",
                ("REF-PERSONA", "Persona Case", client_id),
            ).lastrowid
            conn.commit()

        allocated = operations.add_case_persona_references(
            case_id,
            ["persona-alpha", "PERSONA-BRAVO"],
        )
        self.assertEqual(
            [row["persona_reference"] for row in allocated],
            ["PERSONA-ALPHA", "PERSONA-BRAVO"],
        )
        with self.assertRaisesRegex(ValueError, "PERSONA-ALPHA"):
            operations.add_case_persona_references(case_id, ["persona-alpha"])

        usage = operations.get_persona_reference_usage(date.today().year)
        self.assertEqual(
            {row["persona_reference"] for row in usage},
            {"PERSONA-ALPHA", "PERSONA-BRAVO"},
        )
        self.assertEqual(
            operations.get_management_report_years(
                actor_username="admin",
                actor_role="administrator",
            ),
            [date.today().year],
        )

    def test_lifecycle_dates_are_set_once_at_their_workflow_milestones(self):
        administrator_id = db.add_user("admin", "hash")
        with db.get_connection() as conn:
            client_id = conn.execute("INSERT INTO clients (name) VALUES (?)", ("Client",)).lastrowid
            case_id = conn.execute(
                "INSERT INTO cases (case_ref, case_name, client_id) VALUES (?, ?, ?)",
                ("REF-DATES", "Date Case", client_id),
            ).lastrowid
            conn.commit()

        with db.get_connection() as conn:
            expected_start_date = conn.execute("SELECT DATE('now')").fetchone()[0]
        operations.transition_case_lifecycle(case_id, "in_progress", actor_user_id=administrator_id)
        with db.get_connection() as conn:
            first_start_date = conn.execute(
                "SELECT start_date FROM cases WHERE id = ?",
                (case_id,),
            ).fetchone()["start_date"]
        self.assertEqual(first_start_date, expected_start_date)

        with db.get_connection() as conn:
            expected_end_date = conn.execute("SELECT DATE('now')").fetchone()[0]
        operations.transition_case_lifecycle(case_id, "submitted", actor_user_id=administrator_id)
        with db.get_connection() as conn:
            first_end_date = conn.execute(
                "SELECT end_date FROM cases WHERE id = ?",
                (case_id,),
            ).fetchone()["end_date"]
        self.assertEqual(first_end_date, expected_end_date)

        operations.transition_case_lifecycle(case_id, "rejected", actor_user_id=administrator_id)
        operations.transition_case_lifecycle(case_id, "in_progress", actor_user_id=administrator_id)
        operations.transition_case_lifecycle(case_id, "submitted", actor_user_id=administrator_id)
        with db.get_connection() as conn:
            expected_report_date = conn.execute("SELECT DATE('now')").fetchone()[0]
        operations.transition_case_lifecycle(case_id, "completed", actor_user_id=administrator_id)
        with db.get_connection() as conn:
            case = conn.execute(
                "SELECT start_date, end_date, report_date FROM cases WHERE id = ?",
                (case_id,),
            ).fetchone()
        self.assertEqual(case["start_date"], first_start_date)
        self.assertEqual(case["end_date"], first_end_date)
        self.assertEqual(case["report_date"], expected_report_date)

    def test_management_report_configurations_are_private_and_validated(self):
        administrator_id = db.add_user("admin", "hash")
        manager_id = db.add_user(
            "manager", "hash", created_by_username="admin", role="manager"
        )
        other_manager_id = db.add_user(
            "othermanager", "hash", created_by_username="admin", role="manager"
        )
        configuration = {
            "preset": "month",
            "scope": "team",
            "investigator_id": None,
            "complexity_mode": "totals",
            "sections": ["throughput", "workload"],
        }
        saved = operations.save_management_report_configuration(
            manager_id,
            "Monthly workload",
            configuration,
            actor_username="manager",
            actor_role="manager",
        )
        self.assertEqual(
            [item["name"] for item in operations.list_management_report_configurations(
                manager_id, actor_username="manager", actor_role="manager"
            )],
            ["Monthly workload"],
        )
        self.assertEqual(
            operations.list_management_report_configurations(
                other_manager_id, actor_username="othermanager", actor_role="manager"
            ),
            [],
        )
        with self.assertRaisesRegex(ValueError, "not found"):
            operations.delete_management_report_configuration(
                other_manager_id,
                saved["id"],
                actor_username="othermanager",
                actor_role="manager",
            )
        with self.assertRaisesRegex(ValueError, "invalid timeframe"):
            operations.save_management_report_configuration(
                manager_id,
                "Invalid",
                {**configuration, "preset": "decade"},
                actor_username="manager",
                actor_role="manager",
            )


if __name__ == "__main__":
    unittest.main()
