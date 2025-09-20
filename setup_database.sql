-- SNFLegTracker Database Setup Script
-- Run this script against your PostgreSQL database to create all tables

-- Create users table first (referenced by other tables)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    hashed_password VARCHAR(255),
    full_name VARCHAR(200),
    organization VARCHAR(200),
    role VARCHAR(50) DEFAULT 'user',
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    preferences TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Create indexes for users
CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);
CREATE INDEX IF NOT EXISTS ix_users_is_active ON users(is_active);

-- Create bills table
CREATE TABLE IF NOT EXISTS bills (
    id SERIAL PRIMARY KEY,
    bill_number VARCHAR(50) UNIQUE,
    title VARCHAR(500),
    summary TEXT,
    full_text TEXT,
    source VARCHAR(100),
    state_or_federal VARCHAR(20),
    introduced_date TIMESTAMP,
    last_action_date TIMESTAMP,
    status VARCHAR(100),
    sponsor VARCHAR(200),
    committee VARCHAR(200),
    chamber VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- Create indexes for bills
CREATE INDEX IF NOT EXISTS ix_bills_bill_number ON bills(bill_number);
CREATE INDEX IF NOT EXISTS ix_bills_title ON bills(title);
CREATE INDEX IF NOT EXISTS ix_bills_state_or_federal ON bills(state_or_federal);
CREATE INDEX IF NOT EXISTS ix_bills_introduced_date ON bills(introduced_date);
CREATE INDEX IF NOT EXISTS ix_bills_last_action_date ON bills(last_action_date);
CREATE INDEX IF NOT EXISTS ix_bills_status ON bills(status);
CREATE INDEX IF NOT EXISTS ix_bills_created_at ON bills(created_at);
CREATE INDEX IF NOT EXISTS ix_bills_is_active ON bills(is_active);

-- Create composite indexes for bills
CREATE INDEX IF NOT EXISTS idx_bill_search ON bills(title, summary);
CREATE INDEX IF NOT EXISTS idx_bill_date_status ON bills(last_action_date, status);
CREATE INDEX IF NOT EXISTS idx_bill_sponsor_committee ON bills(sponsor, committee);

-- Create keywords table
CREATE TABLE IF NOT EXISTS keywords (
    id SERIAL PRIMARY KEY,
    term VARCHAR(200) UNIQUE,
    category VARCHAR(100),
    synonyms TEXT,
    importance_weight FLOAT DEFAULT 1.0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_user_id INTEGER REFERENCES users(id)
);

-- Create indexes for keywords
CREATE INDEX IF NOT EXISTS ix_keywords_term ON keywords(term);
CREATE INDEX IF NOT EXISTS ix_keywords_category ON keywords(category);
CREATE INDEX IF NOT EXISTS ix_keywords_is_active ON keywords(is_active);

-- Create bill_versions table
CREATE TABLE IF NOT EXISTS bill_versions (
    id SERIAL PRIMARY KEY,
    bill_id INTEGER NOT NULL REFERENCES bills(id),
    version_number VARCHAR(20),
    title VARCHAR(500),
    summary TEXT,
    full_text TEXT,
    introduced_date TIMESTAMP,
    last_action_date TIMESTAMP,
    status VARCHAR(100),
    sponsor VARCHAR(200),
    committee VARCHAR(200),
    changes_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_current BOOLEAN DEFAULT false
);

-- Create indexes for bill_versions
CREATE INDEX IF NOT EXISTS ix_bill_versions_bill_id ON bill_versions(bill_id);
CREATE INDEX IF NOT EXISTS ix_bill_versions_is_current ON bill_versions(is_current);
CREATE INDEX IF NOT EXISTS idx_bill_version_current ON bill_versions(bill_id, is_current);
CREATE INDEX IF NOT EXISTS idx_bill_version_date ON bill_versions(bill_id, created_at);

-- Create bill_keyword_matches table
CREATE TABLE IF NOT EXISTS bill_keyword_matches (
    id SERIAL PRIMARY KEY,
    bill_id INTEGER NOT NULL REFERENCES bills(id),
    keyword_id INTEGER NOT NULL REFERENCES keywords(id),
    match_count INTEGER DEFAULT 1,
    match_locations TEXT,
    confidence_score FLOAT,
    context_snippet TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for bill_keyword_matches
CREATE INDEX IF NOT EXISTS ix_bill_keyword_matches_bill_id ON bill_keyword_matches(bill_id);
CREATE INDEX IF NOT EXISTS ix_bill_keyword_matches_keyword_id ON bill_keyword_matches(keyword_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_bill_keyword_unique ON bill_keyword_matches(bill_id, keyword_id);
CREATE INDEX IF NOT EXISTS idx_bill_keyword_score ON bill_keyword_matches(bill_id, confidence_score);

-- Create alerts table
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    bill_id INTEGER NOT NULL REFERENCES bills(id),
    alert_type VARCHAR(50),
    message TEXT,
    is_read BOOLEAN DEFAULT false,
    severity VARCHAR(20) DEFAULT 'medium',
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP
);

-- Create indexes for alerts
CREATE INDEX IF NOT EXISTS ix_alerts_user_id ON alerts(user_id);
CREATE INDEX IF NOT EXISTS ix_alerts_bill_id ON alerts(bill_id);
CREATE INDEX IF NOT EXISTS ix_alerts_alert_type ON alerts(alert_type);
CREATE INDEX IF NOT EXISTS ix_alerts_is_read ON alerts(is_read);
CREATE INDEX IF NOT EXISTS ix_alerts_triggered_at ON alerts(triggered_at);
CREATE INDEX IF NOT EXISTS idx_user_alerts_unread ON alerts(user_id, is_read, triggered_at);
CREATE INDEX IF NOT EXISTS idx_bill_alerts ON alerts(bill_id, alert_type);

-- Create impact_analyses table
CREATE TABLE IF NOT EXISTS impact_analyses (
    id SERIAL PRIMARY KEY,
    bill_id INTEGER NOT NULL REFERENCES bills(id),
    analysis_version VARCHAR(20) DEFAULT '1.0',
    impact_score FLOAT,
    impact_category VARCHAR(100),
    summary TEXT,
    detailed_analysis TEXT,
    key_provisions TEXT,
    affected_areas TEXT,
    recommendation TEXT,
    confidence_score FLOAT,
    model_used VARCHAR(100),
    analysis_prompt TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_user_id INTEGER REFERENCES users(id)
);

-- Create indexes for impact_analyses
CREATE INDEX IF NOT EXISTS ix_impact_analyses_bill_id ON impact_analyses(bill_id);
CREATE INDEX IF NOT EXISTS ix_impact_analyses_impact_score ON impact_analyses(impact_score);
CREATE INDEX IF NOT EXISTS idx_impact_score ON impact_analyses(impact_score);
CREATE INDEX IF NOT EXISTS idx_impact_category ON impact_analyses(impact_category);
CREATE INDEX IF NOT EXISTS idx_bill_impact_latest ON impact_analyses(bill_id, created_at);

-- Create a trigger to update the updated_at column in bills table
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply the trigger to bills table
DROP TRIGGER IF EXISTS update_bills_updated_at ON bills;
CREATE TRIGGER update_bills_updated_at
    BEFORE UPDATE ON bills
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Insert default admin user (password is 'admin123' hashed with bcrypt)
INSERT INTO users (email, hashed_password, full_name, role, is_active, is_verified)
VALUES ('admin@snflegtracker.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewYWPs0W9.f0.9N.', 'System Administrator', 'admin', true, true)
ON CONFLICT (email) DO NOTHING;

-- Verify table creation
SELECT
    'users' as table_name, COUNT(*) as record_count FROM users
UNION ALL
SELECT
    'bills' as table_name, COUNT(*) as record_count FROM bills
UNION ALL
SELECT
    'keywords' as table_name, COUNT(*) as record_count FROM keywords
UNION ALL
SELECT
    'bill_versions' as table_name, COUNT(*) as record_count FROM bill_versions
UNION ALL
SELECT
    'bill_keyword_matches' as table_name, COUNT(*) as record_count FROM bill_keyword_matches
UNION ALL
SELECT
    'alerts' as table_name, COUNT(*) as record_count FROM alerts
UNION ALL
SELECT
    'impact_analyses' as table_name, COUNT(*) as record_count FROM impact_analyses
ORDER BY table_name;

-- Display success message
SELECT 'Database tables created successfully!' as status;