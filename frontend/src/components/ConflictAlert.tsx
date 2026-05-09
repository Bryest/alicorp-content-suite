export default function ConflictAlert({
  conflicts,
}: {
  conflicts: Array<{ rule: string; violation: string; suggestion: string }>;
}) {
  if (!conflicts || conflicts.length === 0) return null;
  return (
    <div className="card border-red-400/40 bg-red-500/10 mt-3">
      <div className="font-bold text-red-300 mb-2">Conflictos con las reglas de marca</div>
      <ul className="space-y-2">
        {conflicts.map((c, i) => (
          <li key={i}>
            <div className="text-sm font-semibold">{c.rule}</div>
            <div className="text-sm">{c.violation}</div>
            {c.suggestion && (
              <div className="text-xs muted mt-1">→ {c.suggestion}</div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
