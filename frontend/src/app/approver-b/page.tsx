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
  const [selectedFiles, setSelectedFiles] = useState<Record<string, File>>({});
  const [previewUrls, setPreviewUrls] = useState<Record<string, string>>({});
  const inputs = useRef<Record<string, HTMLInputElement | null>>({});

  useEffect(() => {
    if (!auth.token()) window.location.href = "/";
    if (auth.role() !== "approver_b") window.location.href = "/";
    refresh();
  }, []);

  // Clean up object URLs when component unmounts
  useEffect(() => {
    return () => {
      Object.values(previewUrls).forEach((url) => URL.revokeObjectURL(url));
    };
  }, [previewUrls]);

  async function refresh() {
    try {
      const list = await api.listContent({ status: "approved_text" });
      setItems(list);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  function selectFile(id: string, file: File) {
    // Revoke any previous preview URL for this item
    if (previewUrls[id]) {
      URL.revokeObjectURL(previewUrls[id]);
    }
    const url = URL.createObjectURL(file);
    setSelectedFiles({ ...selectedFiles, [id]: file });
    setPreviewUrls({ ...previewUrls, [id]: url });
    setErr(null);
  }

  function clearSelection(id: string) {
    if (previewUrls[id]) {
      URL.revokeObjectURL(previewUrls[id]);
    }
    const newFiles = { ...selectedFiles };
    delete newFiles[id];
    setSelectedFiles(newFiles);
    const newPreviews = { ...previewUrls };
    delete newPreviews[id];
    setPreviewUrls(newPreviews);
    // Reset the file input element so the user can re-select the same file if needed
    const input = inputs.current[id];
    if (input) input.value = "";
  }

  async function runAudit(id: string) {
    const file = selectedFiles[id];
    if (!file) return;
    setBusy(id);
    setErr(null);
    try {
      const r = await api.auditImage(id, file);
      setAudit({ ...audit, [id]: r });
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(null);
    }
  }

  async function dismissAndContinue(id: string) {
    const newAudit = { ...audit };
    delete newAudit[id];
    setAudit(newAudit);
    clearSelection(id);
    await refresh();
  }

  return (
    <main className="max-w-4xl mx-auto px-6 py-8">
      <Header title="Validación visual · Aprobador B" />
      {err && <div className="card border-red-400/40 bg-red-500/10 text-red-300 mb-4">{err}</div>}
      {items.length === 0 && (
        <div className="card muted">
          No hay imágenes pendientes de validación. Los items aparecen una vez que el Aprobador A aprueba el texto.
        </div>
      )}
      <div className="space-y-4">
        {items.map((i) => {
          const result = audit[i.content_id];
          const file = selectedFiles[i.content_id];
          const previewUrl = previewUrls[i.content_id];
          const isBusy = busy === i.content_id;

          return (
            <div key={i.content_id} className="card">
              <div className="flex justify-between items-start gap-3 mb-2">
                <div>
                  <div className="text-xs uppercase tracking-wide muted">{i.content_type}</div>
                  <div className="text-sm mt-1">{i.content}</div>
                </div>
                <StatusBadge status={i.status} />
              </div>

              {/* Si ya hay resultado del audit, mostramos solo eso (feedback persistente) */}
              {result ? (
                <div className="mt-3 space-y-3">
                  <div
                    className={`p-4 rounded-lg border ${
                      result.audit_result?.compliant
                        ? "border-green-400/40 bg-green-500/10"
                        : "border-red-400/40 bg-red-500/10"
                    }`}
                  >
                    <div className="font-semibold mb-2 text-base">
                      {result.audit_result?.compliant
                        ? "✓ Imagen aprobada"
                        : "✗ Imagen no cumple las reglas de marca"}{" "}
                      — <StatusBadge status={result.status} />
                    </div>
                    <div className="text-sm mb-3">{result.audit_result?.summary}</div>
                    {previewUrl && (
                      <div className="mb-3">
                        <img
                          src={previewUrl}
                          alt="Imagen auditada"
                          className="max-h-48 rounded-md border border-white/10"
                        />
                      </div>
                    )}
                    <ul className="text-sm space-y-1">
                      {(result.audit_result?.checks || []).map((c: any, idx: number) => (
                        <li key={idx} className="flex gap-2">
                          <span className={c.passed ? "text-green-400" : "text-red-400"}>
                            {c.passed ? "✓" : "✗"}
                          </span>
                          <span>
                            <b>{c.rule}</b> — <span className="muted">{c.note}</span>
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="flex gap-2">
                    <button
                      className="btn btn-primary"
                      onClick={() => dismissAndContinue(i.content_id)}
                    >
                      Continuar →
                    </button>
                  </div>
                </div>
              ) : (
                <div className="mt-3 flex flex-col gap-3">
                  {!file ? (
                    <>
                      <input
                        type="file"
                        accept="image/png,image/jpeg,image/webp"
                        ref={(el) => {
                          inputs.current[i.content_id] = el;
                        }}
                        onChange={(e) => {
                          const f = e.target.files?.[0];
                          if (f) selectFile(i.content_id, f);
                        }}
                        className="text-sm"
                      />
                      <div className="text-xs muted">
                        Sube una imagen (JPG, PNG o WebP, máx 5 MB). Validaremos contra las
                        reglas visuales de la marca.
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="flex items-start gap-3 p-3 rounded-lg border border-white/10 bg-white/5">
                        {previewUrl && (
                          <img
                            src={previewUrl}
                            alt="Vista previa"
                            className="max-h-32 rounded-md border border-white/10"
                          />
                        )}
                        <div className="flex-1 text-sm">
                          <div className="font-medium truncate">{file.name}</div>
                          <div className="text-xs muted mt-1">
                            {(file.size / 1024).toFixed(1)} KB · {file.type}
                          </div>
                          <button
                            type="button"
                            className="text-xs text-red-300 mt-2 hover:text-red-200"
                            onClick={() => clearSelection(i.content_id)}
                            disabled={isBusy}
                          >
                            Cambiar imagen
                          </button>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <button
                          className="btn btn-primary"
                          disabled={isBusy}
                          onClick={() => runAudit(i.content_id)}
                        >
                          {isBusy ? "Validando imagen…" : "Validar imagen"}
                        </button>
                        <button
                          className="btn btn-secondary"
                          disabled={isBusy}
                          onClick={() => clearSelection(i.content_id)}
                        >
                          Cancelar
                        </button>
                      </div>
                      {isBusy && (
                        <div className="text-xs muted">
                          Gemini Vision está analizando tu imagen contra las reglas de la
                          marca…
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </main>
  );
}
