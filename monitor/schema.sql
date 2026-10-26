DROP TABLE IF EXISTS run_header;
DROP TABLE IF EXISTS meta_step;
DROP TABLE IF EXISTS l1_run;
DROP TABLE IF EXISTS framework;
DROP TABLE IF EXISTS model;
DROP TABLE IF EXISTS eval_event;
DROP TABLE IF EXISTS ledger;
DROP TABLE IF EXISTS gpu_sample;
DROP TABLE IF EXISTS log_line;
DROP TABLE IF EXISTS kill_event;
DROP TABLE IF EXISTS d0_outbox;

CREATE TABLE run_header (
    meta_run_id TEXT PRIMARY KEY,
    arm INTEGER NOT NULL,
    arm_name TEXT NOT NULL,
    replicate INTEGER NOT NULL,
    phase TEXT NOT NULL,
    topology TEXT NOT NULL,
    k_horizon INTEGER NOT NULL,
    b_gpu REAL NOT NULL,
    b_step_gpu REAL NOT NULL,
    b_step_tokens REAL NOT NULL,
    design_hash TEXT NOT NULL,
    design_version INTEGER NOT NULL,
    design_ok INTEGER NOT NULL,
    changed_after_d0_view INTEGER NOT NULL,
    last_d0_look_ts TEXT,
    as_of TEXT NOT NULL,
    scorer_state TEXT NOT NULL,
    kappa REAL,
    ts TEXT NOT NULL
);

CREATE TABLE meta_step (
    id INTEGER PRIMARY KEY,
    meta_run_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    design_hash TEXT NOT NULL,
    k INTEGER NOT NULL,
    t_start TEXT,
    t_end TEXT,
    budget_gpu_h REAL,
    budget_tokens REAL,
    spent_gpu_h REAL,
    spent_tokens REAL,
    l0_s REAL,
    l1_s REAL,
    hypothesis_id TEXT,
    hypothesis_text TEXT,
    status TEXT NOT NULL,
    phase TEXT NOT NULL,
    tamper_reason TEXT,
    parent_framework_id TEXT,
    edit_json TEXT,
    UNIQUE (meta_run_id, k)
);

CREATE TABLE l1_run (
    id INTEGER PRIMARY KEY,
    meta_run_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    design_hash TEXT NOT NULL,
    run_id TEXT NOT NULL UNIQUE,
    k INTEGER NOT NULL,
    framework_id TEXT NOT NULL,
    parent_framework_id TEXT,
    seed INTEGER NOT NULL,
    alloc_gpu_h REAL,
    alloc_tokens REAL,
    status TEXT NOT NULL,
    kill_reason TEXT,
    phase TEXT NOT NULL,
    kappa REAL,
    gpu_h_used REAL,
    tokens_used REAL
);

CREATE TABLE framework (
    id INTEGER PRIMARY KEY,
    meta_run_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    design_hash TEXT NOT NULL,
    framework_id TEXT NOT NULL,
    k_first INTEGER NOT NULL,
    parent_framework_id TEXT,
    level1_snapshot TEXT,
    rules_json TEXT,
    edit_json TEXT,
    n_seeds INTEGER,
    j_sel_median REAL,
    j_sel_seed1 REAL,
    j_sel_seed2 REAL,
    j_sel_seed3 REAL,
    ci_lo REAL,
    ci_hi REAL,
    n_killed INTEGER,
    elected INTEGER NOT NULL DEFAULT 0,
    hypothesis_text TEXT,
    UNIQUE (meta_run_id, framework_id)
);

CREATE TABLE model (
    model_id TEXT PRIMARY KEY,
    meta_run_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    design_hash TEXT NOT NULL,
    run_id TEXT NOT NULL,
    framework_id TEXT NOT NULL,
    branch_id TEXT,
    parent_model_id TEXT,
    operator TEXT,
    seed INTEGER NOT NULL,
    b_created REAL NOT NULL,
    u REAL,
    status TEXT NOT NULL,
    artifact_path TEXT,
    artifact_sha256 TEXT,
    is_ideal_model INTEGER NOT NULL DEFAULT 0,
    seq INTEGER NOT NULL
);

CREATE TABLE eval_event (
    id INTEGER PRIMARY KEY,
    meta_run_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    design_hash TEXT NOT NULL,
    run_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    b REAL NOT NULL,
    split TEXT NOT NULL CHECK (split = 'sel'),
    s REAL NOT NULL,
    e_mae REAL,
    trigger TEXT
);

CREATE TABLE ledger (
    id INTEGER PRIMARY KEY,
    meta_run_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    design_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    run_id TEXT,
    k INTEGER NOT NULL,
    gpu_h REAL NOT NULL,
    tokens_in INTEGER NOT NULL,
    tokens_out INTEGER NOT NULL,
    cum_gpu_h REAL NOT NULL,
    cum_tokens INTEGER NOT NULL
);

CREATE TABLE gpu_sample (
    id INTEGER PRIMARY KEY,
    meta_run_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    design_hash TEXT NOT NULL,
    run_id TEXT NOT NULL,
    k INTEGER NOT NULL,
    model_id TEXT,
    b REAL NOT NULL,
    gpu_busy REAL NOT NULL
);

CREATE TABLE log_line (
    id INTEGER PRIMARY KEY,
    meta_run_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    design_hash TEXT NOT NULL,
    run_id TEXT,
    k INTEGER NOT NULL,
    role TEXT,
    model_id TEXT,
    message TEXT NOT NULL
);

CREATE TABLE kill_event (
    id INTEGER PRIMARY KEY,
    meta_run_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    design_hash TEXT NOT NULL,
    run_id TEXT,
    framework_id TEXT,
    k INTEGER NOT NULL,
    reason TEXT NOT NULL
);

CREATE TABLE d0_outbox (
    event_id TEXT PRIMARY KEY,
    meta_run_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    design_hash TEXT NOT NULL,
    type TEXT NOT NULL,
    k INTEGER NOT NULL,
    run_id TEXT,
    model_id TEXT,
    artifact_path TEXT,
    artifact_sha256 TEXT,
    hmac TEXT
);

CREATE INDEX idx_step_k ON meta_step (meta_run_id, k);
CREATE INDEX idx_l1_fw ON l1_run (meta_run_id, framework_id);
CREATE INDEX idx_model_run ON model (run_id, seq);
CREATE INDEX idx_eval_run ON eval_event (run_id, b);
CREATE INDEX idx_log_k ON log_line (meta_run_id, k);
