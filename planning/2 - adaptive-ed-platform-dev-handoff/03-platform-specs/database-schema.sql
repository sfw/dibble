-- Adaptive K-12 Learning Platform Database Schema
-- Generated from content-metadata-schema.csv and platform specifications
-- PostgreSQL 14+ with pgcrypto and pg_trgm extensions required

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =============================================================================
-- USER MANAGEMENT
-- =============================================================================

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255), -- NULL for SSO users
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    user_type VARCHAR(20) NOT NULL CHECK (user_type IN ('student', 'teacher', 'parent', 'admin', 'specialist')),
    auth_provider VARCHAR(20) DEFAULT 'local' CHECK (auth_provider IN ('local', 'clever', 'google', 'microsoft')),
    external_id VARCHAR(100), -- SSO provider ID
    email_verified BOOLEAN DEFAULT FALSE,
    last_login_at TIMESTAMP WITH TIME ZONE,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE, -- Soft delete
    mfa_enabled BOOLEAN DEFAULT FALSE,
    mfa_secret_encrypted TEXT
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_external_id ON users(external_id) WHERE external_id IS NOT NULL;
CREATE INDEX idx_users_type ON users(user_type);

-- =============================================================================
-- STUDENTS
-- =============================================================================

CREATE TABLE students (
    student_id UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    grade_level INTEGER CHECK (grade_level BETWEEN 0 AND 12),
    date_of_birth DATE,
    home_language VARCHAR(50),
    english_proficiency VARCHAR(20) CHECK (english_proficiency IN ('native', 'fluent', 'intermediate', 'beginner')),
    enrollment_status VARCHAR(20) DEFAULT 'active' CHECK (enrollment_status IN ('active', 'inactive', 'transferred', 'graduated')),
    current_school_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE student_accommodations (
    student_id UUID REFERENCES students(student_id) ON DELETE CASCADE,
    accommodation VARCHAR(50) NOT NULL CHECK (accommodation IN (
        'tts', 'extended_time', 'reduced_motion', 'word_highlighting', 
        'high_contrast', 'font_scale', 'screen_reader', 'closed_captions',
        'alternative_navigation', 'color_blind_mode'
    )),
    notes TEXT,
    approved_by UUID REFERENCES users(user_id),
    approved_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (student_id, accommodation)
);

-- =============================================================================
-- TEACHERS & PARENTS
-- =============================================================================

CREATE TABLE teachers (
    teacher_id UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    school_id UUID,
    department VARCHAR(100),
    years_of_experience INTEGER,
    certifications TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE parents (
    parent_id UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    phone VARCHAR(20),
    notification_preferences JSONB DEFAULT '{"email": true, "sms": false, "push": true}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE parent_student_links (
    parent_id UUID REFERENCES parents(parent_id) ON DELETE CASCADE,
    student_id UUID REFERENCES students(student_id) ON DELETE CASCADE,
    relationship VARCHAR(30) NOT NULL CHECK (relationship IN ('mother', 'father', 'guardian', 'grandparent', 'other')),
    is_primary_contact BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (parent_id, student_id)
);

-- =============================================================================
-- CLASSES & ENROLLMENTS
-- =============================================================================

CREATE TABLE schools (
    school_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    district VARCHAR(200),
    state VARCHAR(2),
    country VARCHAR(2) DEFAULT 'US',
    timezone VARCHAR(50) DEFAULT 'America/New_York',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE classes (
    class_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    subject VARCHAR(100) NOT NULL,
    grade_level INTEGER,
    school_id UUID REFERENCES schools(school_id),
    teacher_id UUID REFERENCES teachers(teacher_id),
    academic_year VARCHAR(9) NOT NULL, -- e.g., "2025-2026"
    semester VARCHAR(10) CHECK (semester IN ('fall', 'spring', 'summer', 'year')),
    start_date DATE,
    end_date DATE,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'archived')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE class_enrollments (
    enrollment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    class_id UUID REFERENCES classes(class_id) ON DELETE CASCADE,
    student_id UUID REFERENCES students(student_id) ON DELETE CASCADE,
    enrolled_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    dropped_at TIMESTAMP WITH TIME ZONE,
    UNIQUE (class_id, student_id, enrolled_at)
);

CREATE INDEX idx_classes_teacher ON classes(teacher_id);
CREATE INDEX idx_classes_school ON classes(school_id);
CREATE INDEX idx_enrollments_class ON class_enrollments(class_id);
CREATE INDEX idx_enrollments_student ON class_enrollments(student_id);

-- =============================================================================
-- LEARNING OBJECTS & CONTENT MODULES
-- =============================================================================

CREATE TABLE subjects (
    subject_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    parent_subject_id UUID REFERENCES subjects(subject_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE learning_objectives (
    lo_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    subject_id UUID REFERENCES subjects(subject_id),
    grade_bands VARCHAR(20)[] CHECK (grade_bands <@ ARRAY['K-2', '3-5', '6-8', '9-12']),
    cognitive_level VARCHAR(20) CHECK (cognitive_level IN ('remember', 'understand', 'apply', 'analyze', 'evaluate', 'create')),
    difficulty_estimate INTEGER CHECK (difficulty_estimate BETWEEN 1 AND 5),
    tags TEXT[],
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE content_modules (
    content_module_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lo_id UUID REFERENCES learning_objectives(lo_id),
    title VARCHAR(200) NOT NULL,
    description TEXT,
    module_type VARCHAR(20) NOT NULL CHECK (module_type IN ('instruction', 'practice', 'assessment', 'review')),
    difficulty_tier INTEGER CHECK (difficulty_tier BETWEEN 1 AND 5),
    
    -- Content storage (JSONB for flexibility)
    content_json JSONB NOT NULL,
    
    -- Format variants available
    format_variants VARCHAR(20)[] DEFAULT ARRAY['text']::varchar[] 
        CHECK (format_variants <@ ARRAY['text', 'video', 'interactive', 'audio', 'image']),
    
    -- Accessibility features
    accessibility_features VARCHAR(50)[],
    
    -- Estimated time in minutes
    estimated_time_minutes INTEGER,
    
    -- Engagement metrics
    avg_completion_time_minutes INTEGER,
    avg_accuracy DECIMAL(5,4),
    
    -- Metadata
    author_id UUID REFERENCES teachers(teacher_id),
    is_published BOOLEAN DEFAULT FALSE,
    publish_date DATE,
    version VARCHAR(20) DEFAULT '1.0.0',
    tags TEXT[],
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Full-text search for content
CREATE INDEX idx_content_search ON content_modules 
    USING gin(to_tsvector('english', title || ' ' || COALESCE(description, '')));

-- =============================================================================
-- PREREQUISITE RELATIONSHIPS (Graph topology in PostgreSQL)
-- =============================================================================

CREATE TABLE content_prerequisites (
    module_id UUID REFERENCES content_modules(content_module_id) ON DELETE CASCADE,
    prerequisite_module_id UUID REFERENCES content_modules(content_module_id) ON DELETE CASCADE,
    is_strict BOOLEAN DEFAULT TRUE, -- Must complete before proceeding
    min_mastery_threshold DECIMAL(5,4) DEFAULT 0.70,
    PRIMARY KEY (module_id, prerequisite_module_id)
);

CREATE TABLE lo_prerequisites (
    lo_id UUID REFERENCES learning_objectives(lo_id) ON DELETE CASCADE,
    prerequisite_lo_id UUID REFERENCES learning_objectives(lo_id) ON DELETE CASCADE,
    relationship_type VARCHAR(20) DEFAULT 'required' CHECK (relationship_type IN ('required', 'recommended', 'parallel')),
    PRIMARY KEY (lo_id, prerequisite_lo_id)
);

-- =============================================================================
-- STANDARDS ALIGNMENT
-- =============================================================================

CREATE TABLE standards_frameworks (
    framework_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) UNIQUE NOT NULL, -- e.g., 'CCSS', 'NGSS', 'TEKS'
    name VARCHAR(100) NOT NULL,
    description TEXT,
    jurisdiction VARCHAR(100),
    version VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE standards (
    standard_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    framework_id UUID REFERENCES standards_frameworks(framework_id),
    code VARCHAR(100) NOT NULL, -- e.g., 'CCSS.MATH.4.OA.A.1'
    description TEXT NOT NULL,
    grade_band VARCHAR(20),
    subject VARCHAR(100),
    parent_standard_id UUID REFERENCES standards(standard_id),
    full_notation TEXT,
    UNIQUE (framework_id, code)
);

CREATE TABLE content_standards_alignment (
    content_module_id UUID REFERENCES content_modules(content_module_id) ON DELETE CASCADE,
    standard_id UUID REFERENCES standards(standard_id) ON DELETE CASCADE,
    alignment_type VARCHAR(20) DEFAULT 'primary' CHECK (alignment_type IN ('primary', 'secondary', 'related')),
    mastery_threshold DECIMAL(5,4) DEFAULT 0.70,
    PRIMARY KEY (content_module_id, standard_id)
);

CREATE INDEX idx_standards_framework ON standards(framework_id);
CREATE INDEX idx_standards_code ON standards(code);

-- =============================================================================
-- KNOWLEDGE TRACING & STUDENT KNOWLEDGE STATE
-- =============================================================================

CREATE TABLE student_knowledge_state (
    knowledge_state_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID REFERENCES students(student_id) ON DELETE CASCADE,
    lo_id UUID REFERENCES learning_objectives(lo_id),
    
    -- BKT Parameters
    mastery_probability DECIMAL(5,4) NOT NULL CHECK (mastery_probability BETWEEN 0 AND 1),
    p_guess DECIMAL(5,4) DEFAULT 0.20 CHECK (p_guess BETWEEN 0 AND 1),
    p_slip DECIMAL(5,4) DEFAULT 0.10 CHECK (p_slip BETWEEN 0 AND 1),
    p_learn DECIMAL(5,4) DEFAULT 0.30 CHECK (p_learn BETWEEN 0 AND 1),
    p_forget DECIMAL(5,4) DEFAULT 0.05 CHECK (p_forget BETWEEN 0 AND 1),
    
    -- Metadata
    attempts_count INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    consecutive_correct INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP WITH TIME ZONE,
    last_attempt_correct BOOLEAN,
    
    -- Forgetting curve (SM2)
    sm2_interval INTEGER DEFAULT 1, -- Days until next review
    sm2_easiness DECIMAL(3,2) DEFAULT 2.5 CHECK (sm2_easiness BETWEEN 1.3 AND 3.0),
    sm2_repetitions INTEGER DEFAULT 0,
    next_review_at TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE (student_id, lo_id)
);

CREATE INDEX idx_knowledge_state_student ON student_knowledge_state(student_id);
CREATE INDEX idx_knowledge_state_lo ON student_knowledge_state(lo_id);
CREATE INDEX idx_knowledge_state_mastery ON student_knowledge_state(mastery_probability);

-- =============================================================================
-- LEARNING INTERACTIONS (High volume - consider partitioning by date)
-- =============================================================================

CREATE TABLE learning_interactions (
    interaction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID REFERENCES students(student_id),
    content_module_id UUID REFERENCES content_modules(content_module_id),
    event_type VARCHAR(30) NOT NULL CHECK (event_type IN (
        'content_started', 'content_completed', 'content_abandoned',
        'answer_submitted', 'hint_requested', 'hint_used',
        'break_taken', 'session_ended'
    )),
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ended_at TIMESTAMP WITH TIME ZONE,
    time_spent_seconds INTEGER,
    
    -- Performance
    correctness DECIMAL(5,4), -- NULL for non-graded events
    attempts_count INTEGER DEFAULT 1,
    hint_count INTEGER DEFAULT 0,
    
    -- Interaction data
    response_data JSONB,
    system_data JSONB, -- Browser, device, etc.
    
    -- Session tracking
    session_id UUID,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
) PARTITION BY RANGE (started_at);

-- Create monthly partitions (example for 2026)
CREATE TABLE learning_interactions_2026_01 PARTITION OF learning_interactions
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE learning_interactions_2026_02 PARTITION OF learning_interactions
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE learning_interactions_2026_03 PARTITION OF learning_interactions
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

CREATE INDEX idx_interactions_student ON learning_interactions(student_id);
CREATE INDEX idx_interactions_module ON learning_interactions(content_module_id);
CREATE INDEX idx_interactions_event ON learning_interactions(event_type);

-- =============================================================================
-- ASSESSMENTS
-- =============================================================================

CREATE TABLE assessments (
    assessment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_type VARCHAR(20) NOT NULL CHECK (assessment_type IN ('diagnostic', 'progress', 'benchmark', 'summative')),
    student_id UUID REFERENCES students(student_id),
    subject_id UUID REFERENCES subjects(subject_id),
    
    -- Assessment metadata
    status VARCHAR(20) DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'completed', 'abandoned', 'expired')),
    total_items INTEGER NOT NULL,
    items_completed INTEGER DEFAULT 0,
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    time_limit_minutes INTEGER,
    
    -- Adaptive parameters
    is_adaptive BOOLEAN DEFAULT TRUE,
    initial_ability_estimate DECIMAL(5,4),
    final_ability_estimate DECIMAL(5,4),
    standard_error DECIMAL(5,4),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE assessment_items (
    item_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID REFERENCES assessments(assessment_id) ON DELETE CASCADE,
    lo_id UUID REFERENCES learning_objectives(lo_id),
    content_module_id UUID REFERENCES content_modules(content_module_id),
    item_number INTEGER NOT NULL,
    difficulty_estimate DECIMAL(5,4),
    
    -- Response
    response_data JSONB,
    correctness DECIMAL(5,4),
    time_spent_seconds INTEGER,
    hint_used BOOLEAN DEFAULT FALSE,
    confidence_level INTEGER CHECK (confidence_level BETWEEN 1 AND 5),
    
    answered_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_assessments_student ON assessments(student_id);
CREATE INDEX idx_assessments_type ON assessments(assessment_type);

-- =============================================================================
-- RECOMMENDATIONS & LEARNING PATH
-- =============================================================================

CREATE TABLE recommendations (
    recommendation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID REFERENCES students(student_id),
    content_module_id UUID REFERENCES content_modules(content_module_id),
    
    -- Recommendation context
    context VARCHAR(30) CHECK (context IN ('onboarding', 'daily_session', 'review', 'intervention', 'assessment_gap')),
    priority_score DECIMAL(5,4),
    predicted_success_probability DECIMAL(5,4),
    estimated_time_minutes INTEGER,
    
    -- Scaffolding
    recommended_scaffolding JSONB,
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected', 'completed', 'skipped')),
    
    -- ML metadata
    model_version VARCHAR(20),
    features_used JSONB,
    
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    presented_at TIMESTAMP WITH TIME ZONE,
    responded_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_recommendations_student ON recommendations(student_id);
CREATE INDEX idx_recommendations_status ON recommendations(status);

-- =============================================================================
-- TEACHER INTERVENTIONS
-- =============================================================================

CREATE TABLE interventions (
    intervention_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID REFERENCES students(student_id),
    teacher_id UUID REFERENCES teachers(teacher_id),
    class_id UUID REFERENCES classes(class_id),
    
    intervention_type VARCHAR(30) CHECK (intervention_type IN (
        'content_review', 'small_group', 'accommodation_adjustment',
        'parent_notification', 'specialist_referral', 'custom'
    )),
    description TEXT,
    
    -- Assigned content
    assigned_modules UUID[],
    
    -- Timeline
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    due_date DATE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'resolved', 'escalated', 'no_response', 'dismissed')),
    
    -- Outcome
    outcome_notes TEXT,
    effectiveness_rating INTEGER CHECK (effectiveness_rating BETWEEN 1 AND 5)
);

-- =============================================================================
-- SESSIONS & ANALYTICS
-- =============================================================================

CREATE TABLE learning_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID REFERENCES students(student_id),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    total_time_minutes INTEGER,
    items_completed INTEGER DEFAULT 0,
    items_attempted INTEGER DEFAULT 0,
    average_accuracy DECIMAL(5,4),
    session_type VARCHAR(20) DEFAULT 'normal' CHECK (session_type IN ('normal', 'review', 'diagnostic', 'intervention')),
    device_info JSONB
);

CREATE INDEX idx_sessions_student ON learning_sessions(student_id);
CREATE INDEX idx_sessions_date ON learning_sessions(started_at);

-- =============================================================================
-- AT-RISK ALERTS
-- =============================================================================

CREATE TABLE at_risk_alerts (
    alert_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID REFERENCES students(student_id),
    teacher_id UUID REFERENCES teachers(teacher_id),
    class_id UUID REFERENCES classes(class_id),
    
    risk_score DECIMAL(5,4) NOT NULL CHECK (risk_score BETWEEN 0 AND 1),
    risk_factors VARCHAR(50)[],
    knowledge_gaps UUID[], -- Array of lo_ids
    
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'acknowledged', 'intervention_created', 'resolved')),
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    acknowledged_by UUID REFERENCES teachers(teacher_id),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_alerts_teacher ON at_risk_alerts(teacher_id);
CREATE INDEX idx_alerts_student ON at_risk_alerts(student_id);
CREATE INDEX idx_alerts_status ON at_risk_alerts(status);

-- =============================================================================
-- AUDIT LOG (Security & Compliance)
-- =============================================================================

CREATE TABLE audit_log (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    session_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_resource ON audit_log(resource_type, resource_id);
CREATE INDEX idx_audit_created ON audit_log(created_at);

-- =============================================================================
-- TRIGGERS FOR UPDATED_AT
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_students_updated_at BEFORE UPDATE ON students
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_content_modules_updated_at BEFORE UPDATE ON content_modules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_learning_objectives_updated_at BEFORE UPDATE ON learning_objectives
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_student_knowledge_state_updated_at BEFORE UPDATE ON student_knowledge_state
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- VIEWS FOR COMMON QUERIES
-- =============================================================================

CREATE VIEW student_progress_summary AS
SELECT 
    s.student_id,
    u.first_name,
    u.last_name,
    s.grade_level,
    COUNT(DISTINCT k.lo_id) as skills_attempted,
    COUNT(DISTINCT CASE WHEN k.mastery_probability >= 0.70 THEN k.lo_id END) as skills_mastered,
    AVG(k.mastery_probability) as avg_mastery,
    COALESCE(SUM(li.time_spent_seconds), 0) / 60 as total_time_minutes,
    MAX(li.started_at) as last_activity_at
FROM students s
JOIN users u ON s.student_id = u.user_id
LEFT JOIN student_knowledge_state k ON s.student_id = k.student_id
LEFT JOIN learning_interactions li ON s.student_id = li.student_id
WHERE u.deleted_at IS NULL
GROUP BY s.student_id, u.first_name, u.last_name, s.grade_level;

CREATE VIEW class_analytics AS
SELECT 
    c.class_id,
    c.name as class_name,
    c.subject,
    COUNT(DISTINCT ce.student_id) as enrolled_students,
    COUNT(DISTINCT CASE WHEN ce.dropped_at IS NULL THEN ce.student_id END) as active_students,
    COUNT(DISTINCT a.alert_id) FILTER (WHERE a.status = 'active') as at_risk_count,
    AVG(sps.avg_mastery) as class_avg_mastery
FROM classes c
LEFT JOIN class_enrollments ce ON c.class_id = ce.class_id
LEFT JOIN at_risk_alerts a ON c.class_id = a.class_id
LEFT JOIN student_progress_summary sps ON ce.student_id = sps.student_id
GROUP BY c.class_id, c.name, c.subject;
