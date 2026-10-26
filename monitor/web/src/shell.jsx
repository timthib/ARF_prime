import { createContext, useContext } from "react";
import { dur, gloss, gpu, jfmt, tok } from "./api";

export const Nav = createContext({ go() {}, commands: [] });

export function useNav() {
  return useContext(Nav);
}

function Meter({ used, cap }) {
  const pct = cap ? Math.min(100, (100 * Number(used)) / Number(cap)) : 0;
  return (
    <div className="meter" aria-hidden="true">
      <div style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Strip({ strip }) {
  if (!strip) return null;
  const verdict = strip.running
    ? "Descriptive until step K."
    : strip.elected
      ? "Elected by the core."
      : "The core has not elected.";
  return (
    <div className="strip">
      <div className="cell" title="The core owns the step counter. K is a hard minimum and a hard maximum.">
        <span className="kicker">Step</span>
        <strong className="num">
          {strip.k} / {strip.K}
        </strong>
        <span className="muted">{strip.phase || "no run"}</span>
      </div>
      <div className="cell" title="GPU-hours charged by the core against the meta-run cap.">
        <span className="kicker">GPU-h</span>
        <strong className="num">
          {gpu(strip.gpu_h_used)} / {gpu(strip.gpu_h_cap)}
        </strong>
        <Meter used={strip.gpu_h_used} cap={strip.gpu_h_cap} />
      </div>
      <div className="cell" title="Tokens charged by the core gateway, L0 and L1 together.">
        <span className="kicker">Tokens</span>
        <strong className="num">
          {tok(strip.tokens_used)} / {tok(strip.tokens_cap)}
        </strong>
        <Meter used={strip.tokens_used} cap={strip.tokens_cap} />
      </div>
      <div className="cell" title="Wall clock of this meta-run. The 8–13 h band is the planning estimate for K = 20.">
        <span className="kicker">Time</span>
        <strong className="num">{dur(strip.elapsed_s)}</strong>
        <span className="muted">
          {strip.wall_band_h ? `of ${strip.wall_band_h[0]}–${strip.wall_band_h[1]} h` : "run clock"}
        </span>
      </div>
      <div className="cell" title={gloss.j_sel}>
        <span className="kicker">{strip.elected ? "Elected" : "Would elect"}</span>
        <strong className="num">{jfmt(strip.leading_j_sel)}</strong>
        <span className="muted">
          {strip.leading_framework_id || "—"} · {verdict}
        </span>
      </div>
      <div className="cell">
        <span className={`lamp ${strip.lamp?.level || "ok"}`}>{strip.lamp?.text}</span>
        <span className={`dot ${strip.scorer?.state || "stopped"}`} title="Scorer lamp. No hold-out figure is on this page." />
        <span className="muted">
          scorer {strip.scorer?.state} · outbox {strip.scorer?.outbox_depth ?? 0}
        </span>
      </div>
    </div>
  );
}

export function Shell({ strip, children }) {
  const { go } = useNav();
  return (
    <>
      <header className="top">
        <div className="brand">
          <button type="button" className="text" onClick={() => go("/study")}>
            Study
          </button>
          <span className="mark">ARF</span>
          <span className="room">Control room</span>
        </div>
        <Strip strip={strip} />
      </header>
      <main>{children}</main>
    </>
  );
}
