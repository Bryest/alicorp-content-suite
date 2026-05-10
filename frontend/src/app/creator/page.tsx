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

// Templates por defecto para cada tipo de contenido. Se autorrellenan al cambiar el dropdown.
const REQUEST_TEMPLATES: Record<string, string> = {
  product_description:
    "Escribe una descripción atractiva del producto que destaque sus ingredientes, origen y diferenciador clave. Tono coherente con el manual de marca.",
  video_script:
    "Crea un guion de video corto con apertura visual, beneficio principal y cierre con call to action claro.",
  image_prompt:
    "Genera una descripción visual detallada para crear una imagen del producto siguiendo las reglas de marca (paleta, fondo, composición, encuadre, iluminación y mood).",
  social_post:
    "Escribe un post de Instagram emocional que conecte con la audiencia objetivo. Termina con un call to action y hashtags relevantes.",
  tagline:
    "Crea un tagline corto y memorable que capture la esencia de la marca y sea fácil de recordar.",
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
    name: "Inka Chips",
    product_type: "Snack de papas nativas peruanas, sin colorantes ni saborizantes artificiales",
    tone: "Orgulloso, cercano y auténtico — celebra la identidad andina sin caer en folclorismo",
    audience: "Familias peruanas y consumidores 25-45 años que valoran ingredientes locales y naturales",
    visual_rules: "Paleta tierra (terracota, ocre, marrón) + acentos rojo andino. Fondos neutros claros. Fotografía natural mostrando textura de papas nativas y origen agrícola. Logo siempre visible (mín. 80px). Evitar saturación digital o filtros agresivos.",
    forbidden_words: "barato, instantáneo, artificial, frito",
    key_messages: "papas nativas del Perú, ingredientes 100% naturales, sabor auténtico andino",
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
  const [request, setRequest] = useState(REQUEST_TEMPLATES.product_description);
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<Generation | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [brandDetails, setBrandDetails] = useState<any | null>(null);
  const [showBrandPanel, setShowBrandPanel] = useState(false);

  // Cuando cambia el tipo de contenido, autorrellenar con el template correspondiente
  function handleContentTypeChange(newType: string) {
    setContentType(newType);
    setRequest(REQUEST_TEMPLATES[newType] || REQUEST_TEMPLATES.product_description);
  }

  // Cuando cambia la marca seleccionada, traer el manual completo
  useEffect(() => {
    if (!activeBrand) {
      setBrandDetails(null);
      return;
    }
    let cancelled = false;
    api
      .getBrand(activeBrand)
      .then((b) => {
        if (!cancelled) setBrandDetails(b);
      })
      .catch(() => {
        if (!cancelled) setBrandDetails(null);
      });
    return () => {
      cancelled = true;
    };
  }, [activeBrand]);

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
                {b.name} · {formatBrandTimestamp(b.created_at)}
              </option>
            ))}
          </select>
          {brandDetails && (
            <div className="mt-2">
              <button
                type="button"
                onClick={() => setShowBrandPanel((v) => !v)}
                className="text-xs muted hover:text-white underline"
              >
                {showBrandPanel ? "▼ Ocultar manual" : "▶ Ver manual de la marca"}
              </button>
              {showBrandPanel && (
                <div className="mt-2 p-3 rounded-lg border border-white/10 bg-white/[0.03] space-y-2 text-sm">
                  <div className="text-xs muted">
                    <strong>{brandDetails.name}</strong> ·{" "}
                    {brandDetails.product_type || "sin tipo"}
                  </div>
                  {brandDetails.sections &&
                    Object.entries(brandDetails.sections).map(([k, v]) => (
                      <div key={k}>
                        <div className="text-xs uppercase tracking-wide muted">
                          {humanSection(k)}
                        </div>
                        <div className="text-sm mt-0.5">{v as string}</div>
                      </div>
                    ))}
                </div>
              )}
            </div>
          )}
        </div>
        <div>
          <label className="text-xs uppercase tracking-wide muted">Tipo de contenido</label>
          <select
            className="select mt-1"
            value={contentType}
            onChange={(e) => handleContentTypeChange(e.target.value)}
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
          Tip: usa palabras prohibidas como "barato" para ver el bloqueo de marca en acción.
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
              <>
                <div className="border border-white/10 rounded-lg p-3 bg-white/5 whitespace-pre-wrap">
                  {out.content}
                </div>
                <div className="flex items-center justify-between text-xs muted">
                  <span>{wordCount(out.content)} palabras · {out.content.length} caracteres</span>
                  <button
                    type="button"
                    onClick={() => submit({ preventDefault: () => {} } as React.FormEvent)}
                    disabled={busy}
                    className="text-xs underline hover:text-white"
                  >
                    Regenerar
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function wordCount(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function formatBrandTimestamp(iso: string): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const now = new Date();
    const sameDay =
      d.getFullYear() === now.getFullYear() &&
      d.getMonth() === now.getMonth() &&
      d.getDate() === now.getDate();
    const time = d.toLocaleTimeString("es-PE", {
      hour: "2-digit",
      minute: "2-digit",
    });
    if (sameDay) return `hoy ${time}`;
    const date = d.toLocaleDateString("es-PE", {
      day: "2-digit",
      month: "2-digit",
    });
    return `${date} ${time}`;
  } catch {
    return iso;
  }
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
