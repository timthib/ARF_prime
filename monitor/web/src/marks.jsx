export function Sym({ base, sub }) {
  return (
    <abbr className="sym" title={`${base}_${sub}`}>
      {base}
      <sub>{sub}</sub>
    </abbr>
  );
}

export function SvgSym({ base, sub }) {
  return (
    <>
      {base}
      <tspan className="sub" baselineShift="sub">
        {sub}
      </tspan>
    </>
  );
}
