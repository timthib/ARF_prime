import { useEffect, useState } from "react";
import { dur, gloss, gpu, jfmt, sendCommand, signed, tok, usePoll } from "./api";
import { Sym } from "./marks";
import { Shell, useNav } from "./shell";
import {
  BurnChart,
  CheckChart,
  CloudChart,
  DecisionChart,
  FrameworkTree,
  GpuChart,
  JSelChart,
  ModelEvalChart,
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

function withSym(text) {
  if (text == null || text === "") return text;
  const parts = String(text).split(/(J_sel|S_sel|s_sel)/g);
  if (parts.length === 1) return text;
  return parts.map((part, index) => {
    if (part === "J_sel") return <Sym key={index} base="J" sub="sel" />;
    if (part === "S_sel") return <Sym key={index} base="S" sub="sel" />;
    if (part === "s_sel") return <Sym key={index} base="s" sub="sel" />;
    return <span key={index}>{part}</span>;
  });
}

function Thinking({ thinking, who }) {
  if (!thinking) {
    return (
      <p className="empty-inline">
        <span className="kicker">{who}</span> No thinking was recorded.
      </p>
    );
  }
  return (
    <div className="thinking">
      <article>
        <span className="kicker">{who} · what</span>
        <p>{withSym(thinking.what) || "—"}</p>
      </article>
      <article>
        <span className="kicker">{who} · how</span>
        <p>{withSym(thinking.how) || "—"}</p>
      </article>
      <article>
        <span className="kicker">{who} · why</span>
        <p>{withSym(thinking.why) || "—"}</p>
      </article>
    </div>
  );
}

function Stat({ label, value, note }) {
  return (
    <div className="stat">
      <span className="kicker">{label}</span>
      <strong className="num">{value}</strong>
      {note ? <span className="muted">{note}</span> : null}
    </div>
  );
}

function Figure({ title, note, legend, children }) {
  return (
    <figure>
      <figcaption>{title}</figcaption>
      {note ? <p className="figure-note">{note}</p> : null}
      {children}
      {legend || null}
    </figure>
  );
}

function OverfitReading({ summary, scope }) {
  if (!summary) return null;
  const losses = (summary.events || []).filter((event) => event.overfit);
  return (
    <div className="reading">
      <span className="kicker">Overfitting · {scope}</span>
      <p className="figure-note" title={gloss.overfit}>
        An overfit step is an incumbent change where u rises and <Sym base="S" sub="sel" /> falls. L1 chooses by u on
        D1_fit and does not see <Sym base="S" sub="sel" />.
      </p>
      <div className="stats">
        <Stat label="Overfit steps" value={`${summary.n_overfit} / ${summary.n_changes}`} note="incumbent changes" />
        <Stat
          label={
            <>
              <Sym base="S" sub="sel" /> lost
            </>
          }
          value={jfmt(summary.n_overfit ? summary.selection_loss : 0)}
          note="sum of the falls on overfit steps"
        />
        <Stat
          label={
            <>
              Spread u − <Sym base="S" sub="sel" />
            </>
          }
          value={jfmt(summary.spread)}
          note="on the latest incumbent"
        />
      </div>
      {losses.length === 0 && (
        <p>
          No incumbent change raised u while <Sym base="S" sub="sel" /> fell.
        </p>
      )}
      {losses.length > 0 && (
        <ul className="overfit-list">
          {losses.map((event) => (
            <li key={event.to_id}>
              <span className="kicker">Overfit step</span> {event.from_label} → {event.to_label}
              <span className="num">
                {" "}
                Δu {signed(event.du)} · Δ<Sym base="S" sub="sel" /> {signed(event.ds)} · at {gpu(event.b)} GPU-h
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function roleOf(model) {
  if (model.overfit) return "Overfit step";
  if (model.current) return "Incumbent";
  if (model.incumbent) return "Earlier incumbent";
  return "Not selected";
}

function ModelTable({ models, metric, onOpen }) {
  const ordered = [...models].sort((a, b) => a.seq - b.seq);
  return (
    <table className="grid">
      <thead>
        <tr>
          <th>Model</th>
          <th>Family</th>
          <th>Operator</th>
          <th>{metric} on D1_fit</th>
          <th>
            <Sym base="s" sub="sel" /> on D1_sel
          </th>
          <th>
            Spread u − <Sym base="s" sub="sel" />
          </th>
          <th>Role</th>
          <th>L1 · what</th>
        </tr>
      </thead>
      <tbody>
        {ordered.map((model) => (
          <tr key={model.model_id} className={model.overfit ? "overfit" : model.current ? "incumbent-row" : ""}>
            <td>
              <button type="button" className="text" onClick={() => onOpen(model.model_id)}>
                {model.label}
              </button>
            </td>
            <td>{model.family}</td>
            <td>{model.operator}</td>
            <td className="num">{jfmt(model.u)}</td>
            <td className="num">{model.s_sel == null ? "not scored" : jfmt(model.s_sel)}</td>
            <td className="num">{jfmt(model.spread)}</td>
            <td>{roleOf(model)}</td>
            <td>{withSym(model.thinking?.what) || "No thinking recorded."}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

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
            <span className="kicker">Step </span>
            {cell.k}/{cell.K}
          </span>
          <span className="num" title={gloss.j_sel}>
            <Sym base="J" sub="sel" /> {jfmt(cell.j_sel)}
          </span>
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
        The campaign, then the meta-run that is in progress. A trigger stays off until the core command exists.
      </p>
      <h2>Campaign</h2>
      <ol className="pipeline">
        {data.stages.map((stage) => (
          <li key={stage.id} className={`stage ${stage.state}`}>
            <span className="kicker">{stage.state.replace("_", " ")}</span>
            <strong>{stage.label}</strong>
            {stage.detail && <span className="muted">{stage.detail}</span>}
          </li>
        ))}
      </ol>
      <div className="workspace">
        <div>
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
        </div>
        <aside>
          <h2>Commands</h2>
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
                  <p>
                    <span className="kicker">Section 7.3 horizon</span> {report.k_rule}.{" "}
                    <span className="kicker">Stored horizon K</span> {report.experiment_k}.
                  </p>
                  <p>
                    <span className="kicker">
                      <Sym base="J" sub="sel" /> curve
                    </span>{" "}
                    {report.j_sel?.map((value) => Number(value).toFixed(2)).join(" → ")}
                  </p>
                  <p className="muted">
                    <span className="kicker">Seed noise</span> {report.sigma_seed} ·{" "}
                    <span className="kicker">GPU-h per L1 run</span> {report.gpu_h_per_l1_run} ·{" "}
                    <span className="kicker">Tokens per L0 step</span> {tok(report.tokens_per_l0_step)} ·{" "}
                    <span className="kicker">Wall per step</span> {dur(report.wall_clock_per_step_s)} ·{" "}
                    <span className="kicker">Tamper rate</span> {report.tamper_rate}
                  </p>
                </>
              )}
            </section>
          )}
        </aside>
      </div>
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
          <span>
            <span className="kicker">Budget</span> <span className="num">{gpu(slot.budget_gpu_h)} GPU-h</span>
          </span>
          <span>
            <span className="kicker">Tokens</span> <span className="num">{tok(slot.budget_tokens)}</span>
          </span>
          <span className="muted">Fresh step budget. Unspent budget is not carried in.</span>
        </>
      )}
      {slot.status === "rejected" && (
        <>
          <strong className="bad">Rejected</strong>
          <span className="clamp">{withSym(slot.l0_thinking?.what || slot.tamper_reason)}</span>
          <span>
            <span className="kicker">Spent</span> <span className="num">0 GPU-h · 0 tokens</span>
          </span>
          <span className="muted">The step is consumed.</span>
        </>
      )}
      {slot.slot === "done" && slot.status !== "rejected" && (
        <>
          <span className="clamp">
            <span className="kicker">L0 · what </span>
            {withSym(slot.l0_thinking?.what || slot.hypothesis || "Initial framework.")}
          </span>
          <strong className="num" title={gloss.j_sel}>
            <Sym base="J" sub="sel" /> {jfmt(slot.j_sel_median)}
          </strong>
          <span className="muted num">
            <span className="kicker">Seed areas </span>
            {slot.seeds.map((value) => Number(value).toFixed(3)).join("  ")}
          </span>
          <span className="muted">
            <span className="kicker">Spent </span>
            {gpu(slot.gpu_h)} GPU-h · {tok(slot.tokens)} · {dur(slot.duration_s)}
            {slot.n_kills ? ` · ${slot.n_kills} kill` : ""}
          </span>
          {slot.parent_framework_id && (
            <span className="muted">
              <span className="kicker">Parent </span>
              {slot.parent_framework_id}
            </span>
          )}
          {slot.confirmed != null && (
            <span className={slot.confirmed ? "ok-ink" : "bad"}>
              {slot.confirmed ? (
                <>
                  <Sym base="J" sub="sel" /> rose
                </>
              ) : (
                <>
                  <Sym base="J" sub="sel" /> did not rise
                </>
              )}
            </span>
          )}
        </>
      )}
      {slot.slot === "live" && (
        <>
          <span className="clamp">
            <span className="kicker">L0 · what </span>
            {withSym(slot.l0_thinking?.what || slot.hypothesis)}
          </span>
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
          {slot.last_log && <span className="clamp muted">{withSym(slot.last_log)}</span>}
        </>
      )}
    </button>
  );
}

function Journey({ items, className = "journey" }) {
  if (!items?.length) return null;
  return (
    <div className={className}>
      {items.map((item) => (
        <article key={item.id} className={item.state}>
          <span className="kicker">{item.state}</span>
          <strong>{withSym(item.label)}</strong>
          {item.detail && <span className="muted clamp">{withSym(item.detail)}</span>}
        </article>
      ))}
    </div>
  );
}

function NoteList({ notes }) {
  return (
    <ul>
      {notes.map((note) => (
        <li key={`${note.scope}-${note.level}-${note.k}-${note.framework_id}-${note.text}`}>
          <span className="kicker">{note.level}</span>{" "}
          {note.k != null && <span className="num">k{note.k} </span>}
          {note.framework_id && <span className="num">{note.framework_id} </span>}
          {withSym(note.text)}
        </li>
      ))}
    </ul>
  );
}

function Attention({ notes }) {
  const now = (notes || []).filter((note) => note.scope !== "record");
  const record = (notes || []).filter((note) => note.scope === "record");
  const worst = now.some((note) => note.level === "bad") ? "bad" : now.length ? "watch" : "";
  return (
    <>
      <div className={worst ? `attention ${worst}` : "attention"}>
        <strong>{worst === "bad" ? "Needs a look" : worst === "watch" ? "Watch" : "Running clean"}</strong>
        {now.length === 0 && <p className="muted">No live fault. Earlier rejects and kills are listed below.</p>}
        {now.length > 0 && <NoteList notes={now} />}
      </div>
      {record.length > 0 && (
        <div className="attention">
          <strong>Earlier in this run</strong>
          <NoteList notes={record} />
        </div>
      )}
    </>
  );
}

function LogList({ lines }) {
  if (!lines?.length) return <p className="muted">No log line yet.</p>;
  return (
    <ul className="log">
      {lines.map((line) => (
        <li key={`${line.ts}-${line.run_id}-${withSym(line.message)}`} className={line.level === "problem" ? "bad" : ""}>
          <span className="num">{line.ts}</span> <span className="kicker">{line.role || "log"}</span>
          {line.framework_id && <span className="num">{line.framework_id} </span>}
          {withSym(line.message)}
        </li>
      ))}
    </ul>
  );
}

function FrameworkCard({ card, onOpen }) {
  const picked = card.leading || card.elected;
  return (
    <button type="button" className={picked ? "tile picked" : "tile"} onClick={() => onOpen(card.framework_id)}>
      {picked && (
        <span className="tag">
          {card.elected ? "Elected" : (
            <>
              Best <Sym base="J" sub="sel" />
            </>
          )}
        </span>
      )}
      <span className="kicker">
        {card.index} · {card.framework_id} · step {card.k} · {card.status}
      </span>
      <strong className="num" title={gloss.j_sel}>
        <Sym base="J" sub="sel" /> {jfmt(card.j_sel)}
      </strong>
      <span className="num" title={gloss.u}>
        <span className="kicker">Best {card.metric} </span>
        {jfmt(card.best_u)}
      </span>
      <span className="num" title={gloss.overfit}>
        <span className="kicker">Overfit steps </span>
        {card.overfit_steps ?? "—"}
      </span>
      <span className="muted">
        <span className="kicker">Models </span>
        {card.n_models} · <span className="kicker">GPU-h </span>
        {gpu(card.gpu_h)} / {gpu(card.gpu_alloc)}
      </span>
      <span className="muted">
        <span className="kicker">Seeds </span>
        {card.seeds_done}/{card.seeds_total || 3}
      </span>
    </button>
  );
}

export function MetaLoop({ id }) {
  const { go } = useNav();
  const { data, error } = usePoll(`/api/runs/${encodeURIComponent(id)}`, 2000);
  const [sortKey, setSortKey] = useState("index");
  const [status, setStatus] = useState("all");
  const [minJ, setMinJ] = useState("");
  const [logMode, setLogMode] = useState("problems");
  if (!data) {
    return (
      <Shell strip={null}>
        <p className="empty">{error || "Reading the event log…"}</p>
      </Shell>
    );
  }
  const openStep = (k) => go(`/runs/${encodeURIComponent(id)}/steps/${k}`);
  const openFw = (fid) => go(`/runs/${encodeURIComponent(id)}/frameworks/${encodeURIComponent(fid)}`);
  const floor = minJ === "" ? null : Number(minJ);
  const cards = [...(data.cards || [])]
    .filter((card) => status === "all" || card.status === status)
    .filter((card) => floor == null || Number.isNaN(floor) || (card.j_sel != null && card.j_sel >= floor));
  const ranked = [...cards].sort((a, b) => {
    if (sortKey === "j_sel") return (b.j_sel ?? -Infinity) - (a.j_sel ?? -Infinity);
    if (sortKey === "gpu") return (b.gpu_h ?? 0) - (a.gpu_h ?? 0);
    if (sortKey === "best_u") return (b.best_u ?? -Infinity) - (a.best_u ?? -Infinity);
    if (sortKey === "k") return a.k - b.k || a.index - b.index;
    return a.index - b.index;
  });
  const logs = (data.logs || []).filter((line) => {
    if (logMode === "problems") return line.level === "problem";
    if (logMode === "all") return true;
    return (line.role || "").toLowerCase() === logMode;
  });
  const recent = logs.slice(-40);
  const liveStep = (data.steps || []).find((slot) => slot.k === data.now?.k);
  const check = data.incumbent_check || {};
  const sameWinner =
    check.elected_framework_id && check.elected_framework_id === check.best_s_framework_id;
  return (
    <Shell strip={data.strip}>
      <header className="page-head">
        <h1>
          {data.arm_name} · replicate {data.replicate}
        </h1>
        <p className="lede">
          <span className="kicker">Phase</span> {data.phase} · <span className="kicker">Topology</span> {data.topology} ·{" "}
          <span className="kicker">Run clock</span> {data.strip.as_of}. Closing this page does not stop the run.
        </p>
      </header>
      <Journey items={data.journey} />
      <div className="workspace">
        <section>
          <h2>L1 frameworks</h2>
          <p className="figure-note">
            One card per framework. The red border is the best <Sym base="J" sub="sel" />. <Sym base="J" sub="sel" />{" "}
            appears when that framework’s seeds have all finished. Open a card for the models and the L1 thinking.
          </p>
          <div className="filters">
            <label>
              Sort
              <select value={sortKey} onChange={(event) => setSortKey(event.target.value)}>
                <option value="index">Index</option>
                <option value="j_sel">Jₛₑₗ</option>
                <option value="best_u">Best u</option>
                <option value="gpu">GPU-h spent</option>
                <option value="k">Step</option>
              </select>
            </label>
            <label>
              Status
              <select value={status} onChange={(event) => setStatus(event.target.value)}>
                <option value="all">All</option>
                <option value="running">Running</option>
                <option value="complete">Complete</option>
                <option value="killed">Killed</option>
              </select>
            </label>
            <label>
              Minimum <Sym base="J" sub="sel" />
              <input value={minJ} onChange={(event) => setMinJ(event.target.value)} inputMode="decimal" />
            </label>
          </div>
          <div className="card-grid">
            {ranked.map((card) => (
              <FrameworkCard key={card.framework_id} card={card} onOpen={openFw} />
            ))}
          </div>
          {ranked.length === 0 && <p className="muted">No framework matches this filter.</p>}
        </section>
        <aside>
          <h2>Step {data.now?.k ?? "—"} · L0</h2>
          <Thinking thinking={liveStep?.l0_thinking} who="L0" />
          {liveStep && (
            <button type="button" className="text" onClick={() => openStep(liveStep.k)}>
              Open step {liveStep.k}
            </button>
          )}
          <h2>What is running</h2>
          {data.now?.running?.length ? (
            <ul className="log">
              {data.now.running.map((row) => (
                <li key={row.run_id}>
                  <button type="button" className="text" onClick={() => openFw(row.framework_id)}>
                    {row.framework_id}
                  </button>{" "}
                  <span className="kicker">seed</span> {row.seed} · <span className="kicker">GPU-h</span> {gpu(row.b)} /{" "}
                  {gpu(row.B)}
                  {row.last_log && <span className="muted"> · {withSym(row.last_log)}</span>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No L1 run is marked running at step {data.now?.k ?? "—"}.</p>
          )}
          <h2>This step</h2>
          <Journey items={data.live_sequence} className="sequence" />
          <h2>Attention</h2>
          <Attention notes={data.attention} />
          <details className="fold">
            <summary>Log lines</summary>
            <div className="filters">
              <label>
                Log
                <select value={logMode} onChange={(event) => setLogMode(event.target.value)}>
                  <option value="problems">Problems</option>
                  <option value="all">All</option>
                  <option value="l0">L0</option>
                  <option value="l1">L1</option>
                  <option value="core">Core</option>
                </select>
              </label>
            </div>
            <LogList lines={recent} />
          </details>
        </aside>
        <section className="span-all">
          <h2>Overfitting</h2>
          <p className="figure-note" title={gloss.overfit}>
            Median over the seeds of this framework. An overfit step is an incumbent change where u rises and{" "}
            <Sym base="S" sub="sel" /> falls. <Sym base="S" sub="sel" /> lost is the sum of those falls.
          </p>
          <table className="grid">
            <thead>
              <tr>
                <th>Framework</th>
                <th>Step</th>
                <th>Status</th>
                <th>
                  <Sym base="J" sub="sel" />
                </th>
                <th>
                  Spread u − <Sym base="S" sub="sel" />
                </th>
                <th>Overfit steps</th>
                <th>
                  <Sym base="S" sub="sel" /> lost
                </th>
              </tr>
            </thead>
            <tbody>
              {(data.cards || []).map((card) => (
                <tr key={card.framework_id} className={card.overfit_steps ? "overfit" : ""}>
                  <td>
                    <button type="button" className="text" onClick={() => openFw(card.framework_id)}>
                      {card.index} · {card.framework_id}
                    </button>
                  </td>
                  <td className="num">{card.k}</td>
                  <td>{card.status}</td>
                  <td className="num">{jfmt(card.j_sel)}</td>
                  <td className="num">{jfmt(card.spread)}</td>
                  <td className="num">{card.overfit_steps ?? "—"}</td>
                  <td className="num">{jfmt(card.selection_loss)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className="span-all charts-2">
          <Figure
            title={
              <>
                <Sym base="J" sub="sel" /> by framework
              </>
            }
            note={
              <>
                Horizontal axis: framework index, in the order the framework appeared. Vertical axis:{" "}
                <Sym base="J" sub="sel" />. The red point is the best <Sym base="J" sub="sel" />. The dashed line is
                the reference score 1.
              </>
            }
            legend={
              <p className="legend">
                <i className="swatch elect" /> best <Sym base="J" sub="sel" />
              </p>
            }
          >
            <CloudChart points={data.cloud || []} onPick={openFw} />
          </Figure>
          <Figure
            title={
              <>
                <Sym base="J" sub="sel" /> by meta-step
              </>
            }
            note={
              <>
                Dots are the seed areas. The ring is their median. The line is the best <Sym base="J" sub="sel" /> so
                far. Click a step to open it.
              </>
            }
            legend={
              <p className="legend">
                <i className="swatch gpu" /> best so far · ring is the median · dots are the seed areas
              </p>
            }
          >
            <JSelChart series={data.j_series} onPick={openStep} />
          </Figure>
          <Figure
            title={
              <>
                Final incumbent <Sym base="s" sub="sel" />
              </>
            }
            note={
              <>
                Height is the median, over the three seeds, of the incumbent’s last <Sym base="s" sub="sel" /> on
                D1_sel. Red is the framework with the best <Sym base="J" sub="sel" />.
              </>
            }
          >
            <CheckChart points={check.points || []} onPick={openFw} />
            <p>
              <span className="kicker">Reading</span>{" "}
              {!check.elected_framework_id && (
                <>
                  <Sym base="J" sub="sel" /> appears when a framework finishes its seeds.
                </>
              )}
              {sameWinner && (
                <>
                  {check.elected_framework_id} leads on <Sym base="J" sub="sel" /> and on the final incumbent{" "}
                  <Sym base="s" sub="sel" />.
                </>
              )}
              {check.elected_framework_id && !sameWinner && (
                <>
                  <Sym base="J" sub="sel" /> leads with {check.elected_framework_id}. The highest final{" "}
                  <Sym base="s" sub="sel" /> is {check.best_s_framework_id}.
                </>
              )}
            </p>
          </Figure>
          <Figure
            title="Budget used"
            note="Each line is a cumulative share of that cap. 1 means the cap for the whole meta-run."
            legend={
              <p className="legend">
                <i className="swatch gpu" /> GPU-h <i className="swatch tok" /> tokens
              </p>
            }
          >
            <BurnChart points={data.burn} />
          </Figure>
          <Figure
            title="Wall clock"
            note="Minutes in the step. The dark bar is L1. The rust bar, stacked above it, is L0."
            legend={
              <p className="legend">
                <i className="swatch l1" /> L1 <i className="swatch l0" /> L0
              </p>
            }
          >
            <WallChart points={data.wall} onPick={openStep} />
          </Figure>
        </section>
        <section className="span-all">
          <h2>Meta-steps</h2>
          <p className="figure-note">
            One card per step. Open a card for L0’s thinking and for each L1 model.
          </p>
          <div className="rail">
            {data.steps.map((slot) => (
              <Slot key={slot.k} slot={slot} onOpen={openStep} />
            ))}
          </div>
        </section>
        <section className="span-all">
          <h2>Lineage</h2>
          <p className="figure-note">
            Parent on the left, child on the right. The fill is <Sym base="J" sub="sel" />. A dashed box has not
            finished. The heavy outline is the framework L0 would elect.
          </p>
          <FrameworkTree nodes={data.tree} onOpen={openFw} />
        </section>
      </div>
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
  const [seedPick, setSeedPick] = useState(null);
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
        <p className="lede">
          <span className="kicker">Hypothesis</span> {withSym(data.hypothesis || "Initial framework. No hypothesis.")}
        </p>
        {data.tamper_reason && (
          <p className="banner bad">
            <span className="kicker">Tamper</span> {data.tamper_reason}
          </p>
        )}
        {data.note && <p className="muted">{data.note}</p>}
        {data.parent_framework_id && (
          <p>
            <span className="kicker">Parent</span> {data.parent_framework_id}
          </p>
        )}
      </header>
      <h2>L0 thinking</h2>
      <Thinking thinking={data.l0_thinking} who="L0" />
      <Journey items={data.sequence} className="sequence" />
      <h2>Edit recorded for this step</h2>
      <EditCards edit={data.edit} />
      <h2>Allocation</h2>
      {data.allocation.length === 0 && (
        <p>
          <span className="kicker">Step budget</span> {gpu(data.budget_gpu_h)} GPU-h and {tok(data.budget_tokens)} tokens.
        </p>
      )}
      {data.allocation.map((row) => (
        <p key={row.framework_id}>
          <span className="kicker">{row.framework_id}</span>{" "}
          <span className="num">
            {row.seeds} seeds × {gpu(row.gpu_per_seed)} GPU-h · {tok(row.tokens_per_seed)} tokens each
          </span>
        </p>
      ))}
      <h2>Frameworks in this step</h2>
      <div className="card-grid">
        {data.frameworks.map((framework) => (
          <div key={framework.framework_id}>
            <FrameworkCard
              card={framework}
              onOpen={(fid) => go(`/runs/${encodeURIComponent(id)}/frameworks/${encodeURIComponent(fid)}`)}
            />
            <ul>
              {(framework.seeds || framework.seed_line || []).map((seed) => (
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
          </div>
        ))}
      </div>
      <h2>L1 thinking</h2>
      <p className="figure-note">
        One block per model, for the seed you select. What, how, and why are the agent’s own record. The core’s{" "}
        <Sym base="s" sub="sel" /> is not part of that record.
      </p>
      {data.frameworks.map((framework) => {
        const seeds = framework.model_seeds || [];
        const active = seeds.find((seed) => seed.seed === seedPick) || seeds[0];
        const metric = framework.metric || "u";
        return (
          <section key={framework.framework_id}>
            <h3>{framework.framework_id}</h3>
            <div className="seed-switch" role="tablist" aria-label={`Seed for ${framework.framework_id}`}>
              {seeds.map((seed) => (
                <button
                  key={seed.seed}
                  type="button"
                  className={active?.seed === seed.seed ? "on" : ""}
                  onClick={() => setSeedPick(seed.seed)}
                >
                  seed {seed.seed} · {seed.status}
                </button>
              ))}
            </div>
            {active && (
              <>
                <OverfitReading summary={active.overfit} scope={`seed ${active.seed}`} />
                <ModelTable
                  models={active.models}
                  metric={metric}
                  onOpen={(modelId) =>
                    go(
                      `/runs/${encodeURIComponent(id)}/frameworks/${encodeURIComponent(framework.framework_id)}/models/${encodeURIComponent(modelId)}`,
                    )
                  }
                />
                <div className="think-stack">
                  {active.models
                    .slice()
                    .sort((a, b) => a.seq - b.seq)
                    .map((model) => (
                      <details key={model.model_id} className="fold" open={model.current || model.overfit}>
                        <summary>
                          {model.label} · {model.family} · L1 thinking
                        </summary>
                        <Thinking thinking={model.thinking} who="L1" />
                      </details>
                    ))}
                </div>
              </>
            )}
          </section>
        );
      })}
      {data.frameworks.length === 0 && <p className="muted">This step has no L1 framework.</p>}
      <details className="fold">
        <summary>Logs for this step</summary>
        <LogList lines={data.logs} />
      </details>
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

function openModel(go, id, frameworkId, modelId) {
  go(
    `/runs/${encodeURIComponent(id)}/frameworks/${encodeURIComponent(frameworkId)}/models/${encodeURIComponent(modelId)}`,
  );
}

export function FrameworkPage({ id, frameworkId }) {
  const { go } = useNav();
  const { data, error } = usePoll(
    `/api/runs/${encodeURIComponent(id)}/frameworks/${encodeURIComponent(frameworkId)}`,
    2000,
  );
  const [seedId, setSeedId] = useState(null);
  useEffect(() => {
    setSeedId(null);
  }, [frameworkId]);
  if (!data) {
    return (
      <Shell strip={null}>
        <p className="empty">{error || "Reading the event log…"}</p>
      </Shell>
    );
  }
  const active =
    data.seeds.find((seed) => seed.seed === seedId) || data.seeds[0];
  const metric = data.metric || "u";
  const changes = active?.best_u || [];
  function pickModel(modelId) {
    openModel(go, id, data.framework_id, modelId);
  }
  return (
    <Shell strip={data.strip}>
      <header className="page-head">
        <button type="button" className="text" onClick={() => go(`/runs/${encodeURIComponent(id)}/steps/${data.k}`)}>
          Back to step {data.k}
        </button>
        <h1>
          {data.framework_id}
          {data.leading ? (
            <>
              {" "}
              · best <Sym base="J" sub="sel" />
            </>
          ) : (
            ""
          )}
        </h1>
        <p className="lede">
          <span className="kicker">Hypothesis</span> {withSym(data.hypothesis || "Initial framework. No hypothesis.")}
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
      </header>
      <div className="stats">
        <Stat
          label={<Sym base="J" sub="sel" />}
          value={jfmt(data.j_sel_median)}
          note={
            data.j_sel_median == null
              ? "Median of the seed areas. Shown when every seed has finished."
              : `${data.ci_label} ${jfmt(data.ci_lo)}–${jfmt(data.ci_hi)}`
          }
        />
        <Stat
          label={
            <>
              Final <Sym base="s" sub="sel" />
            </>
          }
          value={jfmt(data.s_final)}
          note="Median of the last incumbent on each seed"
        />
        <Stat label={`Best ${metric}`} value={jfmt(data.best_u)} note="Highest validation score on D1_fit" />
        <Stat label="Models" value={data.n_models} note={`${gpu(data.gpu_h)} GPU-h`} />
        <Stat label="Overfit steps" value={data.overfit_steps ?? "—"} note="Most on any seed" />
        <Stat
          label={
            <>
              <Sym base="S" sub="sel" /> lost
            </>
          }
          value={jfmt(data.selection_loss)}
          note="Median over seeds"
        />
      </div>
      <h2>L0 thinking for step {data.k}</h2>
      <Thinking thinking={data.l0_thinking} who="L0" />
      <h2>Edit recorded for this framework</h2>
      <EditCards edit={data.edit} />
      <div className="seed-switch" role="tablist" aria-label="Seed">
        {data.seeds.map((seed, index) => (
          <button
            key={seed.seed}
            type="button"
            className={active?.seed === seed.seed ? "on" : ""}
            onClick={() => setSeedId(seed.seed)}
          >
            <i style={{ background: SEED_COLORS[index % SEED_COLORS.length] }} />
            seed {seed.seed} · {seed.status}
            {seed.area != null ? ` · area ${jfmt(seed.area)}` : ""}
          </button>
        ))}
      </div>
      <p className="figure-note">
        <span className="kicker">Seed</span> The table and the curves below are seed {active?.seed ?? "—"}. L0 and L1 do
        not see the other seeds.
      </p>
      <OverfitReading summary={active?.overfit} scope={`seed ${active?.seed ?? "—"}`} />
      <h2>Models · seed {active?.seed ?? "—"}</h2>
      <ModelTable models={active?.models || []} metric={metric} onOpen={pickModel} />
      <div className="think-stack">
        {(active?.models || [])
          .slice()
          .sort((a, b) => a.seq - b.seq)
          .map((model) => (
            <details key={model.model_id} className="fold" open={model.current || model.overfit}>
              <summary>
                {model.label} · {model.family} · L1 thinking
              </summary>
              <Thinking thinking={model.thinking} who="L1" />
            </details>
          ))}
      </div>
      <div className="charts-2">
        <Figure
          title={
            <>
              Best {metric} and <Sym base="S" sub="sel" /> · seed {active?.seed ?? "—"}
            </>
          }
          note={
            <>
              Green is the best validation score so far. Rust is the core’s <Sym base="S" sub="sel" /> of that
              incumbent. A red ring is an overfit step: u rose and <Sym base="S" sub="sel" /> fell. Names are model1,
              model2, … in the order L1 proposed them.
            </>
          }
          legend={
            <p className="legend">
              <i className="swatch u" /> best {metric} <i className="swatch s" /> <Sym base="S" sub="sel" />{" "}
              <i className="swatch elect" /> overfit step
            </p>
          }
        >
          <DecisionChart seed={active} B={data.B} onPick={pickModel} />
          <p>
            <span className="kicker">Incumbent changes</span>{" "}
            {changes.length
              ? changes.map((point) => `${point.label} at ${gpu(point.b)} GPU-h`).join(", ")
              : "None yet."}
          </p>
          <p className="figure-note" title={gloss.carry}>
            A dashed continuation, when a run stops before B, holds the last incumbent score out to B.
          </p>
          <GpuChart spans={active?.gpu || []} B={data.B} selectedModel={null} onPick={pickModel} />
          <p className="figure-note">GPU-h held by each model on this seed, in time order.</p>
        </Figure>
        <Figure
          title={
            <>
              Every model, {metric} · seed {active?.seed ?? "—"}
            </>
          }
          note="Each point is one model. Green is the current incumbent. The others were proposed and scored on D1_fit."
          legend={
            <p className="legend">
              <i className="swatch u" /> incumbent <i className="swatch gpu" /> other candidate
            </p>
          }
        >
          <ModelEvalChart models={active?.models || []} metric={metric} onPick={pickModel} />
        </Figure>
      </div>
      <h2>Search tree · seed {active?.seed ?? "—"}</h2>
      <p className="figure-note">
        Each box is one model. The edge is the parent L1 edited. Green outline: current incumbent. Red outline: overfit
        step.
      </p>
      <SearchTree models={active?.models || []} selectedModel={null} onPick={(model) => pickModel(model.model_id)} />
      <h2>
        u against <Sym base="S" sub="sel" />, all seeds
      </h2>
      <p className="figure-note" title={gloss.u}>
        Each point is an incumbent. Horizontal axis: u, L1’s validation on D1_fit. Vertical axis:{" "}
        <Sym base="S" sub="sel" />, the core’s score on D1_sel. A red ring is an overfit step. Click a point to open
        that model.
      </p>
      <ScatterU
        points={data.scatter}
        onPick={(point) => {
          setSeedId(point.seed);
          pickModel(point.model_id);
        }}
      />
      <p className="legend">
        {data.seeds.map((seed, index) => (
          <span key={seed.seed}>
            <i className="swatch" style={{ background: SEED_COLORS[index % SEED_COLORS.length] }} /> seed {seed.seed}
          </span>
        ))}
      </p>
      {active?.kill_reason && (
        <p className="banner bad">
          <span className="kicker">Kill</span> {active.kill_reason}
        </p>
      )}
      <details className="fold">
        <summary>Rules in force</summary>
        <pre>{JSON.stringify(data.rules, null, 2)}</pre>
      </details>
      <details className="fold">
        <summary>Log for seed {active?.seed ?? "—"}</summary>
        <ul className="log">
          {(active?.logs || []).map((line) => (
            <li key={`${line.ts}-${withSym(line.message)}`}>
              <span className="num">{line.ts}</span> {withSym(line.message)}
            </li>
          ))}
        </ul>
      </details>
    </Shell>
  );
}

function nameOf(models, id) {
  return models.find((item) => item.model_id === id)?.label || "—";
}

function decisionText(models, model) {
  const ordered = [...models].sort((a, b) => a.b_created - b.b_created || a.seq - b.seq);
  let best = null;
  for (const item of ordered) {
    if (item.model_id === model.model_id) {
      if (best == null || item.u > best.u) {
        return "L1 made this model the incumbent. Its validation score u is the best so far.";
      }
      return `L1 kept ${best.label}. This model's u does not beat that incumbent.`;
    }
    if (item.u != null && (best == null || item.u > best.u)) best = item;
  }
  return "This model is on record for the seed.";
}

export function ModelPage({ id, frameworkId, modelId }) {
  const { go } = useNav();
  const { data, error } = usePoll(
    `/api/runs/${encodeURIComponent(id)}/frameworks/${encodeURIComponent(frameworkId)}`,
    2000,
  );
  if (!data) {
    return (
      <Shell strip={null}>
        <p className="empty">{error || "Reading the event log…"}</p>
      </Shell>
    );
  }
  const seed = data.seeds.find((item) => item.models.some((model) => model.model_id === modelId));
  const model = seed?.models.find((item) => item.model_id === modelId);
  if (!model) {
    return (
      <Shell strip={data.strip}>
        <p className="empty">That model is not in this framework.</p>
      </Shell>
    );
  }
  const children = (seed?.models || []).filter((item) => item.parent_model_id === model.model_id);
  const metric = data.metric || "u";
  return (
    <Shell strip={data.strip}>
      <header className="page-head">
        <button
          type="button"
          className="text"
          onClick={() => go(`/runs/${encodeURIComponent(id)}/frameworks/${encodeURIComponent(frameworkId)}`)}
        >
          Back to {frameworkId}
        </button>
        <h1>
          {model.label} · {model.family}
        </h1>
        <p className="lede">
          <span className="kicker">Seed</span> {seed.seed} · <span className="kicker">Operator</span> {model.operator} ·{" "}
          <span className="kicker">Status</span> {model.status}
          {model.current ? " · incumbent" : ""}
          {model.overfit ? " · overfit step" : ""}
        </p>
      </header>
      <h2>L1 thinking</h2>
      <Thinking thinking={model.thinking} who="L1" />
      <div className="stats">
        <Stat label={`${metric} on D1_fit`} value={jfmt(model.u)} note="L1’s validation score" />
        <Stat
          label={
            <>
              <Sym base="s" sub="sel" /> on D1_sel
            </>
          }
          value={model.s_sel == null ? "not scored" : jfmt(model.s_sel)}
          note={
            model.s_sel == null
              ? "Only an incumbent is scored by the core"
              : `Mean absolute error on D1_sel: ${jfmt(model.s_mae)} °C`
          }
        />
        <Stat
          label={
            <>
              Spread u − <Sym base="s" sub="sel" />
            </>
          }
          value={jfmt(model.spread)}
          note="Positive means u sits above the selection score"
        />
        <Stat label="GPU-h held" value={gpu(model.gpu_h)} note={`Created at ${gpu(model.b_created)} GPU-h`} />
        <Stat label="Updates" value={model.n_updates} note="Child models on this branch" />
        <Stat label="Role" value={roleOf(model)} note={model.operator} />
      </div>
      <div className="reading">
        <span className="kicker">L1 decision</span>
        <p>{decisionText(seed.models, model)}</p>
      </div>
      {model.overfit && (
        <div className="reading">
          <span className="kicker">Overfit step</span>
          <p title={gloss.overfit}>
            {model.label} became the incumbent with a higher u and a lower <Sym base="S" sub="sel" /> than the previous
            incumbent. That is overfitting the fit set. L1 does not see <Sym base="S" sub="sel" />.
          </p>
        </div>
      )}
      {model.s_sel != null && (
        <p className="figure-note" title={gloss.s_sel}>
          <span className="kicker">Core score</span> Scored on D1_sel at {gpu(model.b_scored)} GPU-h. L1 does not receive
          this score.
        </p>
      )}
      <dl className="drawer">
        <div>
          <dt>Family</dt>
          <dd>{model.family}</dd>
        </div>
        <div>
          <dt>Id</dt>
          <dd className="num">{model.model_id}</dd>
        </div>
        <div>
          <dt>Artifact</dt>
          <dd className="num">{model.artifact_sha256?.slice(0, 16)}</dd>
        </div>
      </dl>
      <h2>Lineage</h2>
      <div className="row">
        {model.parent_model_id ? (
          <button type="button" className="text" onClick={() => openModel(go, id, frameworkId, model.parent_model_id)}>
            Parent {nameOf(seed.models, model.parent_model_id)}
          </button>
        ) : (
          <span className="muted">Root of this branch.</span>
        )}
        {children.map((child) => (
          <button
            key={child.model_id}
            type="button"
            className="text"
            onClick={() => openModel(go, id, frameworkId, child.model_id)}
          >
            Child {child.label} · {child.family}
          </button>
        ))}
      </div>
      <h2>Log</h2>
      <ul className="log">
        {(seed.logs || [])
          .filter((line) => !line.model_id || line.model_id === model.model_id)
          .map((line) => (
            <li key={`${line.ts}-${withSym(line.message)}`}>
              <span className="num">{line.ts}</span> {withSym(line.message)}
            </li>
          ))}
      </ul>
    </Shell>
  );
}
