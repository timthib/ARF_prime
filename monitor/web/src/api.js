import { useEffect, useState } from "react";

export const gloss = {
  j_sel: "Jₛₑₗ is the median, over seeds, of the area under Sₛₑₗ from 0 to B.",
  s_sel: "Sₛₑₗ(b) is the D1_sel score of the incumbent at GPU-hours b. The incumbent is the model with the best u so far on D1_fit.",
  carry: "Carry-forward: a run that stops before B keeps its last incumbent score out to B.",
  u: "u is L1's own validation score inside D1_fit. It chooses the incumbent. L1 never sees D1_sel.",
  spread: "Spread is u minus Sₛₑₗ on an incumbent. Positive means validation sits above the selection score.",
  overfit: "An overfit step is an incumbent change where u rises and Sₛₑₗ falls.",
};

export function usePoll(url, ms) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let stop = false;
    let timer = 0;
    let controller = null;
    async function tick() {
      controller = new AbortController();
      try {
        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const body = await response.json();
        if (!stop) {
          setData(body);
          setError("");
        }
      } catch (err) {
        if (err.name === "AbortError" || stop) return;
        setError(err.message || "The event log could not be read.");
      }
      if (!stop) timer = window.setTimeout(tick, ms);
    }
    tick();
    return () => {
      stop = true;
      window.clearTimeout(timer);
      if (controller) controller.abort();
    };
  }, [url, ms]);
  return { data, error };
}

export async function sendCommand(verb, payload) {
  const response = await fetch("/api/commands", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ verb, ...payload }),
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || "The command was not accepted.");
  }
  return {
    status: body.status,
    event_id: body.event_id,
    reason: body.reason,
    verb: body.verb,
  };
}

export function gpu(value) {
  if (value == null || Number.isNaN(Number(value))) return "—";
  return Number(value).toFixed(2);
}

export function tok(value) {
  if (value == null) return "—";
  const n = Number(value);
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${Math.round(n / 1e3)}k`;
  return String(n);
}

export function dur(seconds) {
  if (seconds == null) return "—";
  const whole = Math.max(0, Math.round(seconds));
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  if (hours) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

export function jfmt(value) {
  if (value == null || Number.isNaN(Number(value))) return "—";
  return Number(value).toFixed(3);
}

export function signed(value) {
  if (value == null || Number.isNaN(Number(value))) return "—";
  const number = Number(value);
  const text = number.toFixed(3);
  return number > 0 ? `+${text}` : text;
}
