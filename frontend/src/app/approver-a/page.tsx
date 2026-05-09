"use client";
import { useEffect, useState } from "react";
import { api, auth, humanSection } from "@/lib/api";
import Header from "@/components/Header";
import StatusBadge from "@/components/StatusBadge";
import Toast from "@/components/Toast";

export default function ApproverAPage() {
  const [items, setItems] = useState<any[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [toast, setToast] = useState<{ message: string; variant: "success" | "error" } | null>(null);

  useEffect(() => {
    if (!auth.token()) window.location.href = "/";
    if (auth.role() !== "approver_a") window.location.href = "/";
    refresh();
  }, []);

  async function refresh() {
    try {
      const list = await api.listContent({ status: "pending" });
      setItems(list);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function decide(id: string, decision: "approved_text" | "rejected") {
    setBusy(id);
    setErr(null);
    try {
      await api.decideText(id, decision, notes[id] || undefined);
      setToast(
        decision === "approved_text"
          ? { message: "Texto aprobado y enviado a validación visual", variant: "success" }
          : { message: "Contenido rechazado", variant: "error" },
      );
      await refresh();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="max-w-4xl mx-auto px-6 py-8">
      <Header title="Cola de aprobación de texto · Aprobador A" />
      {toast && (
        <Toast message={toast.message} variant={toast.variant} onDismiss={() => setToast(null)} />
      )}
      {err && <div className="card border-red-400/40 bg-red-500/10 text-red-300 mb-4">{err}</div>}
      {items.length === 0 && (
        <div className="card muted">No hay items pendientes. El creador aún no ha generado contenido nuevo.</div>
      )}
      <div className="space-y-3">
        {items.map((i) => (
          <div key={i.content_id} className="card">
            <div className="flex justify-between items-start gap-3 mb-2">
              <div>
                <div className="text-xs uppercase tracking-wide muted">{i.content_type}</div>
                <div className="text-sm muted mt-1">Pedido: {i.original_request}</div>
              </div>
              <StatusBadge status={i.status} />
            </div>
            <div className="border border-white/10 rounded-lg p-3 bg-white/5 whitespace-pre-wrap text-sm">
              {i.content}
            </div>
            {i.retrieved_chunks?.length > 0 && (
              <div className="mt-3 text-xs muted">
                Secciones de marca usadas: {i.retrieved_chunks.map((c: any) => `${humanSection(c.section)} (${(c.similarity * 100).toFixed(0)}%)`).join(" · ")}
              </div>
            )}
            <div className="mt-3 flex flex-col gap-2">
              <textarea
                className="textarea"
                placeholder="Notas (opcional)"
                value={notes[i.content_id] || ""}
                onChange={(e) => setNotes({ ...notes, [i.content_id]: e.target.value })}
              />
              <div className="flex gap-2">
                <button
                  className="btn btn-primary"
                  disabled={busy === i.content_id}
                  onClick={() => decide(i.content_id, "approved_text")}
                >
                  Aprobar texto
                </button>
                <button
                  className="btn btn-danger"
                  disabled={busy === i.content_id}
                  onClick={() => decide(i.content_id, "rejected")}
                >
                  Rechazar
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
