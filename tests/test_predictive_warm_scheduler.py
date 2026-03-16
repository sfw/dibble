from uuid import uuid4

from dibble.models.curriculum import CurriculumResourceUpsert
from dibble.models.generation import GenerationRequest
from dibble.services.adaptive_router import AdaptiveRouter
from dibble.services.content_validator import ContentValidator
from dibble.services.content_warmer import ContentWarmer
from dibble.services.curriculum_store import SQLiteCurriculumStore
from dibble.services.generation_engine import GenerationEngine
from dibble.services.llm_provider import MockLLMProvider
from dibble.services.predictive_content_warming import PredictiveWarmPlan
from dibble.services.predictive_warm_queue_store import SQLitePredictiveWarmQueueStore
from dibble.services.predictive_warm_scheduler import PredictiveWarmScheduler
from dibble.services.profile_store import SQLiteProfileStore
from dibble.services.rag_retriever import RAGRetriever
from dibble.storage import ensure_database
from tests.support import build_curriculum_resource, build_profile


def test_predictive_warm_scheduler_processes_enqueued_tasks(tmp_path):
    database_path = str(tmp_path / "predictive-warm-scheduler.db")
    ensure_database(database_path)
    profile_store = SQLiteProfileStore(database_path)
    curriculum_store = SQLiteCurriculumStore(database_path)
    queue_store = SQLitePredictiveWarmQueueStore(database_path)
    student_id = uuid4()
    profile_store.upsert(build_profile_model(student_id))
    curriculum_store.upsert(CurriculumResourceUpsert.model_validate(build_curriculum_resource()))
    generation_engine = GenerationEngine(
        retriever=RAGRetriever(curriculum_store),
        router=AdaptiveRouter(),
        provider=MockLLMProvider(),
        validator=ContentValidator(),
    )
    scheduler = PredictiveWarmScheduler(
        queue_store=queue_store,
        content_warmer=ContentWarmer(
            profile_store=profile_store,
            generation_engine=generation_engine,
            generation_mode_calibrator=None,
        ),
        inline_process_limit=2,
    )
    request = GenerationRequest.model_validate(
        {
            "student_id": str(student_id),
            "learning_session_id": "session-1",
            "target_kc_ids": ["KC-1"],
            "intent": "practice",
            "requested_content_type": "practice_problem",
            "curriculum_context": ["Equivalent fractions"],
            "predictive_warm": True,
            "warm_reason": "test",
            "source_generation_id": "gen-1",
        }
    )

    enqueue_result = scheduler.enqueue_plan(
        plan=PredictiveWarmPlan(
            requests=[request],
            content_types=["practice_problem"],
            reasons=["test"],
        )
    )
    process_result = scheduler.process_inline(task_ids=enqueue_result.task_ids or [])

    assert enqueue_result.enqueued_count == 1
    assert process_result.completed_tasks == 1
    assert process_result.cache_misses == 1
    assert process_result.pending_tasks == 0
    assert queue_store.stats()["completed"] == 1


def build_profile_model(student_id):
    from dibble.models.profile import LearnerProfile

    return LearnerProfile.model_validate(build_profile(student_id))
