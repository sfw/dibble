# Dibble as a Composition of Harnesses

## Proof-of-concept system definition

---

## Framing

Dibble is a proof of concept for a thesis: autonomous AI teaching is not one giant model doing everything, but a composition of domain-specialized harnesses, each doing its one thing well, composing through typed contracts, with verification at every boundary.

This document defines the POC system. It is not a product specification. It deliberately omits regulatory compliance, institutional tenancy, guardian-legal frameworks, and the rest of the infrastructure a shipped ed-tech product would need. The POC exists to demonstrate that the thesis works, to produce visible learning outcomes, and to accumulate a compounding library of verified educational content. Product comes later.

**Deployment shape.** Dibble ships as a Docker container. A parent (typically a homeschool parent) pulls the image, provides model provider API keys, creates learner profiles for their children, and runs it on their own hardware. All learner data — profiles, observations, session history — stays inside the container. The container talks to hosted model providers for generation and to a shared cloud library for content retrieval. The cloud library is the only Dibble-hosted infrastructure, and by design it contains no personally identifiable information.

**Content rule, non-negotiable.** Generated content is a function of curriculum, never a function of learner identity. A worked example for fraction-addition is the same worked example regardless of who's being served it. Their *profiles* route them to it differently, but the content itself is curriculum-shaped, PII-free, and shareable across all users of the system. This rule is what makes the shared cloud library possible without compliance overhead, and it's what enables the library to compound across the entire user base.

**Harness architecture.** Nine harnesses, each with planner, executor, verifier, and durable state. Two layers of plugin-ness beneath them: modality plugins (what kind of content is produced) and model-provider plugins (what inference capability is used). The plugin system is what makes Dibble extensible — new modalities or new providers ship as plugins without touching core.

The nine harnesses:

1. Curriculum Intake & Alignment
2. Curriculum Planning
3. Learner Profile
4. Modality Routing
5. Content Generation (plugin host)
6. Assessment & Evidence
7. Socratic Dialogue
8. Within-Session Control
9. Autonomous Teacher

Two concerns that are full harnesses in a product — Safety & Compliance, and Escalation — collapse to smaller capabilities in the POC: a content-appropriateness verifier inside Content Generation, and a parent-notification capability inside Autonomous Teacher.

---

## Cross-cutting principles

**Typed contracts at every boundary.** Every harness defines its inputs and outputs as structured types. Harnesses communicate through these types, never through shared state.

**Verification is a first-class responsibility.** Every harness verifies its own output before returning. A harness that cannot verify returns a structured uncertainty signal, not a best-guess answer.

**Durable state is explicit and owned.** Every harness declares what state it owns. No state is shared between harnesses except through explicit contracts.

**Failure is a contract, not an exception.** Every harness declares how it can fail and what it returns on failure. Callers handle these cases explicitly.

**Provenance flows with everything.** Every artifact the system produces carries provenance — which harness produced it, from which inputs, with which verifier results.

**Calibration over fixed policy.** Harnesses that make decisions under uncertainty observe their own outcomes and update their priors. The system learns from its own performance.

**Content is curriculum-shaped, never learner-shaped.** The content rule, elevated to a system-wide invariant. Personalization happens at routing. Content is reusable.

---

## Deployment architecture

### The container

One Docker image contains the entire Dibble runtime: FastAPI backend, SQLite database, React frontend served statically, Python services for all nine harnesses, in-process modality plugins. The container is configured via environment variables (model provider credentials, cloud library endpoint, optional parent account credentials) and mounts a volume for the SQLite database so state persists across restarts.

One container per household. Parents install once, manage multiple children's profiles under one account, run Dibble on a laptop, home server, NAS, or modest VPS.

### The cloud library

A small, Dibble-hosted service. A read-heavy API over a content store. Accepts queries keyed on curriculum metadata and returns verified content artifacts. Accepts writes from container instances when they've generated new content that passes verification. Holds no personally identifiable information — by construction, everything in it is curriculum-shaped.

This is the only piece of infrastructure Dibble runs centrally. A single modest VPS plus object storage covers it. Read-scales by caching; write-scales by batching and verification gates.

### Model providers

Hosted models as the POC default. Text generation via Anthropic or OpenAI. TTS via ElevenLabs or OpenAI. Diagrams via hosted image or SVG-generation models. Interactive widget code via Claude or GPT code generation. Each modality plugin declares which model-provider plugin it needs; the container routes calls to the configured provider.

Local-model support is present in the existing codebase (OpenAI-compatible APIs including Ollama) but not the POC default. Parents who want to swap in local models later can do so by reconfiguration without touching any modality plugin.

### The data boundary

What crosses the container boundary, and what doesn't:

*Never leaves the container.* Learner profiles, observation history, session transcripts, assessment evidence, Socratic dialogue content, within-session controller state, parent-learner relationship context, any data that ties content to a specific learner.

*Leaves the container to model providers.* Curriculum-shaped generation prompts, containing KC targets, misconception descriptions, theme family, locale, scaffolding level. No learner identity, no session identity, no profile state.

*Leaves the container to the cloud library.* Queries (curriculum-shaped metadata only) and writes (newly-verified content, tagged with curriculum metadata, plus verification results). No learner data.

This discipline is what makes the compliance posture tractable. The container is the privacy boundary. Everything the container shares externally is curriculum-shaped by design.

---

## 1. Curriculum Intake & Alignment Harness

### Purpose

Turn external curriculum artifacts — standards documents, frameworks, community contributions — into Dibble's internal curriculum representation. For the POC, scope is narrow: enough curriculum to demonstrate adaptation across a few subjects and age ranges, not a global curriculum platform.

### POC scope

A handful of well-chosen frameworks covering subjects where modality adaptation produces the most visible differentiation. A reasonable starting set: Common Core math K-8, Next Generation Science Standards for grades 3-8, an adult-learning introduction-to-programming path, an elementary-school reading comprehension path. One international framework — Alberta Program of Studies, since the existing codebase already has it seeded — to prove the framework abstraction works.

### Contract

**Inputs.** Curriculum source documents (structured feeds where available, PDFs and spreadsheets where not), with metadata: jurisdiction, grade range, subject, version, language.

**Outputs.** Canonical Dibble curriculum artifacts: StandardsFramework, Strand, Outcome, KnowledgeComponent, with associated misconception catalogs and theme family tags. Alignment edges between equivalent KCs across frameworks where multiple frameworks are loaded.

### Planner

Chooses extraction strategy per source. Structured sources get deterministic parsing. Unstructured sources get LLM-assisted extraction with explicit uncertainty flags. Crosswalk proposals (alignment edges) are generated automatically via embedding similarity plus LLM-judge, with low-confidence proposals held for human review.

### Executor

Dedicated extraction pipeline per source type. LLM extraction uses constrained output against the Dibble curriculum schema.

### Verifier

Schema conformance, internal consistency (prerequisite graphs acyclic, grade levels monotonic), and alignment quality (crosswalks reviewed by independent LLM-judge). A human review gate for official frameworks; automated acceptance for well-structured contributions.

### Durable state

Versioned curriculum repository. Every import is a commit. Artifacts carry version history and provenance. Lives in the cloud library infrastructure — curriculum is public and shared, same as content.

### Failure modes

Parsing failure: structured error, import fails cleanly. Extraction confidence below threshold: artifacts drafted but marked `review_required`. Alignment conflict with existing edge: both recorded until resolved.

### Composition

Feeds Curriculum Planning as the sole source of curriculum truth. Read-only from every other harness's perspective.

---

## 2. Curriculum Planning Harness

### Purpose

Given a learner and a goal, produce and maintain a trajectory through the curriculum — which concepts to teach when, in what order, with what pacing. Replan when the trajectory stops working.

Distinct from Within-Session Control. This harness plans weeks and months; Within-Session plans the next few minutes.

### POC scope

Learner-declared goals only. "I want to learn Grade 5 math" or "I want to understand basic Python" or "I want to improve my reading comprehension." No test-date constraints, no institutional goals, no multi-stakeholder goal negotiation. The parent can review and approve proposed goals but the goal surface is narrow.

### Contract

**Inputs.** A learner (via profile reference), a goal pulled from the curriculum library, the learner's current profile state.

**Outputs.** A trajectory: an ordered, prerequisite-respecting sequence of concept clusters with expected durations, checkpoints, interleaving schedules, and spaced-practice rhythms. Revised as outcomes land.

### Planner

Operates on the curriculum graph and learner mastery state. Computes the concept sequence required to reach the goal, respects prerequisites, estimates durations from learner pace priors, inserts spaced-practice revisits, interleaves related concepts. Re-runs on a schedule and on trigger events.

### Executor

Execution happens in other harnesses. This harness maintains the trajectory and revises it.

### Verifier

Prerequisite consistency, goal reachability, pace feasibility, cognitive-load balance. On revision, additional check: concepts already mastered aren't re-introduced, concepts in progress aren't abandoned without cause.

### Durable state

Per-learner trajectory history. Current active trajectory. Revision log. Inside the container.

### Failure modes

Goal not reachable given current pace: warning returned with shortfall analysis, not silently truncated. Curriculum graph missing prerequisites: gap report surfaced to Curriculum Intake. No viable trajectory: returns alternatives (relax deadline, narrow goal, accept lower mastery threshold).

### Composition

Reads Curriculum Intake (curriculum graph) and Learner Profile. Emits trajectory directives to Within-Session Control and Autonomous Teacher.

---

## 3. Learner Profile Harness

### Purpose

Maintain the canonical, durable model of who a learner is: knowledge state, affective state, cognitive load, metacognitive state, modality affinity, strategy profile, emotional trajectory, cognitive traits where evidence permits. Every other harness reads from this model; no other harness writes to it.

The profile stays fully scoped in the POC. This is the heart of personalization and it's not where to cut.

### Contract

**Inputs.** Observations from learner interactions (correctness, timing, hints, pauses, modality switches, completion). Assessment evidence. Socratic dialogue evidence. Engagement signals per modality. Explicit learner-declared updates (accommodation registrations, preferences).

**Outputs.** The learner profile. The single source of learner truth.

### Planner

Given an incoming signal, decide which profile dimensions to update, at what rate, with what confidence adjustment. Different signals update different dimensions. Also decides when to apply mastery decay to stale dimensions.

### Executor

Inference pipeline per dimension. Bayesian blending against priors with confidence-weighted updates. Cross-signal coherence checks: contradictions are recorded, not silently averaged.

### Verifier

Cross-signal consistency, temporal plausibility, calibration check. Systematically-wrong predictions flag the relevant inference pipeline for review. Periodic aggregate calibration across profiles surfaces model drift.

### Durable state

Per-learner profile, fully versioned. Every update is a durable event. Historical profiles reconstructable at any past time. Calibration records per prediction type. All inside the container.

### Failure modes

Signal for non-existent learner: rejected. Signal contradicts recent signal beyond threshold: neither fully applied, additional evidence requested. Calibration check fails: update held, operator alert. Inference fails to converge: returns "insufficient" rather than low-confidence posterior.

### Composition

Read by nearly every harness. Written only by this harness, only from inputs in its contract. The single-writer invariant is the reason the profile can be trusted.

### PII boundary

Profile state never crosses into content. Profile can tell the routing harness "this learner engages with game modalities in pet-care theme"; that translates to a content request for "game modality, pet-care theme" with no learner identity attached. The transformation from learner-specific profile dimensions to curriculum-shaped content parameters happens at the routing boundary.

---

## 4. Modality Routing Harness

### Purpose

Given a learner, a concept, and a pedagogical move (explain, practice, remediate, assess, stretch), decide which modality — or composition of modalities — to deliver it in. Decide which Content Generation plugin(s) to invoke. Update the decision model based on observed engagement and mastery outcomes.

This is the harness that most directly demonstrates the thesis. When a learner struggles with fraction addition in text and the next attempt comes back as a game in a theme they engage with, that's the visible adaptation the POC exists to show off.

### Contract

**Inputs.** Learner profile (full read), concept target (KC and outcome), pedagogical move from Within-Session Control, composition context (what modalities have been recent), session constraints (budget, accessibility needs).

**Outputs.** A modality directive: which plugin(s) to invoke, in what composition, with what curriculum-shaped parameters. Passed to Content Generation.

### Planner

Contextual bandit over plugin identity. Thompson sampling with Beta priors per (learner × concept cluster × plugin). This extends the pattern already in the codebase's adaptive router, widening the action space from four interventions to the full plugin space.

Priors are built from modality affinity (from Learner Profile), recent modality history (avoid repetition unless warranted), expected mastery-lift from calibration data, plugin capability match. Thompson sampling picks.

Composition is a second planner stage: for some moves, the planner may choose to compose multiple plugins (text narrative + embedded diagram + audio narration). Composition decisions have their own priors.

**Critically for the content rule:** the routing harness is where learner-specific information gets *translated* into curriculum-shaped parameters. The profile says "this learner engages with pet-care themes." The routing harness converts that into a content request for "pet-care theme" on the target KC. The content request itself contains no learner identity.

### Executor

Hands off to Content Generation with a structured, curriculum-shaped request. Does not generate anything itself. Owns composition orchestration when multiple plugins are invoked.

### Verifier

Pre-dispatch: chosen plugin(s) satisfy declared constraints. Post-generation: returned content matches the modality directive. Outcome-based, slower: did the chosen modality produce engagement and mastery improvement for this learner? Feeds back into priors.

### Durable state

Per-learner per-concept-cluster priors over plugins. Historical routing decisions with outcomes. Composition priors. Inside the container — these are learner-specific.

### Failure modes

No plugin matches constraints: returns `no-viable-modality` signal. Selected plugin fails: falls back to next-best in sampled ordering. All plugins fail: escalates.

### Composition

Reads Learner Profile. Writes to Content Generation. Reports outcomes back to Learner Profile as engagement signals.

---

## 5. Content Generation Harness (Plugin Host)

### Purpose

Host the modality plugins. Dispatch curriculum-shaped requests to them. Compose their outputs. Verify outputs. Manage the content library's read/write path. This harness is small; its value is the plugin system it enables and the library discipline it enforces.

The plugin host is where the content rule lives as an enforced contract: every input to every plugin and every artifact produced by every plugin is curriculum-shaped, never learner-shaped.

### Contract

**Inputs.** A curriculum-shaped modality directive from Routing: which plugin(s), composition plan, learning objective, curriculum context, theme family, scaffolding level, locale. No learner identity.

**Outputs.** A generated artifact with the modality-native content, standardized accessibility metadata (alt text, captions, transcripts), provenance (plugin identity, version, model identity, prompt version, input hash), verifier results, confidence scores, interaction hooks.

### Plugin contract

Every modality plugin implements the same interface:

**Capability declaration.** Modality type, supported subjects, supported grade ranges, supported languages, accessibility properties, minimum/maximum latency, cost per call, quality tier. This metadata is what Modality Routing uses to decide eligibility and pick.

**Input schema.** Curriculum-shaped request. Objective, KC target, misconception target, curriculum grounding from retrieval, theme family, scaffolding level, locale. Explicitly no learner identity fields — the schema doesn't have slots for them.

**Output schema.** Modality-native content, accessibility metadata, provenance, self-verifier results, confidence, interaction hooks.

**Self-verifier.** Plugin runs modality-specific correctness checks before returning. Text plugin runs math-sanity and grounding coverage. Diagram plugin runs VLM review. Widget plugin runs sandbox execution. Plugin returns results; does not hide failures.

**Lifecycle hooks.** Init, health-check, shutdown, version info.

### POC plugin set

Five modality plugins at launch. Each demonstrates something specific:

*Text plugin.* Explanations, worked examples, practice problems, short narratives. Uses text-generation model-provider plugin. Self-verifies grounding coverage, readability, math sanity where applicable.

*Audio plugin.* Narrated explanations, dialogue-style walkthroughs, audio prompts. Uses TTS model-provider plugin over text produced by the text plugin or directly generated. Self-verifies audio duration, caption alignment.

*Diagram plugin.* Static SVG diagrams for geometric, arithmetic, scientific concepts. Constrained LLM output to SVG, with VLM-judge verification that the diagram shows what it claims to show.

*Interactive widget plugin.* Browser-rendered React/Canvas/Three.js manipulatives — number lines, fraction bars, geometry sandboxes, algebra balances. Code generated by LLM against a typed widget SDK, sandboxed in the frontend iframe, verified by headless execution before serving.

*Narrative plugin.* Story-based concept introductions and practice contexts. Text-modality but with narrative structure, theme families, and character frameworks. Uses text-generation model-provider. Self-verifies narrative coherence, age-appropriate vocabulary, concept integration.

These five cover enough modality diversity to demonstrate the thesis without requiring the hardest plugins (generated video, generated games) that warrant their own research tracks.

### Model-provider plugin layer

Separate from modality plugins. Each model-provider plugin wraps inference for a specific capability: text generation, TTS, diagram generation, code generation, embedding. Modality plugins declare which inference capabilities they need; model-provider plugins fulfill them.

POC ships with hosted-provider configurations (Anthropic text, OpenAI text as fallback, ElevenLabs TTS, hosted image generation). Swappable to local providers via configuration without touching modality plugins.

### Planner (of the host)

Given a modality directive, resolve plugins from the capability registry, assemble the curriculum-shaped input (fetching curriculum grounding from retrieval, composing theme parameters), plan composition if multiple plugins involved, decide whether to serve from the shared library cache.

**Library-first retrieval.** Before generating anything fresh, query the cloud library for a matching verified artifact. Match keyed on (concept, misconception if applicable, modality, theme family, locale, scaffolding level). Hit: serve from library. Miss or staleness threshold exceeded: generate fresh.

### Executor (of the host)

Dispatches to plugins. In-process for POC (all five plugins run inside the container). The host enforces timeout budgets, retry policies, circuit-breaker semantics. Composition orchestration happens here.

### Verifier (of the host)

Three layers on top of plugin self-verification:

*System content verifier.* Independent model reviews the artifact for pedagogical correctness, curriculum alignment, misconception avoidance. Different model family than the generator for independence.

*Composition coherence verifier.* When multiple plugins' outputs are composed, verify the pieces hang together — diagram illustrates what text is explaining, audio matches text, etc.

*Content-appropriateness verifier.* The POC version of what would be Safety & Compliance in a product. Age-neutral-or-appropriate content, no crisis-adjacent material generated casually, no content that would embarrass the project if it surfaced publicly. Curriculum-shaped content can't be personally inappropriate (it doesn't know who it's for) but it can still be pedagogically inappropriate, and this verifier catches that.

### Durable state

**Local (inside container):** plugin capability registry, recent-generation cache for rate-limiting and fallback, plugin lifecycle state.

**Cloud (shared library):** every successfully generated and verified artifact goes into the content-addressed library, keyed on curriculum metadata. Writes happen when a container generates something new and passes verification. Reads happen on every content request before fresh generation is considered. The library is the system's compounding asset.

### Failure modes

Plugin timeout: circuit-break, return failure to routing. Plugin returns invalid output: rejected, treated as plugin failure. Plugin self-verifier reports failure: artifact not used, failure reported. Host verifier rejects plugin-passed artifact: held for review, plugin's prior downgraded. Library unavailable: fall back to local generation; write to library on recovery.

### Composition

Called by Modality Routing. Reads from Learner Profile *only for plugin-declared-interest dimensions* (most plugins don't need profile data at all; the routing harness handles learner-specific considerations). Reads from Curriculum Intake for grounding. Reads from cloud library for cached artifacts. Writes to cloud library on fresh verified generation.

---

## 6. Assessment & Evidence Harness

### Purpose

Turn learner responses into structured evidence about what they know, how they're thinking, what misconceptions they hold, and how confident they are. Feed that evidence to Learner Profile.

Single-pass assessment path: a response arrives, the harness scores it. Multi-turn conversational path is the Socratic harness.

### Contract

**Inputs.** A learner response (answer to a problem, explanation, artifact, interaction trace from a widget), context (which concept, which misconception if remediation, expected form of response), and the associated content artifact's verifier results.

**Outputs.** An evidence bundle: mastery signal with confidence, detected misconceptions, depth-of-understanding signal, transfer-readiness signal, metacognitive signals (was self-reported confidence calibrated?), quality-of-evidence signal.

### Planner

Chooses evidence extractors based on response type. Multiple choice with reveal: correctness plus reveal-text analysis plus time-on-task. Free response: correctness plus misconception matching plus reasoning depth. Interactive widget trace: goal-achievement plus behavioral analysis. Narrative comprehension response: comprehension signal plus engagement quality.

### Executor

One extractor per evidence type. Correctness deterministic where possible. Misconception matching uses the catalog from Curriculum Intake with term aliases and behavioral evidence summaries — this is the existing `misconception_detector.py` machinery, preserved and extended. Depth estimation uses LLM-judging against a rubric with self-consistency checks.

### Verifier

Evidence-quality verifier: does the response justify the claimed mastery? Independent LLM-judge reviews. Disagreements below confidence don't update profile; they trigger additional evidence gathering (Socratic dialogue, more practice) via Within-Session Control.

Misconception-match verifier: claimed match requires specific evidence terms, not just lexical overlap.

### Durable state

Evidence history per learner. Rubric versions. Calibration records per extractor. Inside the container — this is learner-specific.

### Failure modes

Response uninterpretable: returns "insufficient" rather than fabricating mastery. Extractor low confidence: signal with explicit uncertainty, Learner Profile weights update less. Extractor disagreement with verifier: evidence quarantined, additional evidence requested.

### Composition

Consumes content artifacts and learner responses. Writes to Learner Profile. Signals Within-Session Control when quality is insufficient. Shares misconception-detection machinery with Socratic Dialogue.

---

## 7. Socratic Dialogue Harness

### Purpose

Conduct multi-turn assessment dialogues that reveal how a learner is thinking, not just whether they got an answer right. Produce evidence bundles that single-shot assessment can't.

Socratic is its own harness because its structure is fundamentally different from single-pass assessment. Its planner picks the next question based on the full dialogue; its executor is an ongoing loop; its verifier tracks evidence accumulation across turns; its state is the dialogue plus the evolving evidence picture; its termination is "enough evidence accumulated" or "dialogue stuck."

This is already one of the most sophisticated pieces of the existing codebase. Preserve and extend; don't rebuild.

### Contract

**Inputs.** A learner, a concept or misconception target, optional prior dialogue context (if resuming), an evidence sufficiency target.

**Outputs.** A completed dialogue session (history, evidence trajectory, final mastery assessment, detected misconceptions, metacognitive observations) or an in-progress session state.

### Planner

The turn policy. Given the dialogue to date and current evidence state, decide next prompt style: diagnostic open-probe, clarification, scaffolded step-back, transfer check, misconception-targeted probe, consolidation. Detects patterns: clarification loops, repeated step-backs, stalled mastery trend, transfer-check success.

Substantially the policy already in `socratic_policy.py`. Preserve as-is, extend as the dialogue repertoire grows.

### Executor

Each turn: turn policy picks prompt style, prompt is composed via Content Generation (in dialog-modality — treat dialog as a sub-mode of text for POC), learner responds, evidence scorer evaluates in the context of the full dialogue. Loop until termination.

The dialog prompts themselves are still curriculum-shaped — they target specific KCs and misconceptions, they don't reference learner identity. Learner *responses* are private and stay in the container.

### Verifier

Per-turn: is the evaluation consistent with what the response contained? Independent judge reviews. Dialogue-level: is evidence accumulating? Stalled dialogues terminate with stall marker. Termination verifier: has enough evidence accumulated to justify claimed conclusion? If not, don't terminate even at high turn count.

### Durable state

Dialogue sessions, full history retained. Evidence trajectory per dialogue. Turn-policy decision history. Per-learner dialogue patterns. Inside the container.

### Failure modes

Learner disengages mid-dialogue: paused, state persisted, resumable or abandonable. Dialogue stalls: terminates with stall marker, signals Within-Session Control that a different approach is needed. Prompt generation fails: dialogue pauses.

### Composition

Invoked by Within-Session Control when deep evidence is needed. Calls Content Generation for each prompt. Emits evidence bundles to Learner Profile through the same pipeline as Assessment & Evidence.

---

## 8. Within-Session Control Harness

### Purpose

Run the outer loop during an active learner session. Decide the next move: continue, reteach, step back, stretch, swap modality, invoke Socratic, consolidate, end session. Invoke the appropriate downstream harness. Own the state of "what's happening right now in this session."

### Contract

**Inputs.** Active session context (learner, current concept from Curriculum Planning, time in session, session budget), learner profile (live read), most recent evidence bundle, current affective and cognitive-load state.

**Outputs.** The next action: a directive to Modality Routing, Socratic Dialogue, Assessment & Evidence, or a session-terminating directive.

### Planner

Thompson-sampling-with-safety-constraints over action types. Safety constraints first: high frustration triggers step-back, cognitive load threshold triggers simplification, session budget exhausted triggers graceful close. Inside the filtered space, Thompson sampling over: continue, reteach, step-back, stretch, swap-modality, invoke-Socratic, consolidate, end-session.

Priors from current evidence signal, session phase, support-step budget remaining, stuck-loop risk, streak lengths, time remaining. Much of this is already in `within_session_adaptation.py` and `adaptive_router.py`; the harness framing organizes what exists.

### Executor

Dispatches to the chosen downstream harness. Does not perform actions itself.

### Verifier

Action-appropriateness: chosen action matches learner state and session goals. Stuck-loop: if same action repeats without evidence progress, blocks repetition and forces different action. Session-coherence: sequence tells a coherent pedagogical story, not a thrashing pattern.

### Durable state

Active session state. Action history per session. Session-phase state (monitor/consolidate/recover). Support-step budget consumption. Stuck-loop counters. Inside the container.

### Failure modes

No viable action: escalates to Autonomous Teacher for higher-level decision. Downstream harness fails: picks next-best or gracefully ends session. Session state corruption: session ends, learner returned to safe state, incident logged.

### Composition

Invokes Modality Routing, Content Generation (via routing), Socratic Dialogue, Assessment & Evidence. Reads Learner Profile, receives trajectory directives from Curriculum Planning, escalates to Autonomous Teacher.

---

## 9. Autonomous Teacher Harness

### Purpose

Be the teacher. Own the full learner relationship across weeks and months. Initiate sessions, decide what a learner should be working on this week or today, track progress against goals, adjust trajectories, celebrate milestones, detect persistent issues, coordinate with the parent when needed.

This is the harness that makes Dibble be the teacher rather than a tool for one.

### POC scope

Per-learner session initiation on a cadence the learner (or parent) configures. "What to work on today" decisions. Gentle re-engagement when a learner has been away. Trajectory coordination with Curriculum Planning. Parent relationship: configurable approval gates, weekly summaries, the "I need your help" pathway.

Reduced from the full product version: no crisis-infrastructure escalation, no institutional coordination, no multi-stakeholder goal negotiation.

### Contract

**Inputs.** Learner full state (profile, goals, trajectory, recent sessions). External triggers (scheduled session, learner-initiated session, parent message, milestone event, stall detection).

**Outputs.** Session initiation directives to Within-Session Control, trajectory-revision requests to Curriculum Planning, goal-revision proposals to the learner (and parent if gated), parent notifications, "I need your help" signals.

### Planner

Long-horizon planner at weekly-to-monthly timescales. Decides session initiation timing (respecting schedule), next session focus (from active trajectory), trajectory revision triggers, milestone celebrations, engagement-drop check-ins, parent-notification triggers.

Has a *relationship* with each learner — understands their rhythms, preferred times, engagement and disengagement patterns. Explicit state, not emergent.

### Executor

Emits directives. Initiates sessions via Within-Session Control. Requests trajectory revisions from Curriculum Planning. Sends notifications to the parent via a simple notification subsystem (email, in-app notification).

### Verifier

Action-cadence: not obnoxiously frequent or negligently rare. Relationship coherence: behavior over time consistent with the learner's accumulated relationship context. Goal-alignment: actions in service of declared goals, not drifting.

### Durable state

Per-learner teacher state. Relationship context (interaction rhythms, preferences, milestones, remembered context). Session initiation history. Trajectory revision history. Notification history. Inside the container.

### Parent relationship

A parent-facing view of the learner's activity — read-mostly access to what's been worked on, mastery trends, what's currently stuck, what the teacher is planning.

Configurable approval gates. A parent who wants hands-off disables them; a parent who wants hands-on sets them on new concepts, new modalities, trajectory revisions. The teacher respects parental authority without requiring it.

Parent-preference state per learner. Which notifications they want, what cadence, whether they approve new modalities or just new subjects, etc.

Soft-escalation pathway. When the system is genuinely stuck (persistent stall across multiple modalities and sessions, apparent sustained frustration, signals warranting adult attention), it surfaces this to the parent as a first-class event: "Maya has been stuck on fraction addition across three sessions and multiple modalities — you might want to work with her directly." The teacher knows it's not omniscient and says so to the parent. This replaces the full Escalation harness.

### Failure modes

Learner non-responsive: re-engagement protocol, then soft-escalation to parent. Goal demonstrably unreachable: trajectory revision requested, learner and parent informed. Relationship context loss: teacher falls back to generic mode and rebuilds over time rather than acting on bad state.

### Composition

Top-level orchestrator. Reads from Learner Profile, Curriculum Planning, its own state. Writes to Within-Session Control (session initiation), Curriculum Planning (revision requests), notification subsystem (parent communications). Conductor of the system at long horizons, while Within-Session Control conducts at short horizons.

---

## Composition topology

How the harnesses interact at runtime.

A learner session begins when Autonomous Teacher decides it's time (scheduled rhythm, learner-initiated, parent-initiated). Autonomous Teacher invokes Within-Session Control with the session target (from Curriculum Planning's active trajectory) and current learner profile state.

Within-Session Control loops. Each iteration: read current state, pick an action. If the action involves content, invoke Modality Routing. Modality Routing picks a plugin (or composition), invokes Content Generation with a curriculum-shaped request. Content Generation checks the cloud library first; hits serve from library, misses dispatch to plugin(s). Plugin(s) generate, self-verify, return. Host composition-verifies, content-appropriateness-verifies, writes fresh verified artifacts back to library, returns artifact. Artifact delivered to learner. Learner responds. Response flows to Assessment & Evidence (or Socratic, if that was the action). Evidence bundle updates Learner Profile. Updated profile feeds back to Within-Session Control for next iteration.

At session end, Within-Session Control emits a session summary. Autonomous Teacher consumes it, updates relationship context, potentially requests trajectory revisions, potentially surfaces notifications to the parent, decides when the next session should be.

Curriculum Intake operates on a completely separate cadence — ingesting new curriculum, maintaining the graph. Not in the learner flow.

---

## What flows across the container boundary

Explicitly, because this is the privacy contract.

**Container → cloud library (reads).** Curriculum-shaped queries. KC target, misconception target, modality, theme family, locale, scaffolding level. No learner identity, session identity, or profile state.

**Container → cloud library (writes).** Newly generated and verified content. Curriculum metadata tags. Verification results. Again no learner data.

**Container → model providers.** Curriculum-shaped generation prompts. KC target, misconception description, theme family, locale, scaffolding level. Sent as standard LLM API calls, subject to whatever the provider's terms say about prompt handling. No learner identity in prompts by system-level enforcement.

**Nothing else leaves the container.** Learner profiles, observations, session history, Socratic dialogues, assessment evidence, within-session controller state, parent-relationship state — all stays local. The container is the privacy boundary.

---

## What the POC demonstrates

Five things, in priority order:

**Modality adaptation works.** A learner struggling with a math concept gets something *different* the second time — not just a different worded explanation, but a different modality. Text didn't land, so now it's a diagram, then an interactive widget, then a generated narrative. The learner can feel the system adapting to them in a way no other product does. If nothing else works, this alone is the demo.

**The system actually teaches.** Users who use Dibble for a week are demonstrably better at the concepts they studied. Pre/post assessments, not RCT-grade but real enough to show learning gain. Without this, the POC is just a clever content generator.

**The library compounds.** Return demos at 3 months, 6 months, 12 months show a dramatically richer library of verified content. Technical audiences can look at library growth and verification infrastructure and see the compounding asset in action.

**The harness composition is visible.** The internals are legible. A technical viewer can inspect the system and see the planner/executor/verifier/state structure of each harness. The POC isn't just a working product; it's a reference implementation of the harness thesis.

**The modality plugin system is real and extensible.** A researcher or contributor can ship a new modality plugin and have it work. The POC launches with five plugins; the architecture supports adding a sixth without touching anything else.

---

## What the POC doesn't address

*Regulatory compliance.* COPPA, FERPA, GDPR, AADC are product concerns, not POC concerns. The container-local data boundary plus curriculum-shaped-content-only library gets the POC to a reasonable starting posture for individual users, but shipping to schools requires the full product treatment.

*Institutional deployment.* LTI, OneRoster, SAML, the whole institutional-LMS integration surface. Not a POC concern.

*Multi-stakeholder workflows.* Teachers supervising classrooms, districts setting policy, parents with legal standing in institutional contexts. The POC has a single parent stakeholder per learner by design.

*Outcome validation at scale.* Building the system and proving at scientific rigor that it outperforms alternatives are different projects. The POC can produce outcome data; serious efficacy claims require dedicated research.

*Advanced modalities.* Generated video, generated games, generated simulations. The plugin system supports them; the POC doesn't include them. They're research frontiers that warrant their own tracks.

---

## Closing

The POC's claim is that autonomous AI teaching is a composition of nine specialized harnesses, each doing one thing well, connected by typed contracts and curriculum-shaped content. It runs in a container parents can install on their own hardware. It contributes to and benefits from a shared public library of verified educational content. It demonstrates — concretely and visibly — that the harness thesis produces teaching that works.

If the POC shines, the product comes next. The harnesses that got simplified for the POC (Safety & Compliance, Escalation, institutional deployment) expand back out when the product is worth building. The foundation stays the same.
