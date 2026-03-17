from uuid import uuid4

from dibble.models.profile import LearnerContinueAction, LearnerFlowNextStep, LearnerFlowSummary
from dibble.services.audit_store import SQLiteAuditStore
from dibble.services.teacher_intervention_actions import TeacherInterventionActionService
from dibble.storage import ensure_database


class StubLearnerFlowService:
    def __init__(self, flow: LearnerFlowSummary) -> None:
        self.flow = flow

    def build_for_student(self, *, student_id):
        return self.flow


def test_teacher_intervention_labels_follow_repair_stage_for_lesson_options(tmp_path):
    database_path = str(tmp_path / "teacher-intervention-repair.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = uuid4()
    flow = LearnerFlowSummary(
        status="active",
        flow_type="lesson",
        learning_session_id="lesson-repair",
        current_phase="repair",
        progression_action="hold_repair_target",
        target_stage="repair",
        active_target_kc_ids=["KC-1"],
        rationale="Keep working on the repair target.",
        next_step=LearnerFlowNextStep(
            action="hold_repair_target",
            content_type="micro_explanation",
            target_stage="repair",
            target_kc_ids=["KC-1"],
            rationale="Re-explain the repaired move.",
        ),
        continue_action=LearnerContinueAction.generate_follow_up(
            generation_id="gen-repair",
            learning_session_id="lesson-repair",
            content_type="micro_explanation",
            target_stage="repair",
            target_kc_ids=["KC-1"],
            request_payload={"student_id": str(student_id), "target_kc_ids": ["KC-1"]},
            rationale="Re-explain the repaired move.",
        ),
    )
    service = TeacherInterventionActionService(
        audit_store=audit_store,
        learner_flow_service=StubLearnerFlowService(flow),
    )

    contract = service.build_for_student(student_id=student_id)
    labels = {option.option_id: option.label for option in contract.available_options}
    rationales = {option.option_id: option.rationale for option in contract.available_options}

    assert labels["recommended"] == "Repair Explanation"
    assert labels["worked_example_support_reset"] == "Repair Worked Example"
    assert labels["practice_problem_same_target"] == "Repair Practice"
    assert (
        rationales["worked_example_support_reset"]
        == "Keep working on the repair target. Alternative: Offer a more supported worked example on the repair target before returning to the requested target."
    )
    assert (
        rationales["practice_problem_same_target"]
        == "Keep working on the repair target. Alternative: Stay on the repair target with another practice step before returning to the requested target."
    )


def test_teacher_intervention_labels_follow_transfer_stage_for_lesson_options(tmp_path):
    database_path = str(tmp_path / "teacher-intervention-transfer.db")
    ensure_database(database_path)
    audit_store = SQLiteAuditStore(database_path)
    student_id = uuid4()
    flow = LearnerFlowSummary(
        status="active",
        flow_type="lesson",
        learning_session_id="lesson-transfer",
        current_phase="transfer",
        progression_action="attempt_transfer",
        target_stage="transfer",
        active_target_kc_ids=["KC-2"],
        transfer_target_kc_ids=["KC-2"],
        rationale="Test whether the learner can transfer independently.",
        next_step=LearnerFlowNextStep(
            action="attempt_transfer",
            content_type="worked_example",
            target_stage="transfer",
            target_kc_ids=["KC-2"],
            rationale="Fade support before the transfer check.",
        ),
        continue_action=LearnerContinueAction.generate_follow_up(
            generation_id="gen-transfer",
            learning_session_id="lesson-transfer",
            content_type="worked_example",
            target_stage="transfer",
            target_kc_ids=["KC-2"],
            request_payload={"student_id": str(student_id), "target_kc_ids": ["KC-2"]},
            rationale="Fade support before the transfer check.",
        ),
    )
    service = TeacherInterventionActionService(
        audit_store=audit_store,
        learner_flow_service=StubLearnerFlowService(flow),
    )

    contract = service.build_for_student(student_id=student_id)
    labels = {option.option_id: option.label for option in contract.available_options}
    rationales = {option.option_id: option.rationale for option in contract.available_options}

    assert labels["recommended"] == "Transfer Worked Example"
    assert labels["practice_problem_same_target"] == "Transfer Practice"
    assert labels["assessment_probe_transfer_check"] == "Transfer Check"
    assert (
        rationales["practice_problem_same_target"]
        == "Test whether the learner can transfer independently. Alternative: Stay on the transfer target with one more practice step before assigning a transfer check."
    )
    assert (
        rationales["assessment_probe_transfer_check"]
        == "Test whether the learner can transfer independently. Alternative: Verify transfer explicitly on the current target before assigning more independent work."
    )
