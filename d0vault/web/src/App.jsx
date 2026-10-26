import { useEffect, useState } from "react";

const COLORS = ["#1c1614", "#7a1f2b", "#8a5a2b", "#2c5a3c", "#3d4c7a", "#6e625c"];

function fmt(value) {
  if (value == null || Number.isNaN(Number(value))) return "—";
  return Number(value).toFixed(3);
}

function useBoard(k, ready) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!ready) return undefined;
    let stop = false;
    async function tick() {
      const response = await fetch(`/api/board?k=${k}`);
      if (response.status === 401) {
        if (!stop) setError("signed out");
        return;
      }
      if (!response.ok) {
        if (!stop) setError("The room could not be read.");
        return;
      }
      const body = await response.json();
      if (!stop) {
        setData(body);
        setError("");
      }
    }
    tick();
    const id = setInterval(tick, 10000);
    return () => {
      stop = true;
      clearInterval(id);
    };
  }, [k, ready]);
  return { data, error };
}

function Curves({ curves, frameworks }) {
  const width = 640;
  const height = 240;
  const margin = { l: 40, r: 12, t: 12, b: 28 };
  const scores = curves.flatMap((row) => row.points.map((point) => point.s));
  const yMax = Math.max(1, ...scores, 0.2) * 1.1;
  const x = (b) => margin.l + (b / 0.25) * (width - margin.l - margin.r);
  const y = (s) => margin.t + (1 - s / yMax) * (height - margin.t - margin.b);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="S_0 curves">
      <line x1={margin.l} y1={y(0)} x2={width - margin.r} y2={y(0)} className="axis" />
      {curves.map((row) => {
        const color = COLORS[frameworks.findIndex((item) => item.framework_id === row.framework_id) % COLORS.length];
        let d = `M ${x(0)} ${y(0)}`;
        row.points.forEach((point) => {
          d += ` H ${x(point.b)} V ${y(point.s)}`;
        });
        return <path key={`${row.framework_id}-${row.seed}`} d={d} fill="none" stroke={color} strokeWidth={row.seed === 2 ? 1.8 : 1} opacity={row.seed === 2 ? 1 : 0.45} />;
      })}
    </svg>
  );
}

function GapChart({ gap, kDagger }) {
  const width = 640;
  const height = 240;
  const margin = { l: 40, r: 16, t: 16, b: 28 };
  const values = gap.flatMap((row) => [row.j_sel, row.j0, row.g_k]);
  const yMax = Math.max(1, ...values) * 1.1;
  const maxK = Math.max(...gap.map((row) => row.k), 1);
  const x = (k) => margin.l + ((k - 1) / Math.max(maxK - 1, 1)) * (width - margin.l - margin.r);
  const y = (v) => margin.t + (1 - v / yMax) * (height - margin.t - margin.b);
  const line = (key) => gap.map((row, index) => `${index ? "L" : "M"} ${x(row.k)} ${y(row[key])}`).join(" ");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="Overfitting gap">
      <line x1={margin.l} y1={y(0)} x2={width - margin.r} y2={y(0)} className="axis" />
      <path d={line("j_sel")} fill="none" stroke="#1c1614" strokeWidth="1.7" />
      <path d={line("j0")} fill="none" stroke="#7a1f2b" strokeWidth="1.7" />
      <path d={line("g_k_corrected")} fill="none" stroke="#8a5a2b" strokeWidth="1.4" strokeDasharray="4 3" />
      {kDagger != null && (
        <g>
          <line x1={x(kDagger)} y1={margin.t} x2={x(kDagger)} y2={y(0)} stroke="#7a1f2b" strokeDasharray="2 3" />
          <text x={x(kDagger) + 4} y={margin.t + 12} className="dagger">
            k† hindsight
          </text>
        </g>
      )}
    </svg>
  );
}

function Spread({ spread }) {
  const seeds = spread.elected?.seeds || [];
  return (
    <div>
      <p>
        Elected {spread.elected?.framework_id || "—"} · median {fmt(spread.elected?.median)}
      </p>
      <p className="num">{seeds.map((value) => fmt(value)).join("   ")}</p>
      {spread.f_ideal ? (
        <p>
          f_ideal · S_0 {fmt(spread.f_ideal.s0)} · MAE {fmt(spread.f_ideal.e_mae)} °C · RMSE {fmt(spread.f_ideal.e_rmse)} °C
        </p>
      ) : (
        <p className="muted">Phase 2 has not produced f_ideal for this step.</p>
      )}
    </div>
  );
}

function Ranking({ ranking, onPick }) {
  const points = ranking.points || [];
  const width = 640;
  const height = 280;
  const margin = { l: 44, r: 16, t: 16, b: 32 };
  if (!points.length) return null;
  const xs = points.flatMap((point) => [point.j_sel_min, point.j_sel_max, point.j_sel]);
  const ys = points.flatMap((point) => [point.j0_min, point.j0_max, point.j0]);
  const xMin = Math.min(...xs) - 0.04;
  const xMax = Math.max(...xs) + 0.04;
  const yMin = Math.min(...ys) - 0.04;
  const yMax = Math.max(...ys) + 0.04;
  const x = (value) => margin.l + ((value - xMin) / (xMax - xMin)) * (width - margin.l - margin.r);
  const y = (value) => margin.t + (1 - (value - yMin) / (yMax - yMin)) * (height - margin.t - margin.b);
  return (
    <>
      <p className="num">
        ρ {fmt(ranking.spearman)} · τ {fmt(ranking.kendall)} · rank of elected {ranking.elected_rank} · regret {fmt(ranking.regret)} · n {ranking.n}
      </p>
      <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="J_sel against J_0">
        <line x1={margin.l} y1={height - margin.b} x2={width - margin.r} y2={height - margin.b} className="axis" />
        <line x1={margin.l} y1={margin.t} x2={margin.l} y2={height - margin.b} className="axis" />
        <text x={width - margin.r} y={height - 8} textAnchor="end" className="tick">J_sel</text>
        <text x={margin.l + 4} y="14" className="tick">J_0</text>
        {points.map((point) => (
          <g key={point.framework_id} className="hit" onClick={() => onPick(point.framework_id)}>
            <line x1={x(point.j_sel_min)} y1={y(point.j0)} x2={x(point.j_sel_max)} y2={y(point.j0)} stroke="#1c1614" />
            <line x1={x(point.j_sel)} y1={y(point.j0_min)} x2={x(point.j_sel)} y2={y(point.j0_max)} stroke="#1c1614" />
            <circle cx={x(point.j_sel)} cy={y(point.j0)} r={point.markers.includes("elected") ? 7 : 5} fill={point.markers.includes("elected") ? "#7a1f2b" : "#1c1614"} />
            <text x={x(point.j_sel) + 8} y={y(point.j0) - 6} className="tick">
              {point.framework_id}
              {point.markers.length ? ` ${point.markers.join(" ")}` : ""}
            </text>
          </g>
        ))}
      </svg>
      <table>
        <thead>
          <tr>
            <th>Place by J_sel</th>
            <th>Framework</th>
            <th>J_sel</th>
            <th>J_0</th>
            <th>D0 rank</th>
          </tr>
        </thead>
        <tbody>
          {ranking.four_point.map((row) => (
            <tr key={row.role}>
              <td>{row.role}</td>
              <td>{row.framework_id}</td>
              <td className="num">{fmt(row.j_sel)}</td>
              <td className="num">{fmt(row.j0)}</td>
              <td className="num">{row.rank_0}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <table>
        <thead>
          <tr>
            <th>Framework</th>
            <th>DJF</th>
            <th>MAM</th>
            <th>JJA</th>
            <th>SON</th>
          </tr>
        </thead>
        <tbody>
          {ranking.seasons.map((row) => (
            <tr key={row.framework_id}>
              <td>{row.framework_id}</td>
              <td className="num">{fmt(row.djf)}</td>
              <td className="num">{fmt(row.mam)}</td>
              <td className="num">{fmt(row.jja)}</td>
              <td className="num">{fmt(row.son)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function Board({ onSignOut }) {
  const [k, setK] = useState(6);
  const [focus, setFocus] = useState(null);
  const { data, error } = useBoard(k, true);
  if (error === "signed out") {
    return (
      <p className="login">
        The session ended. <button type="button" onClick={onSignOut}>Sign in again</button>
      </p>
    );
  }
  if (!data) return <p className="muted">{error || "Reading the vault store…"}</p>;
  return (
    <>
      <div className="banner">
        <span>D0 room. This load is logged.{data.fixture ? " Fake vault: these figures are synthetic." : ""}</span>
        <span className="num">looks so far: {data.looks}</span>
      </div>
      <main>
        <h1>Step {data.k} of {data.k_max}</h1>
        <div className="steps">
          {Array.from({ length: data.k_max }, (_, index) => index + 1).map((step) => (
            <button key={step} type="button" className={step === data.k ? "on" : ""} onClick={() => setK(step)}>
              {step}
            </button>
          ))}
        </div>
        <div className="grid">
          <section>
            <h2>S_0(b) and J_0</h2>
            <p className="muted">Three seeds. The darker line is the middle seed. {focus ? `Selected ${focus}.` : "Click a ranking point to name a framework."}</p>
            <Curves curves={data.curves} frameworks={data.frameworks} />
            <ul>
              {data.frameworks.map((row) => (
                <li key={row.framework_id}>
                  {row.framework_id} · J_0 {fmt(row.j0_median)} ({fmt(row.j0_min)}–{fmt(row.j0_max)}) · J_sel {fmt(row.j_sel)}
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h2>Gap</h2>
            <p className="muted">J_sel and J_0 of the leader so far, and the corrected gap. k† is hindsight only.</p>
            <GapChart gap={data.gap} kDagger={data.k_dagger} />
          </section>
        </div>
        <section>
          <h2>Spread</h2>
          <Spread spread={data.spread} />
        </section>
        <section>
          <h2>Ranking</h2>
          <Ranking ranking={data.ranking} onPick={setFocus} />
        </section>
        <section>
          <h2>Audit and scorer</h2>
          <p>
            Scorer {data.health.state}. Queue depth {data.health.queue_depth}. Design {data.design_hash}.
          </p>
          <ul>
            {data.audit.map((row) => (
              <li key={`${row.ts}-${row.page}-${row.params}`}>
                <span className="num">{row.ts}</span> {row.page} {row.params}
              </li>
            ))}
          </ul>
        </section>
      </main>
    </>
  );
}

export default function App() {
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  async function submit(event) {
    event.preventDefault();
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    const body = await response.json();
    if (body.ok) {
      setReady(true);
      setMessage("");
      return;
    }
    setMessage(body.reason || "refused");
  }
  if (!ready) {
    return (
      <form className="login" onSubmit={submit}>
        <h1>D0 room</h1>
        <p className="muted">One session. Opening the figures writes a line in the look log.</p>
        <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" />
        <p><button type="submit">Enter</button></p>
        {message && <p>{message}</p>}
      </form>
    );
  }
  return <Board onSignOut={() => setReady(false)} />;
}
