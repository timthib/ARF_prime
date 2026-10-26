DROP TABLE IF EXISTS d0_meta;
DROP TABLE IF EXISTS d0_score;
DROP TABLE IF EXISTS d0_curve;
DROP TABLE IF EXISTS d0_framework;
DROP TABLE IF EXISTS d0_gap;
DROP TABLE IF EXISTS d0_rank;
DROP TABLE IF EXISTS d0_rank_point;
DROP TABLE IF EXISTS d0_season;
DROP TABLE IF EXISTS d0_view_log;

CREATE TABLE d0_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE d0_score (
    artifact_sha256 TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    framework_id TEXT NOT NULL,
    seed INTEGER NOT NULL,
    k INTEGER NOT NULL,
    b REAL NOT NULL,
    e_mae REAL,
    e_rmse REAL,
    s0 REAL,
    n_origins INTEGER,
    s0_djf REAL,
    s0_mam REAL,
    s0_jja REAL,
    s0_son REAL,
    scorer_version TEXT,
    status TEXT
);

CREATE TABLE d0_curve (
    framework_id TEXT NOT NULL,
    seed INTEGER NOT NULL,
    b REAL NOT NULL,
    s0 REAL NOT NULL,
    PRIMARY KEY (framework_id, seed, b)
);

CREATE TABLE d0_framework (
    framework_id TEXT PRIMARY KEY,
    k INTEGER NOT NULL,
    j_sel REAL NOT NULL,
    j_sel_min REAL NOT NULL,
    j_sel_max REAL NOT NULL,
    j0_median REAL NOT NULL,
    j0_seed1 REAL NOT NULL,
    j0_seed2 REAL NOT NULL,
    j0_seed3 REAL NOT NULL,
    j0_min REAL NOT NULL,
    j0_max REAL NOT NULL,
    n_seeds INTEGER NOT NULL
);

CREATE TABLE d0_gap (
    k INTEGER PRIMARY KEY,
    vstar_framework_id TEXT NOT NULL,
    j_sel REAL NOT NULL,
    j0 REAL NOT NULL,
    g_k REAL NOT NULL,
    g_k_corrected REAL NOT NULL
);

CREATE TABLE d0_rank (
    k INTEGER PRIMARY KEY,
    n INTEGER NOT NULL,
    spearman REAL,
    kendall REAL,
    elected_framework_id TEXT,
    elected_rank INTEGER,
    p_win REAL,
    regret REAL,
    rel_regret REAL
);

CREATE TABLE d0_rank_point (
    k INTEGER NOT NULL,
    framework_id TEXT NOT NULL,
    j_sel REAL NOT NULL,
    j0 REAL NOT NULL,
    rank_sel INTEGER NOT NULL,
    rank_0 INTEGER NOT NULL,
    n_seeds INTEGER NOT NULL,
    j_sel_min REAL NOT NULL,
    j_sel_max REAL NOT NULL,
    j0_min REAL NOT NULL,
    j0_max REAL NOT NULL,
    PRIMARY KEY (k, framework_id)
);

CREATE TABLE d0_season (
    framework_id TEXT NOT NULL,
    k INTEGER NOT NULL,
    djf REAL NOT NULL,
    mam REAL NOT NULL,
    jja REAL NOT NULL,
    son REAL NOT NULL,
    PRIMARY KEY (framework_id, k)
);

CREATE TABLE d0_view_log (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    page TEXT NOT NULL,
    params TEXT,
    design_hash TEXT,
    last_event_id_seen TEXT,
    prev_hash TEXT NOT NULL,
    row_hash TEXT NOT NULL
);
