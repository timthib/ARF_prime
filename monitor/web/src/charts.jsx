import { SvgSym } from "./marks";

export const SEED_COLORS = ["#1b1914", "#b8612d", "#2c5a3c"];

function extent(values, fallback = 1) {
  const nums = values.filter((value) => value != null && !Number.isNaN(value));
  if (!nums.length) return fallback;
  return Math.max(fallback, ...nums);
}

function Axes({ width, height, margin, y, ticks, xLabel, yLabel, format }) {
  const fmt = format || ((value) => (Math.abs(value) >= 10 || Number.isInteger(value) ? String(Math.round(value)) : Number(value).toFixed(2)));
  return (
    <g>
      <line x1={margin.l} y1={y(ticks[0] ?? 0)} x2={width - margin.r} y2={y(ticks[0] ?? 0)} className="axis" />
      {ticks.map((tick) => (
        <g key={tick}>
          <line x1={margin.l - 4} x2={margin.l} y1={y(tick)} y2={y(tick)} className="axis" />
          <text x={margin.l - 6} y={y(tick) + 3} textAnchor="end" className="tick">
            {fmt(tick)}
          </text>
        </g>
      ))}
      <text className="axis-name" x={(margin.l + width - margin.r) / 2} y={height - 4} textAnchor="middle">
        {xLabel}
      </text>
      <text
        className="axis-name"
        textAnchor="middle"
        transform={`translate(12 ${(margin.t + height - margin.b) / 2}) rotate(-90)`}
      >
        {yLabel}
      </text>
    </g>
  );
}

function scoreTicks(yMax) {
  const ticks = [0];
  if (yMax >= 1) ticks.push(1);
  return ticks;
}

export function Sparkline({ points }) {
  if (!points?.length) return <span className="muted">No Sₛₑₗ curve yet</span>;
  const width = 148;
  const height = 42;
  const maxS = extent(points.map((point) => point.s), 0.2);
  const maxB = extent(points.map((point) => point.b), 0.25);
  const x = (b) => (b / maxB) * (width - 8) + 4;
  const y = (s) => height - 14 - (s / (maxS * 1.1)) * (height - 22);
  let d = `M ${x(0)} ${y(0)}`;
  let score = 0;
  points.forEach((point) => {
    d += ` H ${x(point.b)} V ${y(point.s)}`;
    score = point.s;
  });
  d += ` H ${x(maxB)}`;
  return (
    <svg className="spark" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Sₛₑₗ of the incumbent against GPU-hours">
      <text x="4" y="10" className="tick">
        <SvgSym base="S" sub="sel" /> {score.toFixed(2)}
      </text>
      <path d={d} fill="none" stroke="#b8612d" strokeWidth="1.5" />
    </svg>
  );
}

export function JSelChart({ series, onPick }) {
  const width = 640;
  const height = 260;
  const margin = { l: 58, r: 16, t: 16, b: 44 };
  const ks = series.map((point) => point.k);
  const maxK = Math.max(20, ...ks, 1);
  const scores = series.flatMap((point) => [point.median, point.running_max, ...(point.seeds || [])]);
  const yMax = extent(scores, 1) * 1.08;
  const x = (k) => margin.l + ((k - 1) / Math.max(maxK - 1, 1)) * (width - margin.l - margin.r);
  const y = (score) => margin.t + (1 - score / yMax) * (height - margin.t - margin.b);
  const line = series
    .map((point, index) => `${index ? "L" : "M"} ${x(point.k)} ${y(point.running_max)}`)
    .join(" ");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="Jₛₑₗ by meta-step">
      <Axes
        width={width}
        height={height}
        margin={margin}
        y={y}
        ticks={scoreTicks(yMax)}
        xLabel="meta-step k"
        yLabel={<SvgSym base="J" sub="sel" />}
      />
      {yMax >= 1 && <line x1={margin.l} y1={y(1)} x2={width - margin.r} y2={y(1)} className="ref" />}
      <path d={line} className="maxline" />
      {series.map((point) =>
        (point.seeds || []).map((score, index) => (
          <circle
            key={`${point.k}-${index}`}
            cx={x(point.k)}
            cy={y(score)}
            r="3.5"
            fill={SEED_COLORS[index % SEED_COLORS.length]}
            opacity="0.8"
          >
            <title>
              step {point.k}, seed area {Number(score).toFixed(3)}
            </title>
          </circle>
        )),
      )}
      {series.map((point) => (
        <g key={point.k} onClick={() => onPick(point.k)} className="hit">
          <circle cx={x(point.k)} cy={y(point.median)} r="6" className="median" />
          <text x={x(point.k)} y={height - 22} textAnchor="middle" className="tick">
            {point.k}
          </text>
          <title>
            step {point.k}, median {Number(point.median).toFixed(3)}, best so far {Number(point.running_max).toFixed(3)}
          </title>
        </g>
      ))}
    </svg>
  );
}

export function BurnChart({ points }) {
  const width = 640;
  const height = 260;
  const margin = { l: 58, r: 16, t: 16, b: 44 };
  if (!points.length) return <p className="muted">No spend yet.</p>;
  const maxK = Math.max(...points.map((point) => point.k), 1);
  const capGpu = points[0].cap_gpu_h || 1;
  const capTok = points[0].cap_tokens || 1;
  const x = (k) => margin.l + ((k - 1) / Math.max(maxK - 1, 1)) * (width - margin.l - margin.r);
  const y = (fraction) => margin.t + (1 - fraction) * (height - margin.t - margin.b);
  const line = (key, cap) =>
    points.map((point, index) => `${index ? "L" : "M"} ${x(point.k)} ${y(point[key] / cap)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="Share of the GPU-hour cap and the token cap">
      <Axes
        width={width}
        height={height}
        margin={margin}
        y={y}
        ticks={[0, 1]}
        xLabel="meta-step k"
        yLabel="share of the cap"
        format={(value) => (value === 0 ? "0" : "cap")}
      />
      <path d={line("cum_gpu_h", capGpu)} className="gpu-line" />
      <path d={line("cum_tokens", capTok)} className="tok-line" />
      {points.map((point) => (
        <g key={point.k}>
          <text x={x(point.k)} y={height - 22} textAnchor="middle" className="tick">
            {point.k}
          </text>
        </g>
      ))}
    </svg>
  );
}

export function WallChart({ points, onPick }) {
  const width = 640;
  const height = 260;
  const margin = { l: 58, r: 16, t: 16, b: 44 };
  if (!points.length) return <p className="muted">No steps yet.</p>;
  const maxMin = Math.max(...points.map((point) => ((point.l0_s || 0) + (point.l1_s || 0)) / 60), 1);
  const yMax = maxMin * 1.1;
  const innerW = width - margin.l - margin.r;
  const bar = innerW / points.length;
  const y = (minutes) => margin.t + (1 - minutes / yMax) * (height - margin.t - margin.b);
  const base = y(0);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="Wall clock minutes by meta-step, L1 then L0">
      <Axes
        width={width}
        height={height}
        margin={margin}
        y={y}
        ticks={[0, maxMin]}
        xLabel="meta-step k"
        yLabel="minutes"
        format={(value) => (value === 0 ? "0" : value.toFixed(0))}
      />
      {points.map((point, index) => {
        const l1 = (point.l1_s || 0) / 60;
        const l0 = (point.l0_s || 0) / 60;
        const x0 = margin.l + index * bar + 6;
        return (
          <g key={point.k} onClick={() => onPick(point.k)} className="hit">
            <rect x={x0} y={y(l1)} width={Math.max(4, bar - 14)} height={Math.max(0, base - y(l1))} className="l1-bar" />
            <rect x={x0} y={y(l1 + l0)} width={Math.max(4, bar - 14)} height={Math.max(0, y(l1) - y(l1 + l0))} className="l0-bar" />
            <text x={x0 + (bar - 14) / 2} y={height - 22} textAnchor="middle" className="tick">
              {point.k}
            </text>
            <title>
              step {point.k}: L1 {l1.toFixed(1)} min, L0 {l0.toFixed(1)} min
            </title>
          </g>
        );
      })}
    </svg>
  );
}

export function FrameworkTree({ nodes, onOpen }) {
  if (!nodes.length) return <p className="muted">No framework yet.</p>;
  const ids = new Set(nodes.map((node) => node.framework_id));
  const children = {};
  nodes.forEach((node) => {
    const parent = node.parent_framework_id && ids.has(node.parent_framework_id) ? node.parent_framework_id : null;
    (children[parent] ||= []).push(node);
  });
  const depth = {};
  const walk = (id, level) => {
    depth[id] = level;
    (children[id] || []).forEach((child) => walk(child.framework_id, level + 1));
  };
  (children[null] || []).forEach((node) => walk(node.framework_id, 0));
  const columns = {};
  nodes.forEach((node) => {
    const level = depth[node.framework_id] ?? 0;
    (columns[level] ||= []).push(node);
  });
  const levels = Object.keys(columns).map(Number);
  const colW = 168;
  const rowH = 78;
  const width = (Math.max(...levels) + 1) * colW + 24;
  const height = Math.max(...levels.map((level) => columns[level].length)) * rowH + 16;
  const pos = {};
  levels.forEach((level) => {
    columns[level].forEach((node, index) => {
      pos[node.framework_id] = { x: 12 + level * colW, y: 10 + index * rowH };
    });
  });
  const scores = nodes.map((node) => node.j_sel_median).filter((score) => score != null);
  const lo = Math.min(...scores);
  const hi = Math.max(...scores);
  const tone = (node) => {
    if (node.j_sel_median == null) return "transparent";
    const t = hi === lo ? 1 : (node.j_sel_median - lo) / (hi - lo);
    return `rgba(184, 97, 45, ${0.18 + 0.7 * t})`;
  };
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="tree" role="img" aria-label="Framework lineage. Fill is Jₛₑₗ. A dashed box is unfinished.">
      {nodes.map((node) => {
        const parent = node.parent_framework_id;
        if (!parent || !pos[parent] || !pos[node.framework_id]) return null;
        const from = pos[parent];
        const to = pos[node.framework_id];
        return (
          <line
            key={`${parent}-${node.framework_id}`}
            x1={from.x + 140}
            y1={from.y + 26}
            x2={to.x}
            y2={to.y + 26}
            className="edge"
          />
        );
      })}
      {nodes.map((node) => {
        const at = pos[node.framework_id];
        return (
          <g key={node.framework_id} className="hit" onClick={() => onOpen(node.framework_id)}>
            <rect
              x={at.x}
              y={at.y}
              width="140"
              height="52"
              rx="2"
              fill={tone(node)}
              className={node.leading ? "node leading" : "node"}
              strokeDasharray={node.j_sel_median == null ? "4 3" : "0"}
            />
            <text x={at.x + 8} y={at.y + 18} className="node-id">
              {node.framework_id} · step {node.k}
            </text>
            <text x={at.x + 8} y={at.y + 38} className="tick">
              {node.j_sel_median == null ? (
                <>
                  <SvgSym base="J" sub="sel" /> not finished
                </>
              ) : (
                <>
                  <SvgSym base="J" sub="sel" /> {node.j_sel_median.toFixed(3)}
                </>
              )}
              {node.leading ? " · best" : ""}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function stepPath(curve, x, y) {
  const real = curve.filter((point) => !point.carried);
  let solid = `M ${x(0)} ${y(0)}`;
  real.forEach((point) => {
    solid += ` H ${x(point.b)} V ${y(point.s)}`;
  });
  const carry = curve.find((point) => point.carried);
  const last = real[real.length - 1];
  const dashed = carry && last ? `M ${x(last.b)} ${y(last.s)} H ${x(carry.b)}` : "";
  return { solid, dashed, real };
}

function indexX(index, maxIndex, margin, width) {
  return margin.l + ((index - 1) / Math.max(maxIndex - 1, 1)) * (width - margin.l - margin.r);
}

export function CloudChart({ points, onPick }) {
  const width = 640;
  const height = 270;
  const margin = { l: 58, r: 16, t: 16, b: 44 };
  if (!points.length) return <p className="muted">No framework yet.</p>;
  const maxIndex = Math.max(...points.map((point) => point.index), 1);
  const scores = points.map((point) => point.j_sel).filter((score) => score != null);
  const yMax = extent(scores, 1) * 1.08;
  const x = (index) => indexX(index, maxIndex, margin, width);
  const y = (score) => margin.t + (1 - score / yMax) * (height - margin.t - margin.b);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="Jₛₑₗ by framework index">
      <Axes
        width={width}
        height={height}
        margin={margin}
        y={y}
        ticks={scoreTicks(yMax)}
        xLabel="framework index"
        yLabel={<SvgSym base="J" sub="sel" />}
      />
      {yMax >= 1 && <line x1={margin.l} y1={y(1)} x2={width - margin.r} y2={y(1)} className="ref" />}
      {points.map((point) => (
        <text key={`t-${point.index}`} x={x(point.index)} y={height - 22} textAnchor="middle" className="tick">
          {point.index}
        </text>
      ))}
      {points.map((point) =>
        point.j_sel == null ? null : (
          <g key={point.framework_id} className="hit" onClick={() => onPick(point.framework_id)}>
            <circle cx={x(point.index)} cy={y(point.j_sel)} r={point.leading ? 7 : 5} className={point.leading ? "elected-dot" : "cloud-dot"} />
            <title>
              {point.index} {point.framework_id} Jₛₑₗ {Number(point.j_sel).toFixed(3)}
            </title>
          </g>
        ),
      )}
    </svg>
  );
}

export function CheckChart({ points, onPick }) {
  const width = 640;
  const height = 270;
  const margin = { l: 58, r: 16, t: 16, b: 44 };
  if (!points.length) return <p className="muted">No finished incumbent yet.</p>;
  const maxIndex = Math.max(...points.map((point) => point.index), 1);
  const yMax = extent(points.map((point) => point.s_final), 1) * 1.08;
  const x = (index) => indexX(index, maxIndex, margin, width);
  const y = (score) => margin.t + (1 - score / yMax) * (height - margin.t - margin.b);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="Final incumbent sₛₑₗ by framework">
      <Axes
        width={width}
        height={height}
        margin={margin}
        y={y}
        ticks={scoreTicks(yMax)}
        xLabel="framework index"
        yLabel={<SvgSym base="s" sub="sel" />}
      />
      {yMax >= 1 && <line x1={margin.l} y1={y(1)} x2={width - margin.r} y2={y(1)} className="ref" />}
      {points.map((point) => (
        <g key={point.framework_id} className="hit" onClick={() => onPick(point.framework_id)}>
          <circle cx={x(point.index)} cy={y(point.s_final)} r={point.leading ? 7 : 5} className={point.leading ? "elected-dot" : "cloud-dot"} />
          <text x={x(point.index)} y={height - 22} textAnchor="middle" className="tick">
            {point.index}
          </text>
          <title>
            {point.index} {point.framework_id} final sₛₑₗ {Number(point.s_final).toFixed(3)}
          </title>
        </g>
      ))}
    </svg>
  );
}

export function DecisionChart({ seed, B, onPick }) {
  const width = 720;
  const height = 300;
  const margin = { l: 58, r: 16, t: 18, b: 44 };
  if (!seed) return <p className="muted">Pick a seed.</p>;
  const uPoints = seed.best_u || [];
  const sPoints = (seed.curve || []).filter((point) => !point.carried);
  const scores = [...uPoints.map((point) => point.u), ...sPoints.map((point) => point.s)];
  const yMax = extent(scores, 1) * 1.12;
  const budget = B || 0.25;
  const x = (b) => margin.l + (b / budget) * (width - margin.l - margin.r);
  const y = (score) => margin.t + (1 - score / yMax) * (height - margin.t - margin.b);
  const step = (points, key) => {
    let d = `M ${x(0)} ${y(0)}`;
    points.forEach((point) => {
      d += ` H ${x(point.b)} V ${y(point[key])}`;
    });
    const last = points[points.length - 1];
    if (last) d += ` H ${x(budget)}`;
    return d;
  };
  const events = (seed.overfit?.events || []).filter((event) => event.overfit);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="Best u and Sₛₑₗ against GPU-hours">
      <Axes
        width={width}
        height={height}
        margin={margin}
        y={y}
        ticks={scoreTicks(yMax)}
        xLabel="GPU-h b"
        yLabel="score"
      />
      {yMax >= 1 && <line x1={margin.l} y1={y(1)} x2={width - margin.r} y2={y(1)} className="ref" />}
      <path d={step(uPoints, "u")} className="u-line" />
      <path d={step(sPoints, "s")} className="s-line" />
      {uPoints.map((point) => (
        <g key={`u-${point.model_id}`} className="hit" onClick={() => onPick(point.model_id)}>
          <circle cx={x(point.b)} cy={y(point.u)} r="4.5" className="u-dot" />
          <text x={x(point.b) + 5} y={y(point.u) - 7} className="tick">
            {point.label}
          </text>
          <title>
            {point.label} u {Number(point.u).toFixed(3)} at {Number(point.b).toFixed(2)} GPU-h
          </title>
        </g>
      ))}
      {sPoints.map((point) => (
        <g key={`s-${point.model_id}-${point.b}`} className="hit" onClick={() => onPick(point.model_id)}>
          <circle cx={x(point.b)} cy={y(point.s)} r="4" className="s-dot" />
          <title>
            {point.label || point.model_id} Sₛₑₗ {Number(point.s).toFixed(3)}
          </title>
        </g>
      ))}
      {events.map((event) => (
        <g key={`over-${event.to_id}`} className="hit" onClick={() => onPick(event.to_id)}>
          <circle cx={x(event.b)} cy={y(event.s_sel)} r="9" className="overfit-ring" />
          <text x={x(event.b) + 12} y={y(event.s_sel) + 14} className="tick overfit-label">
            overfit
          </text>
          <title>
            {event.from_label} to {event.to_label}: u {event.du >= 0 ? "+" : ""}
            {Number(event.du).toFixed(3)}, Sₛₑₗ {Number(event.ds).toFixed(3)}
          </title>
        </g>
      ))}
    </svg>
  );
}

export function ModelEvalChart({ models, metric, onPick }) {
  const width = 640;
  const height = 250;
  const margin = { l: 58, r: 16, t: 16, b: 48 };
  const rows = [...(models || [])].filter((model) => model.u != null);
  if (!rows.length) return <p className="muted">No model evaluated yet.</p>;
  rows.sort((a, b) => a.seq - b.seq);
  const yMax = extent(rows.map((model) => model.u), 0.2) * 1.15;
  const x = (index) => margin.l + ((index + 0.5) / rows.length) * (width - margin.l - margin.r);
  const y = (score) => margin.t + (1 - score / yMax) * (height - margin.t - margin.b);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label={`Validation ${metric} of every model`}>
      <Axes
        width={width}
        height={height}
        margin={margin}
        y={y}
        ticks={scoreTicks(yMax)}
        xLabel="model, in the order L1 proposed it"
        yLabel={metric}
      />
      {rows.map((model, index) => (
        <g key={model.model_id} className="hit" onClick={() => onPick(model.model_id)}>
          <circle cx={x(index)} cy={y(model.u)} r={model.current ? 6 : 4} className={model.current ? "u-dot" : "cloud-dot"} />
          <text x={x(index)} y={height - 24} textAnchor="middle" className="tick">
            {model.label}
          </text>
          <title>
            {model.label} {model.family} {metric} {Number(model.u).toFixed(3)}
            {model.current ? " incumbent" : ""}
            {model.overfit ? " overfit step" : ""}
          </title>
        </g>
      ))}
    </svg>
  );
}

export function ScoreChart({ seeds, B, selectedModel, onPickModel }) {
  const width = 640;
  const height = 270;
  const margin = { l: 58, r: 16, t: 16, b: 44 };
  const scores = seeds.flatMap((seed) => seed.curve.map((point) => point.s));
  const yMax = extent(scores, 1) * 1.08;
  const x = (b) => margin.l + (b / B) * (width - margin.l - margin.r);
  const y = (score) => margin.t + (1 - score / yMax) * (height - margin.t - margin.b);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="Sₛₑₗ curves by seed">
      <Axes
        width={width}
        height={height}
        margin={margin}
        y={y}
        ticks={scoreTicks(yMax)}
        xLabel="GPU-h b"
        yLabel={<SvgSym base="S" sub="sel" />}
      />
      {yMax >= 1 && <line x1={margin.l} y1={y(1)} x2={width - margin.r} y2={y(1)} className="ref" />}
      {seeds.map((seed, index) => {
        const color = SEED_COLORS[index % SEED_COLORS.length];
        const { solid, dashed, real } = stepPath(seed.curve, x, y);
        return (
          <g key={seed.seed}>
            <path d={solid} fill="none" stroke={color} strokeWidth="1.8" />
            {dashed && <path d={dashed} fill="none" stroke={color} strokeWidth="1.6" strokeDasharray="5 4" />}
            {real.map((point) => (
              <circle
                key={point.model_id}
                cx={x(point.b)}
                cy={y(point.s)}
                r={selectedModel === point.model_id ? 6 : 3.5}
                fill={color}
                className="hit"
                onClick={() => onPickModel({ model_id: point.model_id, seed: seed.seed })}
              >
                <title>
                  seed {seed.seed} {point.label || ""} Sₛₑₗ {Number(point.s).toFixed(3)}
                </title>
              </circle>
            ))}
          </g>
        );
      })}
    </svg>
  );
}

export function GpuChart({ spans, B, selectedModel, onPick }) {
  const width = 720;
  const height = 96;
  const margin = { l: 58, r: 16, t: 22, b: 28 };
  const budget = B || 0.25;
  const x = (b) => margin.l + (b / budget) * (width - margin.l - margin.r);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="GPU-hours held by each model">
      <line x1={margin.l} y1={height - margin.b} x2={width - margin.r} y2={height - margin.b} className="axis" />
      <text className="axis-name" x={(margin.l + width - margin.r) / 2} y={height - 4} textAnchor="middle">
        GPU-h b
      </text>
      <text className="tick" x={margin.l} y="12">
        0
      </text>
      <text className="tick" x={width - margin.r} y="12" textAnchor="end">
        B {Number(budget).toFixed(2)}
      </text>
      {spans.map((span) => {
        const on = selectedModel === span.model_id;
        return (
          <g key={`${span.model_id}-${span.b0}`}>
            <rect
              x={x(span.b0)}
              y={margin.t}
              width={Math.max(1, x(span.b1) - x(span.b0))}
              height={28}
              className={on ? "gpu-span on hit" : "gpu-span hit"}
              onClick={() => onPick(span.model_id)}
            />
            <title>
              {span.label || span.model_id}: {Number(span.b0).toFixed(2)} to {Number(span.b1).toFixed(2)} GPU-h
            </title>
          </g>
        );
      })}
    </svg>
  );
}

export function ScatterU({ points, onPick }) {
  const width = 720;
  const height = 280;
  const margin = { l: 58, r: 18, t: 16, b: 44 };
  if (!points.length) return <p className="muted">No incumbent yet.</p>;
  const maxU = extent(points.map((point) => point.u), 0.2) * 1.12;
  const maxS = extent(points.map((point) => point.s_sel), 1) * 1.08;
  const seeds = [...new Set(points.map((point) => point.seed))].sort((a, b) => a - b);
  const x = (u) => margin.l + (u / maxU) * (width - margin.l - margin.r);
  const y = (score) => margin.t + (1 - score / maxS) * (height - margin.t - margin.b);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="u against Sₛₑₗ for every incumbent">
      <Axes
        width={width}
        height={height}
        margin={margin}
        y={y}
        ticks={scoreTicks(maxS)}
        xLabel="u, validation on D1_fit"
        yLabel={<SvgSym base="S" sub="sel" />}
      />
      <text x={width - margin.r} y={height - 22} textAnchor="end" className="tick">
        {maxU.toFixed(2)}
      </text>
      {points.map((point) => (
        <g key={`${point.seed}-${point.model_id}`} className="hit" onClick={() => onPick(point)}>
          <circle
            cx={x(point.u)}
            cy={y(point.s_sel)}
            r={point.overfit ? 7 : 5}
            fill={SEED_COLORS[Math.max(0, seeds.indexOf(point.seed)) % SEED_COLORS.length]}
            className={point.overfit ? "overfit-dot" : undefined}
            stroke={point.overfit ? "#8d2e2a" : "none"}
            strokeWidth={point.overfit ? 2 : 0}
          />
          <title>
            seed {point.seed} {point.label}: u {Number(point.u).toFixed(3)}, Sₛₑₗ {Number(point.s_sel).toFixed(3)}
            {point.overfit ? ", overfit step" : ""}
          </title>
        </g>
      ))}
    </svg>
  );
}

export function SearchTree({ models, selectedModel, onPick }) {
  if (!models.length) return <p className="muted">No candidate yet.</p>;
  const ids = new Set(models.map((model) => model.model_id));
  const children = {};
  models.forEach((model) => {
    const parent = model.parent_model_id && ids.has(model.parent_model_id) ? model.parent_model_id : null;
    (children[parent] ||= []).push(model);
  });
  const depth = {};
  const walk = (id, level) => {
    depth[id] = level;
    (children[id] || []).forEach((child) => walk(child.model_id, level + 1));
  };
  (children[null] || []).forEach((model) => walk(model.model_id, 0));
  const columns = {};
  models.forEach((model) => {
    const level = depth[model.model_id] ?? 0;
    (columns[level] ||= []).push(model);
  });
  const levels = Object.keys(columns).map(Number);
  const rowH = 72;
  const colW = 148;
  const width = (Math.max(...levels) + 1) * colW + 16;
  const height = Math.max(...levels.map((level) => columns[level].length)) * rowH + 12;
  const pos = {};
  levels.forEach((level) => {
    columns[level].forEach((model, index) => {
      pos[model.model_id] = { x: 8 + level * colW, y: 8 + index * rowH };
    });
  });
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="tree" role="group" aria-label="L1 search tree. Each box is one model.">
      {models.map((model) => {
        const parent = model.parent_model_id;
        if (!parent || !pos[parent]) return null;
        const from = pos[parent];
        const to = pos[model.model_id];
        return <line key={`${parent}-${model.model_id}`} x1={from.x + 128} y1={from.y + 26} x2={to.x} y2={to.y + 26} className="edge" />;
      })}
      {models.map((model) => {
        const at = pos[model.model_id];
        const on = selectedModel === model.model_id;
        return (
          <g
            key={model.model_id}
            className="hit"
            role="button"
            tabIndex={0}
            aria-label={`${model.label}, ${model.family}, u ${Number(model.u).toFixed(2)}${model.current ? ", incumbent" : ""}`}
            onClick={() => onPick(model)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onPick(model);
              }
            }}
          >
            <rect
              x={at.x}
              y={at.y}
              width="128"
              height="52"
              rx="2"
              className={on ? "node on" : model.current ? "node incumbent" : model.overfit ? "node overfit" : "node"}
            />
            <text x={at.x + 8} y={at.y + 16} className="node-id">
              {model.label}
            </text>
            <text x={at.x + 8} y={at.y + 32} className="tick">
              {model.family} · {model.operator}
            </text>
            <text x={at.x + 8} y={at.y + 46} className="tick">
              u {Number(model.u).toFixed(2)}
              {model.s_sel == null ? "" : (
                <>
                  {" "}
                  · <SvgSym base="S" sub="sel" /> {Number(model.s_sel).toFixed(2)}
                </>
              )}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
