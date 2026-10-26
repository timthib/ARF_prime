export const SEED_COLORS = ["#1b1914", "#b8612d", "#2c5a3c"];

function extent(values, fallback = 1) {
  const nums = values.filter((value) => value != null && !Number.isNaN(value));
  if (!nums.length) return fallback;
  return Math.max(fallback, ...nums);
}

export function Sparkline({ points }) {
  if (!points?.length) return <span className="muted">no curve yet</span>;
  const width = 128;
  const height = 36;
  const maxS = extent(points.map((point) => point.s), 0.2);
  const maxB = extent(points.map((point) => point.b), 0.25);
  const x = (b) => (b / maxB) * (width - 4) + 2;
  const y = (s) => height - 4 - (s / (maxS * 1.1)) * (height - 8);
  let d = `M ${x(0)} ${y(0)}`;
  let score = 0;
  points.forEach((point) => {
    d += ` H ${x(point.b)} V ${y(point.s)}`;
    score = point.s;
  });
  d += ` H ${x(maxB)}`;
  return (
    <svg className="spark" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="S_sel sparkline">
      <path d={d} fill="none" stroke="#b8612d" strokeWidth="1.5" />
      <text x="2" y="8" className="tick">
        {score.toFixed(2)}
      </text>
    </svg>
  );
}

export function JSelChart({ series, onPick }) {
  const width = 640;
  const height = 230;
  const margin = { l: 40, r: 12, t: 16, b: 28 };
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
    <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="J_sel by meta-step">
      <line x1={margin.l} y1={y(0)} x2={width - margin.r} y2={y(0)} className="axis" />
      {yMax >= 1 && (
        <line x1={margin.l} y1={y(1)} x2={width - margin.r} y2={y(1)} className="ref" />
      )}
      <path d={line} className="maxline" />
      {series.map((point) =>
        (point.seeds || []).map((score, index) => (
          <circle
            key={`${point.k}-${index}`}
            cx={x(point.k)}
            cy={y(score)}
            r="3"
            fill={SEED_COLORS[index % SEED_COLORS.length]}
            opacity="0.75"
          />
        )),
      )}
      {series.map((point) => (
        <g key={point.k} onClick={() => onPick(point.k)} className="hit">
          <circle cx={x(point.k)} cy={y(point.median)} r="6" className="median" />
          <text x={x(point.k)} y={height - 8} textAnchor="middle" className="tick">
            {point.k}
          </text>
        </g>
      ))}
    </svg>
  );
}

export function BurnChart({ points }) {
  const width = 640;
  const height = 230;
  const margin = { l: 40, r: 12, t: 16, b: 28 };
  if (!points.length) return <p className="muted">No spend yet.</p>;
  const maxK = Math.max(...points.map((point) => point.k), 1);
  const capGpu = points[0].cap_gpu_h || 1;
  const capTok = points[0].cap_tokens || 1;
  const x = (k) => margin.l + ((k - 1) / Math.max(maxK - 1, 1)) * (width - margin.l - margin.r);
  const y = (fraction) => margin.t + (1 - fraction) * (height - margin.t - margin.b);
  const line = (key, cap) =>
    points
      .map((point, index) => `${index ? "L" : "M"} ${x(point.k)} ${y(point[key] / cap)}`)
      .join(" ");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="Budget burn">
      <line x1={margin.l} y1={y(1)} x2={width - margin.r} y2={y(1)} className="ref" />
      <line x1={margin.l} y1={y(0)} x2={width - margin.r} y2={y(0)} className="axis" />
      <path d={line("cum_gpu_h", capGpu)} className="gpu-line" />
      <path d={line("cum_tokens", capTok)} className="tok-line" />
      <text x={margin.l} y="12" className="tick">
        cap
      </text>
    </svg>
  );
}

export function WallChart({ points, onPick }) {
  const width = 640;
  const height = 230;
  const margin = { l: 40, r: 12, t: 16, b: 28 };
  if (!points.length) return <p className="muted">No steps yet.</p>;
  const maxMin = Math.max(...points.map((point) => ((point.l0_s || 0) + (point.l1_s || 0)) / 60), 1);
  const innerW = width - margin.l - margin.r;
  const bar = innerW / points.length;
  const y = (minutes) => margin.t + (1 - minutes / (maxMin * 1.1)) * (height - margin.t - margin.b);
  const base = y(0);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="Wall clock by step">
      <line x1={margin.l} y1={base} x2={width - margin.r} y2={base} className="axis" />
      {points.map((point, index) => {
        const l1 = (point.l1_s || 0) / 60;
        const l0 = (point.l0_s || 0) / 60;
        const x0 = margin.l + index * bar + 4;
        return (
          <g key={point.k} onClick={() => onPick(point.k)} className="hit">
            <rect x={x0} y={y(l1)} width={bar - 10} height={base - y(l1)} className="l1-bar" />
            <rect x={x0} y={y(l1 + l0)} width={bar - 10} height={y(l1) - y(l1 + l0)} className="l0-bar" />
            <text x={x0 + (bar - 10) / 2} y={height - 8} textAnchor="middle" className="tick">
              {point.k}
            </text>
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
    const parent =
      node.parent_framework_id && ids.has(node.parent_framework_id) ? node.parent_framework_id : null;
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
  const colW = 148;
  const rowH = 70;
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
    <svg viewBox={`0 0 ${width} ${height}`} className="tree" role="img" aria-label="Framework tree">
      {nodes.map((node) => {
        const parent = node.parent_framework_id;
        if (!parent || !pos[parent] || !pos[node.framework_id]) return null;
        const from = pos[parent];
        const to = pos[node.framework_id];
        return (
          <line
            key={`${parent}-${node.framework_id}`}
            x1={from.x + 120}
            y1={from.y + 24}
            x2={to.x}
            y2={to.y + 24}
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
              width="120"
              height="48"
              rx="2"
              fill={tone(node)}
              className={node.leading ? "node leading" : "node"}
              strokeDasharray={node.j_sel_median == null ? "4 3" : "0"}
            />
            <text x={at.x + 8} y={at.y + 18} className="node-id">
              {node.framework_id} · k{node.k}
            </text>
            <text x={at.x + 8} y={at.y + 36} className="tick">
              {node.j_sel_median == null ? "in progress" : node.j_sel_median.toFixed(3)}
              {node.leading ? "  · would elect" : ""}
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

export function ScoreChart({ seeds, B, selectedModel, onPickModel }) {
  const width = 640;
  const height = 250;
  const margin = { l: 44, r: 16, t: 16, b: 32 };
  const scores = seeds.flatMap((seed) => seed.curve.map((point) => point.s));
  const yMax = extent(scores, 1) * 1.08;
  const x = (b) => margin.l + (b / B) * (width - margin.l - margin.r);
  const y = (score) => margin.t + (1 - score / yMax) * (height - margin.t - margin.b);
  const base = y(0);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="S_sel curves">
      <line x1={margin.l} y1={base} x2={width - margin.r} y2={base} className="axis" />
      <line x1={margin.l} y1={y(1)} x2={width - margin.r} y2={y(1)} className="ref" />
      <line x1={x(B)} y1={margin.t} x2={x(B)} y2={base} className="axis" />
      <text x={x(B)} y={height - 8} textAnchor="end" className="tick">
        B
      </text>
      <text x={margin.l} y={y(1) - 4} className="tick">
        reference
      </text>
      {seeds.map((seed, index) => {
        const color = SEED_COLORS[index % SEED_COLORS.length];
        const { solid, dashed, real } = stepPath(seed.curve, x, y);
        const fill = `${solid} L ${x(real.length ? real[real.length - 1].b : 0)} ${base} L ${x(0)} ${base} Z`;
        return (
          <g key={seed.seed}>
            <path d={fill} fill={color} opacity="0.06" />
            <path d={solid} fill="none" stroke={color} strokeWidth="1.8" />
            {dashed && (
              <path d={dashed} fill="none" stroke={color} strokeWidth="1.6" strokeDasharray="5 4" />
            )}
            {real.map((point) => (
              <circle
                key={point.model_id}
                cx={x(point.b)}
                cy={y(point.s)}
                r={selectedModel === point.model_id ? 6 : 3.5}
                fill={color}
                className="hit"
                onClick={() => onPickModel({ model_id: point.model_id, seed: seed.seed })}
              />
            ))}
          </g>
        );
      })}
    </svg>
  );
}

export function GpuChart({ spans, B, selectedModel, onPick }) {
  const width = 640;
  const height = 84;
  const margin = { l: 44, r: 16, t: 18, b: 22 };
  const x = (b) => margin.l + (b / B) * (width - margin.l - margin.r);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="GPU occupancy">
      <line x1={margin.l} y1={height - margin.b} x2={width - margin.r} y2={height - margin.b} className="axis" />
      <line x1={x(B)} y1={margin.t} x2={x(B)} y2={height - margin.b} className="axis" />
      {spans.map((span) => {
        const on = selectedModel === span.model_id;
        return (
          <rect
            key={`${span.model_id}-${span.b0}`}
            x={x(span.b0)}
            y={margin.t}
            width={Math.max(1, x(span.b1) - x(span.b0))}
            height={28}
            className={on ? "gpu-span on hit" : "gpu-span hit"}
            onClick={() => onPick(span.model_id)}
          />
        );
      })}
      <text x={margin.l} y="12" className="tick">
        GPU held
      </text>
    </svg>
  );
}

export function ScatterU({ points, onPick }) {
  const width = 640;
  const height = 240;
  const margin = { l: 44, r: 16, t: 16, b: 32 };
  if (!points.length) return <p className="muted">No incumbent yet.</p>;
  const maxU = extent(points.map((point) => point.u), 0.2) * 1.1;
  const maxS = extent(points.map((point) => point.s_sel), 1) * 1.08;
  const x = (u) => margin.l + (u / maxU) * (width - margin.l - margin.r);
  const y = (score) => margin.t + (1 - score / maxS) * (height - margin.t - margin.b);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="chart" role="img" aria-label="u against S_sel">
      <line x1={margin.l} y1={y(0)} x2={width - margin.r} y2={y(0)} className="axis" />
      <line x1={margin.l} y1={margin.t} x2={margin.l} y2={y(0)} className="axis" />
      <text x={width - margin.r} y={height - 8} textAnchor="end" className="tick">
        u
      </text>
      <text x={margin.l + 4} y="14" className="tick">
        S_sel
      </text>
      {points.map((point) => (
        <circle
          key={point.model_id}
          cx={x(point.u)}
          cy={y(point.s_sel)}
          r="5"
          fill={SEED_COLORS[(point.seed ?? 0) % SEED_COLORS.length]}
          className="hit"
          onClick={() => onPick(point)}
        />
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
  const rowH = 64;
  const colW = 118;
  const width = (Math.max(...levels) + 1) * colW + 16;
  const height = Math.max(...levels.map((level) => columns[level].length)) * rowH + 12;
  const pos = {};
  levels.forEach((level) => {
    columns[level].forEach((model, index) => {
      pos[model.model_id] = { x: 8 + level * colW, y: 8 + index * rowH };
    });
  });
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="tree" role="group" aria-label="L1 search tree">
      {models.map((model) => {
        const parent = model.parent_model_id;
        if (!parent || !pos[parent]) return null;
        const from = pos[parent];
        const to = pos[model.model_id];
        return (
          <g key={`${parent}-${model.model_id}`}>
            <line x1={from.x + 100} y1={from.y + 22} x2={to.x} y2={to.y + 22} className="edge" />
          </g>
        );
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
            aria-label={`${model.operator}, u ${Number(model.u).toFixed(2)}${model.incumbent ? ", incumbent" : ""}`}
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
              width="100"
              height="44"
              rx="2"
              className={on ? "node on" : model.incumbent ? "node incumbent" : "node"}
            />
            <text x={at.x + 8} y={at.y + 18} className="node-id">
              {model.operator}
            </text>
            <text x={at.x + 8} y={at.y + 34} className="tick">
              u {Number(model.u).toFixed(2)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
