import { useEffect, useState } from "react";
import { dur, gloss, gpu, jfmt, sendCommand, tok, usePoll } from "./api";
import { Shell, useNav } from "./shell";
import {
  BurnChart,
  FrameworkTree,
  GpuChart,
  JSelChart,
  ScoreChart,
  ScatterU,
  SearchTree,
  SEED_COLORS,
  Sparkline,
  WallChart,
} from "./charts";

const COPY = {
  materialise_split: {
    title: "Materialise the D1 split",
    body: "The core writes D1 fit for the agents and keeps the selection labels.",
  },
  run_baselines: {
    title: "Run the baseline pool",
    body: "Train the reference models on D1 fit. The core keeps the scores.",
  },
  start_pilot: {
    title: "Start a pilot meta-run",
    body: "Five meta-steps on D1. Refused while the scorer is up. The pilot does not change K.",
  },
  freeze: {
    title: "Freeze the design",
    body: "The core tags prereg-v1 when the tree is clean. K stays the stored horizon. Freeze does not start the scorer.",
  },
  bump: {
    title: "Bump the design",
    body: "A new design version. If a D0 page has been opened since the last freeze, the core records that.",
    needsReason: true,
  },
  start_meta_run: {
    title: "Start a meta-run",
    body: "One arm, from the initial framework, for exactly K steps. There is no stop and no extension.",
    picksArm: true,
  },
  kill_framework: {
    title: "Kill this framework",
    body: "This stops the framework inside the current step and releases its unspent share. The meta-run continues. The step still counts.",
    needsReason: true,
  },
  start_phase2: {
    title: "Start Phase 2",
    body: "The elected framework alone, budget κB, one fresh seed, one model.",
  },
  restart_meta_run: {
    title: "Restart from scratch",
    body: "A crashed meta-run is replaced by a new run id. The old run is not resumed.",
  },
};

function CommandButton({ verb, payload, extraReason, note, label }) {
  const { commands } = useNav();
  const command = commands.find((item) => item.verb === verb);
  const copy = COPY[verb];
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [arm, setArm] = useState(6);
  const [result, setResult] = useState(null);
  if (!command || !copy) return null;
  const blocked = !command.available || Boolean(extraReason);
  const why = [!command.available ? command.reason : "", extraReason, note].filter(Boolean).join(" ");
  async function confirm() {
    const body = { ...(payload || {}) };
    if (copy.needsReason) body.reason = reason.trim();
    if (copy.picksArm) body.arm = arm;
    const response = await sendCommand(verb, body);
    setResult(response);
    setOpen(false);
  }
  return (
    <div className="cmd">
      <button type="button" className="btn" disabled={blocked} onClick={() => setOpen(true)}>
        {label || copy.title}
      </button>
      {why && <span className="muted">{why}</span>}
      {result && (
        <span className={result.status === "accepted" ? "ok-ink" : "bad"}>
          {result.status}
          {result.reason ? ` — ${result.reason}` : ""}
          {result.event_id ? ` · ${result.event_id.slice(0, 8)}` : ""}
        </span>
      )}
      {open && (
        <div className="modal-back" onClick={() => setOpen(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <h3>{copy.title}</h3>
            <p>{copy.body}</p>
            {copy.picksArm && (
              <label>
                Arm
                <select value={arm} onChange={(event) => setArm(Number(event.target.value))}>
                  {[1, 2, 3, 4, 5, 6].map((number) => (
                    <option key={number} value={number}>
                      {number}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {copy.needsReason && (
              <textarea
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                placeholder="Reason"
              />
            )}
            <div className="row">
              <button type="button" className="btn" onClick={() => setOpen(false)}>
                Back
              </button>
              <button
                type="button"
                className="btn"
                disabled={copy.needsReason && !reason.trim()}
                onClick={confirm}
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CellButton({ cell, onOpen }) {
  const open = cell.meta_run_id ? () => onOpen(cell.meta_run_id) : undefined;
  return (
    <button type="button" className={`cell-card ${cell.state}`} disabled={!open} onClick={open}>
      <span className="kicker">r{cell.replicate}</span>
      <strong>{cell.state.replace("_", " ")}</strong>
      {cell.meta_run_id && (
        <>
          <span className="num">
            {cell.k}/{cell.K}
          </span>
          <span className="num">{jfmt(cell.j_sel)}</span>
          <span className="muted">
            {gpu(cell.gpu_h)} GPU-h · {tok(cell.tokens)} · {dur(cell.wall_s)}
          </span>
        </>
      )}
    </button>
  );
}

export function Study() {
  const { go } = useNav();
  const { data, error } = usePoll("/api/study", 10000);
  const [report, setReport] = useState(null);
  if (!data) {
    return (
      <Shell strip={null}>
        <p className="empty">{error || "Reading the event log…"}</p>
      </Shell>
    );
  }
  const pilotBlocked = data.scorer?.state && data.scorer.state !== "stopped" ? "refused while the scorer is up" : "";
  const freezeNote = data.freeze?.dirty
    ? `Would tag ${data.freeze.tag}. The working tree is dirty (${data.freeze.dirty_count ?? "unknown"} paths).`
    : `Would tag ${data.freeze.tag}. The working tree is clean.`;
  return (
    <Shell strip={data.strip}>
      <h1>Study</h1>
      <p className="lede">
        The campaign, then the meta-run that is in progress. Trigger buttons stay off until the core command exists.
      </p>
      <ol className="pipeline">
        {data.stages.map((stage) => (
          <li key={stage.id} className={`stage ${stage.state}`}>
            <span className="kicker">{stage.state.replace("_", " ")}</span>
            <strong>{stage.label}</strong>
            {stage.detail && <span className="muted">{stage.detail}</span>}
          </li>
        ))}
      </ol>
      <div className="commands">
        <CommandButton verb="materialise_split" />
        <CommandButton verb="run_baselines" />
        <CommandButton verb="start_pilot" extraReason={pilotBlocked} />
        <CommandButton verb="freeze" note={freezeNote} />
        <CommandButton verb="bump" />
        <CommandButton verb="start_meta_run" />
        <CommandButton verb="start_phase2" />
        <CommandButton verb="restart_meta_run" payload={{ meta_run_id: data.live_meta_run_id || "" }} />
        <button
          type="button"
          className="btn"
          onClick={async () => {
            const response = await fetch("/api/pilot-report");
            setReport(await response.json());
          }}
        >
          Open the pilot report
        </button>
      </div>
      {report && (
        <section className="report">
          <h2>Pilot report</h2>
          {!report.available && <p>No pilot report has been written.</p>}
          {report.available && (
            <>
              <p>{report.note}</p>
              <p className="num">
                Section 7.3 would choose {report.k_rule}. The stored horizon is {report.experiment_k}.
              </p>
              <p className="muted">
                J_sel curve {report.j_sel?.map((value) => Number(value).toFixed(2)).join(" → ")} · seed noise{" "}
                {report.sigma_seed} · GPU-h per L1 run {report.gpu_h_per_l1_run} · tokens per L0 step{" "}
                {tok(report.tokens_per_l0_step)} · wall {dur(report.wall_clock_per_step_s)} per step · tamper rate{" "}
                {report.tamper_rate}
              </p>
            </>
          )}
        </section>
      )}
      <h2>Phase 1</h2>
      <div className="arm-grid">
        {data.arms.map((arm) => (
          <div key={arm.arm} className="arm-row">
            <div className="arm-name">
              <span className="kicker">Arm {arm.arm}</span>
              <strong>{arm.name}</strong>
            </div>
            {arm.cells.map((cell) => (
              <CellButton key={cell.replicate} cell={cell} onOpen={(id) => go(`/runs/${encodeURIComponent(id)}`)} />
            ))}
          </div>
        ))}
      </div>
      <h2>Ablations</h2>
      <div className="arm-grid">
        {data.ablations.map((arm) => (
          <div key={arm.id} className="arm-row">
            <div className="arm-name">
              <span className="kicker">{arm.id}</span>
              <strong>{arm.name}</strong>
            </div>
            {arm.cells.map((cell) => (
              <CellButton key={cell.replicate} cell={cell} onOpen={(id) => go(`/runs/${encodeURIComponent(id)}`)} />
            ))}
          </div>
        ))}
      </div>
      {data.pilot_runs?.length > 0 && (
        <>
          <h2>Pilot runs</h2>
          <div className="pilot-row">
            {data.pilot_runs.map((cell) => (
              <CellButton key={cell.meta_run_id} cell={cell} onOpen={(id) => go(`/runs/${encodeURIComponent(id)}`)} />
            ))}
          </div>
        </>
      )}
    </Shell>
  );
}

function Slot({ slot, onOpen }) {
  return (
    <button type="button" className={`slot ${slot.slot} ${slot.status || ""}`} onClick={() => onOpen(slot.k)}>
      <span className="kicker">
        k {slot.k}
        {slot.status ? ` · ${slot.status}` : " · later"}
      </span>
      {slot.slot === "future" && (
        <>
          <strong>Not started</strong>
          <span className="num">{gpu(slot.budget_gpu_h)} GPU-h</span>
          <span className="num">{tok(slot.budget_tokens)} tokens</span>
          <span className="muted">Fresh step budget. Unspent budget is not carried in.</span>
        </>
      )}
      {slot.status === "rejected" && (
        <>
          <strong className="bad">Rejected</strong>
          <span className="clamp">{slot.tamper_reason}</span>
          <span className="num">0 GPU-h · 0 tokens</span>
          <span className="muted">The step is consumed.</span>
        </>
      )}
      {slot.slot === "done" && slot.status !== "rejected" && (
        <>
          <span className="clamp">{slot.hypothesis || "Initial framework."}</span>
          <strong className="num" title={gloss.j_sel}>
            J_sel {jfmt(slot.j_sel_median)}
          </strong>
          <span className="muted num">{slot.seeds.map((value) => Number(value).toFixed(3)).join("  ")}</span>
          <span className="muted">
            {gpu(slot.gpu_h)} GPU-h · {tok(slot.tokens)} · {dur(slot.duration_s)}
            {slot.n_kills ? ` · ${slot.n_kills} kill` : ""}
          </span>
          {slot.parent_framework_id && <span className="muted">parent {slot.parent_framework_id}</span>}
          {slot.confirmed != null && (
            <span className={slot.confirmed ? "ok-ink" : "bad"}>{slot.confirmed ? "J_sel rose" : "J_sel did not rise"}</span>
          )}
        </>
      )}
      {slot.slot === "live" && (
        <>
          <span className="clamp">{slot.hypothesis}</span>
          <div className="tracks">
            {slot.progress.map((row) => (
              <div key={row.seed} className="track-row">
                <span className="num">s{row.seed}</span>
                <div className="track">
                  <div style={{ width: `${Math.min(100, (100 * row.b) / row.B)}%` }} />
                </div>
                <span className="num">
                  {gpu(row.b)}/{gpu(row.B)}
                </span>
              </div>
            ))}
          </div>
          <Sparkline points={slot.sparkline} />
          {slot.last_log && <span className="clamp muted">{slot.last_log}</span>}
        </>
      )}
    </button>
  );
}

export function MetaLoop({ id }) {
  const { go } = useNav();
  const { data, error } = usePoll(`/api/runs/${encodeURIComponent(id)}`, 2000);
  if (!data) {
    return (
      <Shell strip={null}>
        <p className="empty">{error || "Reading the event log…"}</p>
      </Shell>
    );
  }
  const openStep = (k) => go(`/runs/${encodeURIComponent(id)}/steps/${k}`);
  const openFw = (fid) => go(`/runs/${encodeURIComponent(id)}/frameworks/${encodeURIComponent(fid)}`);
  return (
    <Shell strip={data.strip}>
      <header className="page-head">
        <h1>
          {data.arm_name} · replicate {data.replicate}
        </h1>
        <p className="lede">
          {data.phase} · {data.topology} · run clock {data.strip.as_of}. Closing this page does not stop the run.
        </p>
      </header>
      <div className="charts-3">
        <figure>
          <figcaption title={gloss.j_sel}>J_sel · median, seeds, running max</figcaption>
          <JSelChart series={data.j_series} onPick={openStep} />
        </figure>
        <figure>
          <figcaption>GPU-h and tokens, share of the cap</figcaption>
          <BurnChart points={data.burn} />
          <p className="legend">
            <i className="swatch gpu" /> GPU-h <i className="swatch tok" /> tokens
          </p>
        </figure>
        <figure>
          <figcaption>Wall clock · L1 then L0</figcaption>
          <WallChart points={data.wall} onPick={openStep} />
          <p className="legend">
            <i className="swatch l1" /> L1 <i className="swatch l0" /> L0
          </p>
        </figure>
      </div>
      <h2>Meta-loop</h2>
      <div className="rail">
        {data.steps.map((slot) => (
          <Slot key={slot.k} slot={slot} onOpen={openStep} />
        ))}
      </div>
      <h2>Frameworks</h2>
      <FrameworkTree nodes={data.tree} onOpen={openFw} />
    </Shell>
  );
}

function EditCards({ edit }) {
  if (!edit) return null;
  return (
    <div className="edit-grid">
      <article>
        <h3>θ · L1</h3>
        <p>{edit.theta || "—"}</p>
      </article>
      <article>
        <h3>R · rules</h3>
        <p>{edit.rules || "—"}</p>
      </article>
      <article>
        <h3>φ · L0</h3>
        <p>{edit.phi || "—"}</p>
      </article>
    </div>
  );
}

export function StepPage({ id, k }) {
  const { go } = useNav();
  const { data, error } = usePoll(`/api/runs/${encodeURIComponent(id)}/steps/${k}`, 2000);
  if (!data) {
    return (
      <Shell strip={null}>
        <p className="empty">{error || "Reading the event log…"}</p>
      </Shell>
    );
  }
  return (
    <Shell strip={data.strip}>
      <header className="page-head">
        <button type="button" className="text" onClick={() => go(`/runs/${encodeURIComponent(id)}`)}>
          Back to the meta-loop
        </button>
        <h1>
          Step {data.k}
          {data.status ? ` · ${data.status}` : ""}
        </h1>
        <p className="lede">{data.hypothesis || "Initial framework. No hypothesis."}</p>
        {data.tamper_reason && <p className="banner bad">{data.tamper_reason}</p>}
        {data.note && <p className="muted">{data.note}</p>}
        {data.parent_framework_id && <p className="muted">Parent {data.parent_framework_id}</p>}
      </header>
      <EditCards edit={data.edit} />
      <h2>Allocation</h2>
      {data.allocation.length === 0 && (
        <p className="muted">
          This step’s budget is {gpu(data.budget_gpu_h)} GPU-h and {tok(data.budget_tokens)} tokens.
        </p>
      )}
      {data.allocation.map((row) => (
        <p key={row.framework_id} className="num">
          {row.framework_id}: {row.seeds} seeds × {gpu(row.gpu_per_seed)} GPU-h · {tok(row.tokens_per_seed)} tokens each
        </p>
      ))}
      <h2>Frameworks</h2>
      <div className="fw-list">
        {data.frameworks.map((framework) => (
          <article key={framework.framework_id} className="fw-card">
            <button
              type="button"
              className="text"
              onClick={() =>
                go(`/runs/${encodeURIComponent(id)}/frameworks/${encodeURIComponent(framework.framework_id)}`)
              }
            >
              <strong>{framework.framework_id}</strong>
            </button>
            <span className="num" title={gloss.j_sel}>
              J_sel {jfmt(framework.j_sel_median)}
            </span>
            <ul>
              {framework.seeds.map((seed) => (
                <li key={seed.seed}>
                  seed {seed.seed} · {seed.status} · {gpu(seed.gpu_h_used)} / {gpu(seed.alloc_gpu_h)} GPU-h
                  {seed.area != null ? ` · area ${jfmt(seed.area)}` : ""}
                </li>
              ))}
            </ul>
            {framework.killable && (
              <CommandButton
                verb="kill_framework"
                label={`Kill ${framework.framework_id}`}
                payload={{ meta_run_id: id, framework_id: framework.framework_id }}
              />
            )}
          </article>
        ))}
      </div>
      {data.kills.length > 0 && (
        <>
          <h2>Kills</h2>
          <ul className="kill-list">
            {data.kills.map((kill) => (
              <li key={kill.run_id}>
                seed {kill.seed}: {kill.reason}
              </li>
            ))}
          </ul>
        </>
      )}
    </Shell>
  );
}

export function FrameworkPage({ id, frameworkId }) {
  const { go } = useNav();
  const { data, error } = usePoll(
    `/api/runs/${encodeURIComponent(id)}/frameworks/${encodeURIComponent(frameworkId)}`,
    2000,
  );
  const [seedId, setSeedId] = useState(null);
  const [modelId, setModelId] = useState(null);
  useEffect(() => {
    setSeedId(null);
    setModelId(null);
  }, [frameworkId]);
  if (!data) {
    return (
      <Shell strip={null}>
        <p className="empty">{error || "Reading the event log…"}</p>
      </Shell>
    );
  }
  const active =
    data.seeds.find((seed) => seed.seed === seedId) || data.seeds[Math.floor(data.seeds.length / 2)] || data.seeds[0];
  const selected = active?.models.find((model) => model.model_id === modelId) || null;
  function pick(model) {
    setModelId(model.model_id);
    if (model.seed != null) setSeedId(model.seed);
  }
  return (
    <Shell strip={data.strip}>
      <header className="page-head">
        <button type="button" className="text" onClick={() => go(`/runs/${encodeURIComponent(id)}/steps/${data.k}`)}>
          Back to step {data.k}
        </button>
        <h1>
          {data.framework_id}
          {data.leading ? " · would elect" : ""}
        </h1>
        <p className="lede">{data.hypothesis || "Initial framework. No hypothesis."}</p>
        <p className="num" title={gloss.j_sel}>
          J_sel {jfmt(data.j_sel_median)} · {data.ci_label} {jfmt(data.ci_lo)}–{jfmt(data.ci_hi)}
        </p>
        {data.parent_framework_id && (
          <button
            type="button"
            className="text"
            onClick={() =>
              go(`/runs/${encodeURIComponent(id)}/frameworks/${encodeURIComponent(data.parent_framework_id)}`)
            }
          >
            Parent {data.parent_framework_id}
          </button>
        )}
        <p className="muted num">snapshot {data.snapshot?.slice(0, 12)}</p>
      </header>
      <EditCards edit={data.edit} />
      <div className="seed-switch" role="tablist">
        {data.seeds.map((seed, index) => (
          <button
            key={seed.seed}
            type="button"
            className={active?.seed === seed.seed ? "on" : ""}
            onClick={() => setSeedId(seed.seed)}
          >
            <i style={{ background: SEED_COLORS[index % SEED_COLORS.length] }} />
            seed {seed.seed} · {seed.status}
            {seed.area != null ? ` · ${jfmt(seed.area)}` : ""}
          </button>
        ))}
      </div>
      <div className="l1-grid">
        <section>
          <h2>Search tree</h2>
          <SearchTree models={active?.models || []} selectedModel={modelId} onPick={pick} />
        </section>
        <section>
          <h2 title={gloss.s_sel}>S_sel(b)</h2>
          <p className="muted" title={gloss.carry}>
            Solid is the score so far. A dashed tail is carry-forward out to B.
          </p>
          <ScoreChart
            seeds={data.seeds}
            B={data.B}
            selectedModel={modelId}
            onPickModel={pick}
          />
          <h2>GPU</h2>
          <GpuChart spans={active?.gpu || []} B={data.B} selectedModel={modelId} onPick={setModelId} />
        </section>
      </div>
      <h2 title={gloss.u}>u against S_sel</h2>
      <p className="muted">The incumbent was chosen by u. S_sel is what the core measured afterwards.</p>
      <ScatterU points={data.scatter} onPick={pick} />
      {selected && (
        <aside className="drawer">
          <div className="row">
            <h2>{selected.operator}</h2>
            <button type="button" className="text" onClick={() => setModelId(null)}>
              Close
            </button>
          </div>
          <dl>
            <div>
              <dt>u</dt>
              <dd className="num">{Number(selected.u).toFixed(3)}</dd>
            </div>
            <div>
              <dt>b created</dt>
              <dd className="num">{gpu(selected.b_created)}</dd>
            </div>
            <div>
              <dt>incumbent</dt>
              <dd>{selected.incumbent ? "yes" : "no"}</dd>
            </div>
            <div>
              <dt>status</dt>
              <dd>{selected.status}</dd>
            </div>
            <div>
              <dt>model</dt>
              <dd className="num">{selected.model_id}</dd>
            </div>
            <div>
              <dt>artifact</dt>
              <dd className="num">{selected.artifact_sha256?.slice(0, 16)}</dd>
            </div>
          </dl>
          <h3>Rules in force</h3>
          <pre>{JSON.stringify(data.rules, null, 2)}</pre>
          <h3>Log</h3>
          <ul className="kill-list">
            {(active?.logs || [])
              .filter((line) => !line.model_id || line.model_id === selected.model_id)
              .map((line) => (
                <li key={`${line.ts}-${line.message}`}>
                  <span className="num">{line.ts}</span> {line.message}
                </li>
              ))}
          </ul>
        </aside>
      )}
    </Shell>
  );
}
