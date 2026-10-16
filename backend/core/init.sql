-- Sentinel Verilənlər Bazası Sxemi

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Bank konfiqurasiyaları
CREATE TABLE IF NOT EXISTS banks (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    base_url VARCHAR(500) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Test ssenariləri kataloqu
CREATE TABLE IF NOT EXISTS test_scenarios (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(100) NOT NULL,  -- accounts, balances, transactions, payments, consent
    endpoint VARCHAR(500) NOT NULL,
    method VARCHAR(10) NOT NULL,
    request_body JSONB,
    expected_status INT,
    required_fields TEXT[],
    description TEXT,
    is_active BOOLEAN DEFAULT true
);

-- Test nəticələri
CREATE TABLE IF NOT EXISTS test_results (
    id SERIAL PRIMARY KEY,
    run_id UUID DEFAULT uuid_generate_v4(),
    bank_id VARCHAR(50) REFERENCES banks(id),
    scenario_id INT REFERENCES test_scenarios(id),
    status_code INT,
    response_body JSONB,
    response_headers JSONB,
    latency_ms FLOAT,
    is_compliant BOOLEAN,
    compliance_issues JSONB,
    tested_at TIMESTAMPTZ DEFAULT NOW()
);

-- Gecikmə ölçümləri (time-series)
CREATE TABLE IF NOT EXISTS latency_metrics (
    id SERIAL PRIMARY KEY,
    bank_id VARCHAR(50) REFERENCES banks(id),
    endpoint VARCHAR(500),
    latency_ms FLOAT NOT NULL,
    p50 FLOAT,
    p95 FLOAT,
    p99 FLOAT,
    measured_at TIMESTAMPTZ DEFAULT NOW()
);

-- Uptime qeydləri
CREATE TABLE IF NOT EXISTS uptime_records (
    id SERIAL PRIMARY KEY,
    bank_id VARCHAR(50) REFERENCES banks(id),
    is_up BOOLEAN NOT NULL,
    status_code INT,
    error_message TEXT,
    checked_at TIMESTAMPTZ DEFAULT NOW()
);

-- Drift hadisələri
CREATE TABLE IF NOT EXISTS drift_events (
    id SERIAL PRIMARY KEY,
    bank_id VARCHAR(50) REFERENCES banks(id),
    endpoint VARCHAR(500),
    drift_type VARCHAR(100),  -- field_missing, type_changed, format_changed, structure_changed
    field_path TEXT,
    expected_value TEXT,
    actual_value TEXT,
    severity VARCHAR(20),  -- critical, warning, info
    baseline_snapshot JSONB,
    current_snapshot JSONB,
    detected_at TIMESTAMPTZ DEFAULT NOW()
);

-- Schema snapshot-ları (baseline üçün)
CREATE TABLE IF NOT EXISTS schema_snapshots (
    id SERIAL PRIMARY KEY,
    bank_id VARCHAR(50) REFERENCES banks(id),
    endpoint VARCHAR(500),
    snapshot JSONB NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    captured_at TIMESTAMPTZ DEFAULT NOW()
);

-- Banka reytinqləri
CREATE TABLE IF NOT EXISTS bank_scores (
    id SERIAL PRIMARY KEY,
    bank_id VARCHAR(50) REFERENCES banks(id),
    compliance_score FLOAT,
    reliability_score FLOAT,
    latency_score FLOAT,
    security_score FLOAT,
    total_score FLOAT,
    score_breakdown JSONB,
    calculated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Təhlükəsizlik skan nəticələri
CREATE TABLE IF NOT EXISTS security_scans (
    id SERIAL PRIMARY KEY,
    bank_id VARCHAR(50) REFERENCES banks(id),
    tls_version VARCHAR(20),
    has_hsts BOOLEAN,
    has_csp BOOLEAN,
    has_xcontent_type BOOLEAN,
    has_xframe_options BOOLEAN,
    has_sca_redirect BOOLEAN,
    cert_days_remaining INT,
    issues JSONB,
    score FLOAT,
    scanned_at TIMESTAMPTZ DEFAULT NOW()
);

-- Anomaliya bayraqları
CREATE TABLE IF NOT EXISTS anomalies (
    id SERIAL PRIMARY KEY,
    bank_id VARCHAR(50) REFERENCES banks(id),
    anomaly_type VARCHAR(100),  -- latency_spike, error_burst, schema_change
    severity VARCHAR(20),
    metric_value FLOAT,
    baseline_value FLOAT,
    deviation_factor FLOAT,
    is_resolved BOOLEAN DEFAULT false,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

-- İlkin bank məlumatları
INSERT INTO banks (id, name, base_url) VALUES
    ('bank_a', 'TBC Bank (Compliant)', 'http://bank-a:8000'),
    ('bank_b', 'Bank of Georgia (Drift)', 'http://bank-b:8000'),
    ('bank_c', 'Liberty Bank (Unstable)', 'http://bank-c:8000')
ON CONFLICT (id) DO NOTHING;

-- Test ssenariləri
INSERT INTO test_scenarios (name, category, endpoint, method, expected_status, required_fields, description) VALUES
    ('Get Account List', 'accounts', '/v1/accounts', 'GET', 200, ARRAY['accounts'], 'Bütün hesabların siyahısı'),
    ('Get Single Account', 'accounts', '/v1/accounts/acc-001', 'GET', 200, ARRAY['resourceId','iban','currency'], 'Tək hesab detalları'),
    ('Get Balances', 'balances', '/v1/accounts/acc-001/balances', 'GET', 200, ARRAY['balances'], 'Hesab balansları'),
    ('Get Transactions', 'transactions', '/v1/accounts/acc-001/transactions', 'GET', 200, ARRAY['transactions'], 'Tranzaksiya tarixçəsi'),
    ('Initiate Payment', 'payments', '/v1/payments/sepa-credit-transfers', 'POST', 201, ARRAY['paymentId','transactionStatus'], 'Ödəniş başlatma'),
    ('Create Consent', 'consent', '/v1/consents', 'POST', 201, ARRAY['consentId','consentStatus'], 'Razılıq yaratma'),
    ('Get Consent Status', 'consent', '/v1/consents/cns-test/status', 'GET', 200, ARRAY['consentStatus'], 'Razılıq statusu')
ON CONFLICT DO NOTHING;

-- İndekslər
CREATE INDEX IF NOT EXISTS idx_test_results_bank ON test_results(bank_id, tested_at DESC);
CREATE INDEX IF NOT EXISTS idx_latency_metrics_bank ON latency_metrics(bank_id, measured_at DESC);
CREATE INDEX IF NOT EXISTS idx_uptime_bank ON uptime_records(bank_id, checked_at DESC);
CREATE INDEX IF NOT EXISTS idx_drift_bank ON drift_events(bank_id, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_anomalies_bank ON anomalies(bank_id, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_bank_scores_bank ON bank_scores(bank_id, calculated_at DESC);
