export type SignalLevel = 'none' | 'low' | 'medium' | 'high'
export type ContinueActionKind = 'idle' | 'generate_follow_up' | 'advance_remediation' | 'continue_socratic'
export type ContinueActionMethod = 'POST'
export type TeacherInterventionProposalStatus = 'unavailable' | 'available'
export type TeacherInterventionDecision = 'approve' | 'select_option' | 'defer' | 'escalate_human'
export type TeacherInterventionDecisionStatus =
  | 'approved'
  | 'option_selected'
  | 'deferred'
  | 'escalated_human'

export interface LearnerFlowNextStep {
  action: string
  content_type?: string | null
  target_stage: string
  target_kc_ids: string[]
  rationale?: string | null
}

export interface LearnerContinueAction {
  kind: ContinueActionKind
  display_label?: string | null
  method?: ContinueActionMethod | null
  endpoint?: string | null
  outcome_id?: string | null
  generation_id?: string | null
  learning_session_id?: string | null
  content_type?: string | null
  target_stage: string
  target_kc_ids: string[]
  request_payload: Record<string, unknown>
  rationale?: string | null
}

export interface LearnerCalibrationSummary {
  signal: string
  source: string
  average_run_outcome_score?: number | null
  confidence: number
  matched_run_count: number
  matched_session_count: number
  intent?: string | null
  content_type?: string | null
  target_kc_ids: string[]
  target_lo_ids: string[]
  updated_at?: string | null
}

export interface LearnerProgressSummary {
  signal: string
  source: string
  average_run_outcome_score?: number | null
  confidence: number
  matched_run_count: number
  matched_session_count: number
  positive_run_rate: number
  negative_run_rate: number
  recent_average_run_outcome_score?: number | null
  prior_average_run_outcome_score?: number | null
  progress_delta: number
  updated_at?: string | null
}

export interface LearnerStrategySummary {
  signal: string
  source: string
  support_bias: number
  recovery_focus: string
  trajectory_state: string
  recommended_next_action: string
  confidence: number
  average_run_outcome_score?: number | null
  matched_run_count: number
  matched_session_count: number
  progress_signal: string
  progress_delta: number
  volatility_index: number
  relapse_risk: number
  rationale?: string | null
  updated_at?: string | null
}

export interface CognitiveTraitScore {
  value: number
  confidence: number
  assessed_at?: string
}

export interface LearnerStateProfileSummary {
  signal: string
  source: string
  confidence: number
  average_run_outcome_score?: number | null
  matched_run_count: number
  matched_session_count: number
  progress_signal: string
  progress_delta: number
  strategy_signal: string
  strategy_trajectory_state: string
  engagement: SignalLevel
  frustration: SignalLevel
  total_load: number
  confidence_calibration: number
  help_seeking: SignalLevel
  self_monitoring: number
  affective_reliability: number
  load_reliability: number
  recovery_stability: number
  overload_risk: number
  metacognitive_reliability: number
  rationale?: string | null
  updated_at?: string | null
}

export interface LearnerTraitProfileSummary {
  signal: string
  source: string
  matched_observation_count: number
  matched_session_count: number
  processing_speed?: CognitiveTraitScore | null
  working_memory?: CognitiveTraitScore | null
  spatial_reasoning?: CognitiveTraitScore | null
  processing_speed_reliability: number
  working_memory_reliability: number
  spatial_reasoning_reliability: number
  trait_stability: number
  challenge_tolerance: number
  challenge_evidence_strength: number
  rationale?: string | null
  updated_at?: string | null
}

export interface RecentLearnerActivity {
  generation_count: number
  observation_count: number
  socratic_assessment_count: number
  last_learning_session_id?: string | null
  last_generation_id?: string | null
  last_event_at?: string | null
}

export interface LearnerFlowSummary {
  status: string
  flow_type: string
  learning_session_id?: string | null
  remediation_session_id?: string | null
  socratic_session_id?: string | null
  current_phase: string
  current_content_type?: string | null
  last_generation_id?: string | null
  progression_action: string
  target_stage: string
  active_target_kc_ids: string[]
  deferred_target_kc_ids: string[]
  transfer_target_kc_ids: string[]
  session_phase: string
  session_arc_action: string
  session_stuck_loop_risk: string
  rationale?: string | null
  progression_source: string
  next_step_source: string
  next_step: LearnerFlowNextStep
  continue_action: LearnerContinueAction
  updated_at?: string | null
}

export interface OutcomeProgressSummary {
  outcome_id: string
  title: string
  state: string
  knowledge_component_ids: string[]
  blocked_prerequisite_kc_ids: string[]
  mastery_ratio: number
  current_flow_aligned: boolean
  target_stage: string
  mastery_quality?: string | null
  rationale?: string | null
}

export interface LearnerCurriculumProgressionSummary {
  status: string
  source: string
  flow_type: string
  current_stage: string
  stage_display_label?: string | null
  progression_action: string
  active_target_kc_ids: string[]
  outcome_count: number
  mastered_outcome_count: number
  ready_outcome_count: number
  blocked_outcome_count: number
  active_outcome_count: number
  mastered_outcome_ratio: number
  current_outcome?: OutcomeProgressSummary | null
  next_outcome?: OutcomeProgressSummary | null
  blocked_outcomes: OutcomeProgressSummary[]
  ready_outcomes: OutcomeProgressSummary[]
  rationale?: string | null
  updated_at?: string | null
}

export interface Strand {
  strand_id: string
  course_id: string
  parent_strand_id?: string | null
  title: string
  description: string
  sort_order: number
  tags: string[]
  updated_at: string
}

export interface Outcome {
  outcome_id: string
  title: string
  strand_id: string
  grade_level: string
  subject: string
  description: string
  knowledge_component_ids: string[]
  tags: string[]
  sort_order: number
  updated_at: string
}

export interface KnowledgeComponent {
  kc_id: string
  name: string
  outcome_id: string
  grade_level: string
  subject: string
  taxonomy_cluster_id?: string | null
  concept_family?: string | null
  prerequisite_kc_ids: string[]
  nearby_kc_ids: string[]
  difficulty: number
  estimated_time_minutes: number
  tags: string[]
  common_misconceptions: string[]
  updated_at: string
}

export interface ClassificationReliabilitySummary {
  classification: string
  evaluated_count: number
  accuracy_rate: number
}

export interface StatePredictionReliabilitySummary {
  evaluated_count: number
  overall_accuracy: number
  weighted_accuracy: number
  weakest_classification?: string | null
  strongest_classification?: string | null
  per_classification: ClassificationReliabilitySummary[]
  rationale: string
}

export interface SignalDivergenceSummary {
  signal_a: string
  signal_b: string
  severity: string
  description: string
}

export interface CrossSignalConsistencySummary {
  divergence_count: number
  coherence_score: number
  high_count: number
  medium_count: number
  low_count: number
  divergences: SignalDivergenceSummary[]
  rationale: string
}

export interface ProfileSummary {
  student_id: string
  grade_level: string
  profile_version: string
  kc_count: number
  lo_count: number
  engagement: SignalLevel
  frustration: SignalLevel
  total_load: number
  confidence_calibration: number
  help_seeking: SignalLevel
  calibration: LearnerCalibrationSummary
  progress: LearnerProgressSummary
  strategy: LearnerStrategySummary
  state_profile: LearnerStateProfileSummary
  trait_profile: LearnerTraitProfileSummary
  state_prediction_reliability: StatePredictionReliabilitySummary
  signal_consistency: CrossSignalConsistencySummary
  recent_activity: RecentLearnerActivity
  current_flow: LearnerFlowSummary
  curriculum_progression: LearnerCurriculumProgressionSummary
  updated_at: string
}

export interface ProfileMetadata {
  student_id: string
  version: string
  last_updated: string
  completeness_score: number
}

export interface KnowledgeState {
  lo_mastery: Record<string, number>
  kc_mastery: Record<string, number>
  last_updated?: string
}

export interface LearningPreferences {
  modality_affinity: Record<string, number>
  example_domain_preferences: string[]
  scaffolding_preference: string
  pace_preference: string
}

export interface LearnerProfileV2 {
  profile_metadata: ProfileMetadata
  cognitive_traits: Record<string, CognitiveTraitScore>
  knowledge_state: KnowledgeState
  affective_state: {
    engagement: SignalLevel
    frustration: SignalLevel
    confusion: SignalLevel
    confidence: number
    inferred_at?: string
  }
  cognitive_load: {
    intrinsic_load: number
    extraneous_load: number
    germane_load: number
    total_load: number
    capacity_utilization: number
    inferred_at?: string
  }
  metacognitive_state: {
    confidence_calibration: number
    help_seeking: SignalLevel
    help_seeking_effectiveness: number
    self_monitoring: number
    inferred_at?: string
  }
  learning_preferences: LearningPreferences
  accommodations: string[]
}

export interface AdaptiveRouteDecision {
  intervention_type: string
  delivery_mode: string
  scaffolding_level: string
  reasons: string[]
  calibration?: {
    signal: string
    source: string
    confidence: number
    average_run_outcome_score?: number | null
    matched_run_count: number
    positive_run_rate: number
    negative_run_rate: number
    progress_signal: string
    progress_delta: number
  } | null
}

export interface GroundingReference {
  resource_id: string
  title: string
  grade_level: string
  subject?: string | null
  source_type?: string | null
  score: number
  matched_terms: string[]
  excerpt?: string | null
}

export interface GeneratedBlock {
  kind: string
  title: string
  body: string
}

export interface GenerationMetadata {
  quality_score: number
  validation_passed: boolean
  validation_issue_count: number
  grounding_count: number
  provider_name?: string | null
  model_used?: string | null
  prompt_template_name?: string | null
  prompt_template_version?: string | null
  prompt_template_variant?: string | null
  generation_latency_ms: number
  cache_hit: boolean
  moderation: {
    status: string
    stage: string
    severity: string
    decision: string
    categories: string[]
    reasons: string[]
    matched_terms: string[]
    blocked: boolean
    request_blocked: boolean
    response_rewritten: boolean
    fallback_applied: boolean
    fallback_kind?: string | null
    stream_action: string
    provider_invoked: boolean
    stream_buffered: boolean
    original_block_count: number
    replacement_block_count: number
    audit_message?: string | null
  }
}

export interface GenerationWorkflowSummary {
  status: string
  flow_type: string
  learning_session_id?: string | null
  delivered_phase: string
  delivered_content_type?: string | null
  progression_action: string
  target_stage: string
  active_target_kc_ids: string[]
  rationale?: string | null
  next_step: LearnerFlowNextStep
  continue_action: LearnerContinueAction
}

export interface GeneratedContent {
  generation_id: string
  student_id: string
  content_type: string
  request_context: Record<string, unknown>
  workflow_summary?: GenerationWorkflowSummary | null
  response: {
    student_id: string
    generated_at: string
    route: AdaptiveRouteDecision
    blocks: GeneratedBlock[]
    curriculum_context: string[]
    grounding: GroundingReference[]
    safety_notes: string[]
    validation_issues: string[]
    generation_id?: string | null
    generation_metadata?: GenerationMetadata | null
  }
  quality: GenerationMetadata
  created_at: string
  expires_at?: string | null
}

export interface GenerationRequestPayload {
  student_id: string
  learning_session_id?: string | null
  target_kc_ids: string[]
  target_lo_ids: string[]
  intent: string
  requested_content_type?: string | null
  learner_prompt?: string | null
  curriculum_context: string[]
}

export interface SocraticSessionSummary {
  status: string
  turn_count: number
  latest_prompt_style?: string | null
  latest_steering_action: string
  latest_next_action: string
  latest_evidence_strength: string
  latest_evidence_score: number
  rationale?: string | null
  next_step: LearnerFlowNextStep
  continue_action: LearnerContinueAction
  updated_at?: string | null
}

export interface SocraticAssessmentResponse {
  session_id: string
  student_id: string
  learning_session_id?: string | null
  turn_id: string
  prompt: string
  prompt_style: string
  steering_action: string
  policy_rationale: string
  evaluation: {
    evidence_strength: string
    evidence_score: number
    evidence_dimensions: Record<string, number>
    inferred_mastery: number
    matched_terms: string[]
    rationale: string
    next_action: string
  }
  route: AdaptiveRouteDecision
  grounding: GroundingReference[]
  generated_blocks: GeneratedBlock[]
  conversation_history: Array<{ role: string; text: string }>
  summary: SocraticSessionSummary
  generation_id?: string | null
  generation_metadata?: GenerationMetadata | null
  created_at: string
}

export interface SocraticAssessmentSession {
  session_id: string
  student_id: string
  learning_session_id?: string | null
  target_kc_ids: string[]
  target_lo_ids: string[]
  curriculum_context: string[]
  conversation_history: Array<{ role: string; text: string }>
  turns: Array<{
    turn_id: string
    prompt: string
    prompt_style: string
    steering_action: string
    policy_rationale: string
    learner_response?: string | null
    evaluation: SocraticAssessmentResponse['evaluation']
    created_at: string
  }>
  summary: SocraticSessionSummary
  created_at: string
  updated_at: string
}

export interface RemediationWorkflowStep {
  phase: string
  title: string
  target_kc_ids: string[]
  support_level: string
  objective: string
  guidance: string
  misconception_ids: string[]
  recommended_content_type: string
  status: string
  generated_content_id?: string | null
}

export interface RemediationWorkflowSummary {
  status: string
  current_phase?: string | null
  current_step_title?: string | null
  current_step_target_kc_ids: string[]
  next_phase?: string | null
  completed_step_count: number
  step_count: number
  progression_decision: string
  progression_rationale?: string | null
  progression_target_kc_ids: string[]
  progression_evidence_observation_count: number
  progression_evidence_confidence: number
  progression_average_observed_mastery?: number | null
  progression_low_support_success_count: number
  next_step: LearnerFlowNextStep
  continue_action: LearnerContinueAction
}

export interface KcSequenceSummary {
  action: string
  primary_kc_id?: string | null
  ordered_kc_ids: string[]
  bridge_kc_ids: string[]
  deferred_kc_ids: string[]
  rationale?: string | null
}

export interface RemediationWorkflowSession {
  session_id: string
  student_id: string
  target_kc_id: string
  focus_kc_ids: string[]
  prerequisite_kc_ids: string[]
  misconception_description: string
  curriculum_context: string[]
  rationale: string
  blueprint: Record<string, unknown>
  strategy_summary: LearnerStrategySummary
  kc_sequence: KcSequenceSummary
  steps: RemediationWorkflowStep[]
  current_step_index?: number | null
  completed_generation_ids: string[]
  progression_decision: string
  progression_rationale?: string | null
  progression_target_kc_ids: string[]
  progression_evidence_observation_count: number
  progression_evidence_confidence: number
  progression_average_observed_mastery?: number | null
  progression_low_support_success_count: number
  summary: RemediationWorkflowSummary
  created_at: string
  updated_at: string
}

export interface RemediationWorkflowAdvanceResponse {
  session: RemediationWorkflowSession
  content: GeneratedContent
  executed_phase: string
}

export interface GenerationStreamEvent {
  event: string
  route?: AdaptiveRouteDecision
  chunk?: {
    block_index: number
    kind: string
    title: string
    body_delta: string
    done: boolean
  }
  grounding?: GroundingReference[]
  moderation?: GenerationMetadata['moderation']
  validation_issues?: string[]
  response?: GeneratedContent['response']
}

export interface LearnerWorkspaceArtifact {
  kind: string
  resource_id?: string | null
  generation_id?: string | null
  learning_session_id?: string | null
  flow_type: string
  status: string
  current_phase: string
  content_type?: string | null
  rationale?: string | null
}

export interface AffectiveSupportMessage {
  kind: string
  title: string
  detail: string
}

export interface LearnerWorkspace {
  student_id: string
  summary: ProfileSummary
  active_artifact: LearnerWorkspaceArtifact
  continue_action: LearnerContinueAction
  affective_support?: AffectiveSupportMessage | null
  generated_content?: GeneratedContent | null
  remediation_session?: RemediationWorkflowSession | null
  socratic_session?: SocraticAssessmentSession | null
}

export interface LearnerGenerationHistoryEntry {
  generation_id: string
  learning_session_id?: string | null
  source_generation_id?: string | null
  content_type: string
  flow_type: string
  status: string
  delivered_phase: string
  progression_action: string
  target_stage: string
  active_target_kc_ids: string[]
  intervention_type?: string | null
  rationale?: string | null
  next_step: LearnerFlowNextStep
  continue_action: LearnerContinueAction
  created_at: string
}

export interface LearnerSocraticSessionHistoryEntry {
  session_id: string
  learning_session_id?: string | null
  target_kc_ids: string[]
  target_lo_ids: string[]
  status: string
  turn_count: number
  latest_prompt_style?: string | null
  latest_steering_action: string
  latest_next_action: string
  latest_evidence_strength: string
  rationale?: string | null
  next_step: LearnerFlowNextStep
  continue_action: LearnerContinueAction
  created_at: string
  updated_at: string
}

export interface LearnerRemediationSessionHistoryEntry {
  session_id: string
  target_kc_id: string
  focus_kc_ids: string[]
  prerequisite_kc_ids: string[]
  latest_generation_id?: string | null
  status: string
  current_phase?: string | null
  completed_step_count: number
  step_count: number
  progression_decision: string
  progression_rationale?: string | null
  next_step: LearnerFlowNextStep
  continue_action: LearnerContinueAction
  created_at: string
  updated_at: string
}

export interface TeacherInterventionOption {
  option_id: string
  label: string
  rationale?: string | null
  is_recommended: boolean
  continue_action: LearnerContinueAction
}

export interface TeacherInterventionDecisionRecord {
  action_key: string
  decision_id: string
  decision: TeacherInterventionDecision
  status: TeacherInterventionDecisionStatus
  selected_option_id?: string | null
  note?: string | null
  decided_by?: string | null
  decided_role?: string | null
  decided_at: string
  execution_action: LearnerContinueAction
}

export interface TeacherInterventionActionContract {
  action_key: string
  proposal_status: TeacherInterventionProposalStatus
  flow_type: string
  learning_session_id?: string | null
  remediation_session_id?: string | null
  socratic_session_id?: string | null
  progression_action: string
  target_stage: string
  active_target_kc_ids: string[]
  current_phase: string
  rationale?: string | null
  source: string
  next_step: LearnerFlowNextStep
  proposed_action: LearnerContinueAction
  available_options: TeacherInterventionOption[]
  allowed_decisions: TeacherInterventionDecision[]
  latest_decision?: TeacherInterventionDecisionRecord | null
  updated_at?: string | null
}

export interface TeacherInterventionDecisionRequest {
  decision: TeacherInterventionDecision
  option_id?: string | null
  note?: string | null
}

export interface TeacherLearnerInterventionSummary {
  action_key: string
  proposal_status: TeacherInterventionProposalStatus
  recommended_action_kind: ContinueActionKind
  option_count: number
  latest_decision_status?: TeacherInterventionDecisionStatus | null
}

export interface TeacherLearnerCard {
  student_id: string
  grade_level: string
  engagement: string
  frustration: string
  current_flow: LearnerFlowSummary
  curriculum_progression: LearnerCurriculumProgressionSummary
  recent_activity: RecentLearnerActivity
  intervention: TeacherLearnerInterventionSummary
  display_rationale?: string | null
  attention_level: string
  triage_section: string
  attention_reasons: string[]
}

export interface TeacherSectionOverview {
  section_id: string
  course_id?: string
  title: string
  teacher_label?: string | null
  grade_level?: string | null
  subject?: string | null
  learner_count: number
  active_flow_count: number
  intervention_available_count: number
  blocked_progression_count: number
  attention_needed_count: number
  missing_learner_count: number
  updated_at?: string | null
}

export interface TeacherSectionReadModel extends TeacherSectionOverview {
  missing_student_ids: string[]
  learners: TeacherLearnerCard[]
}

export interface TeacherContractGap {
  severity: 'P0' | 'P1' | 'P2'
  title: string
  why_it_matters: string
  current_backend: string
  frontend_response: string
}

export interface AuthIdentity {
  principal_id: string
  role: string
  auth_scheme: string
  learner_id?: string | null
  display_name?: string | null
}

export interface AuthToken {
  access_token: string
  refresh_token?: string | null
  token_type: string
  expires_in: number
  identity: AuthIdentity
}

export interface HistoryPage<T> {
  items: T[]
  offset: number
  limit: number
  has_more: boolean
}

export type LearnerGenerationHistoryPage = HistoryPage<LearnerGenerationHistoryEntry>
export type LearnerSocraticSessionHistoryPage = HistoryPage<LearnerSocraticSessionHistoryEntry>
export type LearnerRemediationSessionHistoryPage = HistoryPage<LearnerRemediationSessionHistoryEntry>

export type AssignmentStatus = 'assigned' | 'in_progress' | 'completed' | 'canceled'

export interface Assignment {
  assignment_id: string
  student_id: string
  teacher_id: string
  section_id?: string | null
  title: string
  description: string
  status: AssignmentStatus
  target_resource_id?: string | null
  target_kc_ids: string[]
  target_lo_ids: string[]
  due_at?: string | null
  created_at: string
  started_at?: string | null
  completed_at?: string | null
  updated_at: string
}

export interface AssignmentCreate {
  student_id: string
  section_id?: string | null
  title: string
  description?: string
  target_resource_id?: string | null
  target_kc_ids?: string[]
  target_lo_ids?: string[]
  due_at?: string | null
}

export type AssignmentPage = HistoryPage<Assignment>

// Mastery history snapshots
export interface MasterySnapshot {
  snapshot_id: string
  student_id: string
  overall_kc_mastery: number
  overall_lo_mastery: number
  kc_count: number
  lo_count: number
  mastered_kc_count: number
  struggling_kc_count: number
  engagement: string
  frustration: string
  total_load: number
  created_at: string
}

export interface MasteryHistoryResponse {
  student_id: string
  days: number
  snapshot_count: number
  snapshots: MasterySnapshot[]
}

export interface LearnerMasteryTrend {
  student_id: string
  snapshot_count: number
  snapshots: MasterySnapshot[]
  earliest_mastery: number | null
  latest_mastery: number | null
  mastery_delta: number
}

export interface SectionAveragePoint {
  timestamp: string
  average_mastery: number
  learner_count: number
}

export interface SectionMasteryTrendsResponse {
  section_id: string
  days: number
  learner_count: number
  learner_trends: LearnerMasteryTrend[]
  section_average_snapshots: SectionAveragePoint[]
}

export interface FrontendConfig {
  baseUrl: string
  apiKey: string
  bearerToken: string
  useDemoFallback: boolean
  showDebugPanels: boolean
}

export interface SetupStatus {
  configured: boolean
  has_llm_key: boolean
  has_embedding_key: boolean
  has_database: boolean
  has_admin_user: boolean
  llm_api_base: string
  llm_model: string | null
  auth_enabled: boolean
  config_file_exists: boolean
  app_version: string
}

export interface SetupConfigureRequest {
  llm_api_base?: string
  llm_api_key?: string
  llm_model?: string
  embedding_api_base?: string
  embedding_api_key?: string
  embedding_model?: string
  database_path?: string
}

export interface SetupModelCatalogRequest {
  api_base: string
  api_key: string
}

export interface SetupModelCatalogResponse {
  models: string[]
}

export interface SetupConfigureResponse {
  status: 'ok'
  config_path: string
  restart_required: boolean
}

export interface SystemConfigValues {
  app_name: string
  app_version: string
  database_path: string
  router_plugin: string
  retriever_plugin: string
  provider_plugin: string
  validator_plugin: string
  llm_api_base: string
  llm_api_key?: string | null
  llm_model?: string | null
  llm_timeout_seconds: number
  llm_allow_mock_fallback: boolean
  llm_secondary_api_base?: string | null
  llm_secondary_api_key?: string | null
  llm_secondary_model?: string | null
  llm_secondary_timeout_seconds?: number | null
  llm_circuit_breaker_threshold: number
  llm_circuit_breaker_cooldown_seconds: number
  llm_selection_strategy: string
  prompt_library_version: string
  prompt_experiment_enabled: boolean
  prompt_adaptive_selection_enabled: boolean
  prompt_variant_override?: string | null
  embedding_api_base: string
  embedding_api_key?: string | null
  embedding_model?: string | null
  embedding_dimensions: number
  embedding_timeout_seconds: number
  embedding_allow_local_fallback: boolean
  auth_enabled: boolean
  auth_token_secret?: string | null
  auth_token_issuer: string
  auth_token_ttl_seconds: number
  auth_refresh_ttl_seconds: number
  generation_cache_ttl_seconds: number
  predictive_warm_inline_process_limit: number
}

export interface SystemConfigResponse {
  config_path: string
  config_file_exists: boolean
  values: SystemConfigValues
}

export interface SystemConfigUpdateResponse {
  status: 'ok'
  config_path: string
  restart_required: boolean
}

export interface CourseUpsert {
  course_id: string
  title: string
  subject?: string | null
  grade_band?: string | null
  curriculum_package_id?: string | null
  tags?: string[]
}

export interface AdminCourseSummary {
  course_id: string
  title: string
  subject?: string | null
  grade_band?: string | null
  curriculum_package_id?: string | null
  tags: string[]
  updated_at: string
  section_count: number
}

export interface SectionUpsert {
  section_id: string
  course_id: string
  title: string
  grade_level?: string | null
  subject?: string | null
  tags?: string[]
}

export interface AdminSectionSummary {
  section_id: string
  course_id: string
  title: string
  grade_level?: string | null
  subject?: string | null
  tags: string[]
  updated_at: string
  course_title?: string | null
  teacher_count: number
  learner_count: number
}

export interface AdminSectionMembershipUserSummary {
  user_id: string
  display_name?: string | null
}

export interface AdminSectionMembershipSummary {
  section_id: string
  teachers: AdminSectionMembershipUserSummary[]
  learners: AdminSectionMembershipUserSummary[]
}

export interface AdminSectionMembershipUpdateRequest {
  teacher_user_ids: string[]
  learner_user_ids: string[]
}

export interface CreateInitialAdminRequest {
  display_name?: string
}

export interface CreateInitialAdminResponse {
  user_id: string
  api_key: string
  display_name: string | null
  role: string
}

export interface UserCreateRequest {
  display_name?: string
  role: string
  section_ids?: string[]
}

export interface UserCreateResponse {
  user_id: string
  credential: string
  display_name: string | null
  role: string
}

export interface UserSummary {
  user_id: string
  display_name: string | null
  role: string
  learner_id: string | null
  section_ids: string[]
  created_at: string
  updated_at: string
}

export interface UserUpdateRequest {
  display_name?: string
  role?: string
  section_ids?: string[]
}

export interface BulkUserCreateRequest {
  users: UserCreateRequest[]
}

export interface BulkUserCreateResponse {
  created: UserCreateResponse[]
}
