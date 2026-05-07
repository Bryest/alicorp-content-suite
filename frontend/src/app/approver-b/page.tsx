"use client";
import { useEffect, useRef, useState } from "react";
import { api, auth } from "@/lib/api";
import Header from "@/components/Header";
import StatusBadge from "@/components/StatusBadge";

export default function ApproverBPage() {
  const [items, setItems] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [audit, setAudit] = useState<Record<string, any>>({});
  const inputs = useRef<Record<string, HTMLInputElement | null>>({});

  useEffect(() => {
    if (!auth.token()) window.location.href = "/";
    if (auth.role() !== "approver_b") window.location.href = "/";
    refresh();
  }, []);

  async function refresh() {
    try {
      const list = await api.listContent({ status: "approved_text" });
      setItems(list);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function uploadFor(id: string, file: File) {
    setBusy(id);
    setErr(null);
    try {
      const r = await api.auditImage(id, file);
      setAudit({ ...audit, [id]: r });
      await refresh();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="max-w-4xl mx-auto px-6 py-8">
      <Header title="Multimodal audit · Approver B" />
      {err && <div className="card border-red-400/40 bg-red-500/10 text-red-300 mb-4">{err}</div>}
      {items.length === 0 && (
        <div className="card muted">
          No items waiting for image audit. Items appear after Approver A approves the text.
        </div>
      )}
      <div className="space-y-4">
        {items.map((i) => {
          const result = audit[i.content_id];
          return (
            <div key={i.content_id} className="card">
              <div className="flex justify-between items-start gap-3 mb-2">
                <div>
                  <div className="text-xs uppercase tracking-wide muted">{i.content_type}</div>
                  <div className="text-sm mt-1">{i.content}</div>
                </div>
                <StatusBadge status={i.status} />
              </div>
              <div className="mt-3 flex flex-col gap-3">
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  ref={(el) => (inputs.current[i.content_id] = el)}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) uploadFor(i.content_id, f);
                  }}
                  className="text-sm"
                />
                <div className="text-xs muted">
                  Upload an image. Gemini (or the deterministic mock) will audit against the brand's VISUAL section.
                </div>
                {busy === i.content_id && <div className="muted text-sm">Auditing…</div>}
                {result && (
                  <div className={`mt-2 p-3 rounded-lg border ${result.audit_result?.compliant ? "border-green-400/40 bg-green-500/10" : "border-red-400/40 bg-red-500/10"}`}>
                    <div className="font-semibold mb-2">
                      {result.audit_result?.compliant ? "✓ COMPLIANT" : "✗ NON-COMPLIANT"} —{" "}
                      <StatusBadge status={result.status} />
                    </div>
                    <div className="text-sm mb-2">{result.audit_result?.summary}</div>
                    <ul className="text-sm space-y-1">
                      {(result.audit_result?.checks || []).map((c: any, idx: number) => (
                        <li key={idx} className="flex gap-2">
                          <span>{c.passed ? "✓" : "✗"}</span>
                          <span><b>{c.rule}</b> — <span className="muted">{c.note}</span></span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </main>
  );
}
