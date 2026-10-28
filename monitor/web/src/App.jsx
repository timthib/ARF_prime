import { useCallback, useEffect, useState } from "react";
import { usePoll } from "./api";
import { FrameworkPage, MetaLoop, ModelPage, StepPage, Study } from "./pages";
import { Nav, useNav } from "./shell";

function usePath() {
  const [path, setPath] = useState(window.location.pathname);
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  const go = useCallback((to, replace = false) => {
    if (replace) window.history.replaceState({}, "", to);
    else window.history.pushState({}, "", to);
    setPath(to);
  }, []);
  return [path, go];
}

function parse(path) {
  const parts = path.split("/").filter(Boolean);
  if (parts.length === 0) return { name: "home" };
  if (parts[0] === "study") return { name: "study" };
  if (parts[0] === "runs" && parts.length === 2) return { name: "run", id: decodeURIComponent(parts[1]) };
  if (parts[0] === "runs" && parts[2] === "steps" && parts.length === 4) {
    return { name: "step", id: decodeURIComponent(parts[1]), k: Number(parts[3]) };
  }
  if (parts[0] === "runs" && parts[2] === "frameworks" && parts[4] === "models" && parts.length === 6) {
    return {
      name: "model",
      id: decodeURIComponent(parts[1]),
      frameworkId: decodeURIComponent(parts[3]),
      modelId: decodeURIComponent(parts[5]),
    };
  }
  if (parts[0] === "runs" && parts[2] === "frameworks" && parts.length === 4) {
    return {
      name: "framework",
      id: decodeURIComponent(parts[1]),
      frameworkId: decodeURIComponent(parts[3]),
    };
  }
  return { name: "missing" };
}

function Home() {
  const { go } = useNav();
  const { data, error } = usePoll("/api/study", 10000);
  useEffect(() => {
    if (!data) return;
    if (data.live_meta_run_id) go(`/runs/${encodeURIComponent(data.live_meta_run_id)}`, true);
    else go("/study", true);
  }, [data, go]);
  return <p className="empty">{error || "Opening the run in progress…"}</p>;
}

export default function App() {
  const [path, go] = usePath();
  const [commands, setCommands] = useState([]);
  useEffect(() => {
    let stop = false;
    async function load() {
      try {
        const response = await fetch("/api/commands");
        const body = await response.json();
        if (!stop) setCommands(body.commands || []);
      } catch {
        if (!stop) setCommands([]);
      }
    }
    load();
    const id = setInterval(load, 10000);
    return () => {
      stop = true;
      clearInterval(id);
    };
  }, []);
  const route = parse(path);
  let page = <p className="empty">That page is not in the control room.</p>;
  if (route.name === "home") page = <Home />;
  if (route.name === "study") page = <Study />;
  if (route.name === "run") page = <MetaLoop id={route.id} />;
  if (route.name === "step") page = <StepPage id={route.id} k={route.k} />;
  if (route.name === "framework") page = <FrameworkPage id={route.id} frameworkId={route.frameworkId} />;
  if (route.name === "model") {
    page = <ModelPage id={route.id} frameworkId={route.frameworkId} modelId={route.modelId} />;
  }
  return <Nav.Provider value={{ go, commands }}>{page}</Nav.Provider>;
}
