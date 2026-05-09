"use client";
import { useEffect, useState } from "react";
import { api, auth, humanSection } from "@/lib/api";
import Header from "@/components/Header";
import StatusBadge from "@/components/StatusBadge";
import ConflictAlert from "@/components/ConflictAlert";
import Toast from "@/components/Toast";

type Brand = { brand_id: string; name: string; product_type: string; created_at: string };
type Generation = {
  content_id: string | null;
  content: string | null;
  conflicts: Array<{ rule: string; violation: string; suggestion: string }>;
  retrieved_chunks: Array<{ chunk_id: string; section: string; similarity: number }>;
  status: string;
};

export default function CreatorPage() {
  const [tab, setTab] = useState<"brand" | "generate" | "history">("brand");
  const [brands, setBrands] = useState<Brand[]>([]);
  const [activeBrand, setActiveBrand] = useState<string>("");
  const [history, setHistory] = useState<any[]>([]);

  useEffect(() => {
    if (!auth.token()) window.location.href = "/";
    if (auth.role() !== "creator") window.location.href = "/";
    refresh();
  }, []);

  async function refresh() {
    const bs = await api.listBrands();
    setBrands(bs);
    if (!activeBrand && bs.length) setActiveBrand(bs[0].brand_id);
    setHistory(await api.listContent());
  }

  return (
    <main className="max-w-5xl mx-auto px-6 py-8">
      <Header title="Espacio del Creador" />

      <div className="flex gap-2 mb-5">
        {(["brand", "generate", "history"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`btn ${tab === t ? "btn-primary" : "btn-secondary"}`}
          >
            {t === "brand" ? "1 · Define tu marca" : t === "generate" ? "2 · Crear contenido" : "3 · Mis publicaciones"}
          </button>
        ))}
      </div>

      {tab === "brand" && <BrandDNAForm onCreated={refresh} />}
      {tab === "generate" && (
        <GenerateForm
          brands={brands}
          activeBrand={activeBrand}
          setActiveBrand={setActiveBrand}
          onGenerated={refresh}
        />
      )}
      {tab === "history" && <HistoryView items={history} />}
    </main>
  );
}

function BrandDNAForm({ onCreated }: { onCreated: () => void }) {
  const [form, setForm] = useState({
    name: "Snack Andino",
    product_type: "Snack saludable a base de quinua y kiwicha",
    tone: "Cálido y profesional, cercano al consumidor peruano",
    audience: "Adultos jóvenes peruanos 25-40 años, conscientes de su salud",
    visual_rules: "Verde olivo dominante, fondo claro, fotografía natural sin filtros, logo mínimo 80px",
    forbidden_words: "barato, instantáneo, artificial",
    key_messages: "ingredientes andinos, energía natural, hecho en Perú",
  });
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const r = await api.createBrand({
        ...form,
        forbidden_words: form.forbidden_words.split(",").map((s) => s.trim()).filter(Boolean),
        key_messages: form.key_messages.split(",").map((s) => s.trim()).filter(Boolean),
      });
      setResult(r);
      setToast(`Marca "${r.name}" creada e indexada en RAG`);
      onCreated();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid md:grid-cols-2 gap-5">
      {toast && <Toast message={toast} variant="success" onDismiss={() => setToast(null)} />}
      <form onSubmit={submit} className="card space-y-3">
        <h2 className="font-semibold">Define tu marca</h2>
        {(
          [
            ["name", "Nombre de la marca"],
            ["product_type", "Tipo de producto"],
            ["tone", "Tono de voz"],
            ["audience", "Audiencia objetivo"],
          ] as const
        ).map(([k, label]) => (
          <div key={k}>
            <label className="text-xs uppercase tracking-wide muted">{label}</label>
            <input
              className="input mt-1"
              value={(form as any)[k]}
              onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              required
            />
          </div>
        ))}
        <div>
          <label className="text-xs uppercase tracking-wide muted">Reglas visuales</label>
          <textarea
            className="textarea mt-1"
            value={form.visual_rules}
            onChange={(e) => setForm({ ...form, visual_rules: e.target.value })}
          />
        </div>
        <div>
          <label className="text-xs uppercase tracking-wide muted">
            Palabras prohibidas (separadas por coma)
          </label>
          <input
            className="input mt-1"
            value={form.forbidden_words}
            onChange={(e) => setForm({ ...form, forbidden_words: e.target.value })}
          />
        </div>
        <div>
          <label className="text-xs uppercase tracking-wide muted">
            Mensajes clave (separados por coma, en orden de prioridad)
          </label>
          <input
            className="input mt-1"
            value={form.key_messages}
            onChange={(e) => setForm({ ...form, key_messages: e.target.value })}
          />
        </div>
        {err && <div className="text-red-400 text-sm">{err}</div>}
        <button className="btn btn-primary" disabled={busy} type="submit">
          {busy ? "Creando manual…" : "Crear manual de marca"}
        </button>
      </form>

      <div className="card">
        <h2 className="font-semibold mb-3">Resultado</h2>
        {!result && <div className="muted text-sm">Envía el formulario para ver el manual estructurado y las secciones indexadas.</div>}
        {result && (
          <div className="space-y-3 text-sm">
            <div>
              <span className="badge badge-approved">{result.sections_embedded} secciones indexadas</span>
            </div>
            {Object.entries(result.sections || {}).map(([section, content]) => (
              <div key={section}>
                <div className="text-xs uppercase tracking-wide muted">{humanSection(section)}</div>
                <div className="mt-1">{content as string}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function GenerateForm({
  brands,
  activeBrand,
  setActiveBrand,
  onGenerated,
}: {
  brands: Brand[];
  activeBrand: string;
  setActiveBrand: (id: string) => void;
  onGenerated: () => void;
}) {
  const [contentType, setContentType] = useState("product_description");
  const [request, setRequest] = useState(
    "Crea una descripción de 50 palabras para Instagram que destaque los ingredientes andinos y el origen peruano del producto",
  );
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<Generation | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!activeBrand) return setErr("Crea una marca primero.");
    setErr(null);
    setBusy(true);
    setOut(null);
    try {
      const r = await api.generate({
        brand_id: activeBrand,
        content_type: contentType,
        request,
      });
      setOut(r);
      if (r.status === "blocked") {
        setToast("Generación bloqueada: revisa los conflictos de marca");
      } else {
        setToast("Contenido generado y enviado a aprobación");
      }
      onGenerated();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid md:grid-cols-2 gap-5">
      {toast && (
        <Toast
          message={toast}
          variant={out?.status === "blocked" ? "error" : "success"}
          onDismiss={() => setToast(null)}
        />
      )}
      <form onSubmit={submit} className="card space-y-3">
        <h2 className="font-semibold">Generador de contenido</h2>
        <div>
          <label className="text-xs uppercase tracking-wide muted">Marca</label>
          <select
            className="select mt-1"
            value={activeBrand}
            onChange={(e) => setActiveBrand(e.target.value)}
          >
            {brands.length === 0 && <option value="">— crea una marca primero —</option>}
            {brands.map((b) => (
              <option key={b.brand_id} value={b.brand_id}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs uppercase tracking-wide muted">Tipo de contenido</label>
          <select
            className="select mt-1"
            value={contentType}
            onChange={(e) => setContentType(e.target.value)}
          >
            <option value="product_description">Descripción de producto</option>
            <option value="video_script">Guion de video</option>
            <option value="image_prompt">Prompt para imagen</option>
            <option value="social_post">Post para redes sociales</option>
            <option value="tagline">Tagline</option>
          </select>
        </div>
        <div>
          <label className="text-xs uppercase tracking-wide muted">¿Qué quieres generar?</label>
          <textarea
            className="textarea mt-1"
            value={request}
            onChange={(e) => setRequest(e.target.value)}
          />
        </div>
        {err && <div className="text-red-400 text-sm">{err}</div>}
        <button className="btn btn-primary" disabled={busy} type="submit">
          {busy ? "Generando…" : "Generar contenido"}
        </button>
        <div className="text-xs muted">
          Tip: prueba con palabras prohibidas (ej. "cheap") en tu pedido para ver cómo el sistema bloquea contenido fuera de marca.
        </div>
      </form>

      <div className="card">
        <h2 className="font-semibold mb-3">Resultado</h2>
        {!out && <div className="muted text-sm">El contenido generado y las referencias usadas aparecerán aquí.</div>}
        {out && (
          <div className="space-y-3">
            <StatusBadge status={out.status} />
            <ConflictAlert conflicts={out.conflicts} />
            {out.content && (
              <div className="border border-white/10 rounded-lg p-3 bg-white/5 whitespace-pre-wrap">
                {out.content}
              </div>
            )}
            {out.retrieved_chunks?.length > 0 && (
              <div>
                <div className="text-xs uppercase tracking-wide muted mb-1">Referencias de marca usadas</div>
                <ul className="space-y-1 text-sm">
                  {out.retrieved_chunks.map((c) => (
                    <li key={c.chunk_id} className="flex justify-between">
                      <span>{humanSection(c.section)}</span>
                      <span className="muted">relevancia {(c.similarity * 100).toFixed(0)}%</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function HistoryView({ items }: { items: any[] }) {
  if (!items.length)
    return <div className="card muted">Aún no hay contenido — genera algo primero.</div>;
  return (
    <div className="space-y-3">
      {items.map((i) => (
        <div key={i.content_id} className="card">
          <div className="flex justify-between items-start gap-3">
            <div>
              <div className="text-xs uppercase tracking-wide muted">{i.content_type}</div>
              <div className="text-sm mt-1">{i.original_request}</div>
              {i.content && <div className="mt-2 text-sm border-t border-white/10 pt-2 whitespace-pre-wrap">{i.content}</div>}
            </div>
            <StatusBadge status={i.status} />
          </div>
          {i.audit_result && (
            <div className="mt-3 text-xs">
              <div className="muted">Resumen de validación: {i.audit_result.summary}</div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
