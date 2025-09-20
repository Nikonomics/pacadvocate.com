-- SNFLegTracker Keywords Seed Script
-- This script populates the keywords table with SNF-related terms

-- Insert SNF Core Terms
INSERT INTO keywords (term, category, importance_weight, synonyms, is_active) VALUES
('skilled nursing facility', 'SNF', 2.0, '["SNF", "nursing home", "long-term care facility", "LTC facility"]', true),
('skilled nursing', 'SNF', 1.8, '["nursing care", "skilled care", "SNF care"]', true),
('nursing home', 'SNF', 1.9, '["SNF", "skilled nursing facility", "long-term care facility"]', true),
('long-term care', 'SNF', 1.7, '["LTC", "extended care", "chronic care"]', true)
ON CONFLICT (term) DO NOTHING;

-- Insert Medicare & Reimbursement Terms
INSERT INTO keywords (term, category, importance_weight, synonyms, is_active) VALUES
('Medicare Part A', 'Medicare', 1.9, '["Medicare A", "Part A", "hospital insurance"]', true),
('Medicare', 'Medicare', 1.8, '["CMS", "Centers for Medicare & Medicaid Services"]', true),
('Medicaid', 'Medicaid', 1.8, '["state Medicaid", "Medicaid program"]', true),
('reimbursement', 'Financial', 1.6, '["payment", "compensation", "funding"]', true)
ON CONFLICT (term) DO NOTHING;

-- Insert PDPM & MDS Terms
INSERT INTO keywords (term, category, importance_weight, synonyms, is_active) VALUES
('PDPM', 'PDPM', 2.0, '["Patient Driven Payment Model", "patient-driven payment model"]', true),
('Patient Driven Payment Model', 'PDPM', 2.0, '["PDPM"]', true),
('MDS', 'Assessment', 1.8, '["Minimum Data Set", "MDS 3.0", "resident assessment"]', true),
('Minimum Data Set', 'Assessment', 1.8, '["MDS", "MDS 3.0"]', true)
ON CONFLICT (term) DO NOTHING;

-- Insert Staffing & Quality Terms
INSERT INTO keywords (term, category, importance_weight, synonyms, is_active) VALUES
('staffing ratios', 'Staffing', 1.9, '["nurse-to-patient ratio", "staffing requirements", "minimum staffing"]', true),
('nurse staffing', 'Staffing', 1.8, '["nursing staff", "RN staffing", "LPN staffing"]', true),
('CNA', 'Staffing', 1.5, '["certified nursing assistant", "nursing assistant", "aide"]', true),
('registered nurse', 'Staffing', 1.7, '["RN", "staff nurse", "charge nurse"]', true),
('licensed practical nurse', 'Staffing', 1.6, '["LPN", "LVN", "licensed vocational nurse"]', true)
ON CONFLICT (term) DO NOTHING;

-- Insert Quality Measures
INSERT INTO keywords (term, category, importance_weight, synonyms, is_active) VALUES
('star rating', 'Quality', 1.7, '["five-star rating", "CMS star rating", "quality rating"]', true),
('quality measures', 'Quality', 1.6, '["quality indicators", "performance measures", "QMs"]', true),
('deficiency', 'Quality', 1.8, '["citation", "violation", "non-compliance"]', true),
('survey', 'Quality', 1.5, '["inspection", "state survey", "health inspection"]', true)
ON CONFLICT (term) DO NOTHING;

-- Insert Financial & Operations
INSERT INTO keywords (term, category, importance_weight, synonyms, is_active) VALUES
('cost reporting', 'Financial', 1.4, '["cost report", "Medicare cost report"]', true),
('bad debt', 'Financial', 1.3, '["uncollectible debt", "unpaid bills"]', true),
('charity care', 'Financial', 1.2, '["free care", "uncompensated care"]', true),
('admission', 'Operations', 1.4, '["intake", "enrollment", "admission process"]', true),
('discharge', 'Operations', 1.4, '["release", "transition", "discharge planning"]', true)
ON CONFLICT (term) DO NOTHING;

-- Insert Regulatory & Compliance
INSERT INTO keywords (term, category, importance_weight, synonyms, is_active) VALUES
('42 CFR', 'Regulatory', 1.8, '["Code of Federal Regulations", "CFR 42"]', true),
('483', 'Regulatory', 1.9, '["42 CFR 483", "nursing home regulations"]', true),
('F-tag', 'Regulatory', 1.7, '["F tag", "regulatory tag", "compliance tag"]', true),
('life safety', 'Safety', 1.6, '["fire safety", "emergency preparedness", "safety requirements"]', true)
ON CONFLICT (term) DO NOTHING;

-- Insert COVID-19 & Pandemic
INSERT INTO keywords (term, category, importance_weight, synonyms, is_active) VALUES
('COVID-19', 'Pandemic', 1.8, '["coronavirus", "pandemic", "SARS-CoV-2"]', true),
('infection control', 'Safety', 1.7, '["infection prevention", "disease control", "IPC"]', true),
('PPE', 'Safety', 1.5, '["personal protective equipment", "protective equipment"]', true)
ON CONFLICT (term) DO NOTHING;

-- Insert Technology & Innovation
INSERT INTO keywords (term, category, importance_weight, synonyms, is_active) VALUES
('telehealth', 'Technology', 1.4, '["telemedicine", "remote care", "virtual care"]', true),
('electronic health record', 'Technology', 1.3, '["EHR", "electronic medical record", "EMR"]', true)
ON CONFLICT (term) DO NOTHING;

-- Insert Workforce & Training
INSERT INTO keywords (term, category, importance_weight, synonyms, is_active) VALUES
('workforce', 'Staffing', 1.5, '["staff", "employees", "personnel"]', true),
('training', 'Education', 1.3, '["education", "competency", "certification"]', true),
('turnover', 'Staffing', 1.6, '["staff turnover", "employee turnover", "retention"]', true)
ON CONFLICT (term) DO NOTHING;

-- Display keyword statistics
SELECT
    category,
    COUNT(*) as keyword_count,
    ROUND(AVG(importance_weight), 2) as avg_importance
FROM keywords
WHERE is_active = true
GROUP BY category
ORDER BY keyword_count DESC;

-- Display total count
SELECT COUNT(*) as total_keywords FROM keywords WHERE is_active = true;

SELECT 'Keywords seeded successfully!' as status;