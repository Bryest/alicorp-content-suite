"use client";
import { useEffect, useState } from "react";
import { api, auth } from "@/lib/api";
import Header from "@/components/Header";
import StatusBadge from "@/components/StatusBadge";
import ConflictAlert from "@/components/ConflictAlert";

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
      <Header title="Creator workspace" />

      <div className="flex gap-2 mb-5">
        {(["brand", "generate", "history"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`btn ${tab === t ? "btn-primary" : "btn-secondary"}`}
          >
            {t === "brand" ? "1 · Brand DNA" : t === "generate" ? "2 · Generate" : "3 · History"}
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
    name: "QuinoaSnack Pro",
    product_type: "Healthy snack with quinoa",
    tone: "Fun but professional",
    audience: "Gen Z, health-conscious, ages 18-26",
    visual_rules: "Lime green dominant, white background, logo minimum 80px",
    forbidden_words: "cheap, diet, artificial",
    key_messages: "real ingredients, sustainable, energizing",
  });
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

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
      onCreated();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid md:grid-cols-2 gap-5">
      <form onSubmit={submit} className="card space-y-3">
        <h2 className="font-semibold">Define the brand</h2>
        {(
          [
            ["name", "Brand name"],
            ["product_type", "Product type"],
            ["tone", "Tone of voice"],
            ["audience", "Target audience"],
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
          <label className="text-xs uppercase tracking-wide muted">Visual rules</label>
          <textarea
            className="textarea mt-1"
            value={form.visual_rules}
            onChange={(e) => setForm({ ...form, visual_rules: e.target.value })}
          />
        </div>
        <div>
          <label className="text-xs uppercase tracking-wide muted">
            Forbidden words (comma-separated)
          </label>
          <input
            className="input mt-1"
            value={form.forbidden_words}
            onChange={(e) => setForm({ ...form, forbidden_words: e.target.value })}
          />
        </div>
        <div>
          <label className="text-xs uppercase tracking-wide muted">
            Key messages (comma-separated, in priority order)
          </label>
          <input
            className="input mt-1"
            value={form.key_messages}
            onChange={(e) => setForm({ ...form, key_messages: e.target.value })}
          />
        </div>
        {err && <div className="text-red-400 text-sm">{err}</div>}
        <button className="btn btn-primary" disabled={busy} type="submit">
          {busy ? "Generating manual…" : "Generate brand manual + index in RAG"}
        </button>
      </form>

      <div className="card">
        <h2 className="font-semibold mb-3">Result</h2>
        {!result && <div className="muted text-sm">Submit the form to see the structured manual + chunk count.</div>}
        {result && (
          <div className="space-y-3 text-sm">
            <div>
              <span className="badge badge-approved">{result.sections_embedded} sections embedded</span>
            </div>
            {Object.entries(result.sections || {}).map(([section, content]) => (
              <div key={section}>
                <div className="text-xs uppercase tracking-wide muted">{section}</div>
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
  const [request, setRequest] = useState("Write a 50-word Instagram description for our snack");
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<Generation | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!activeBrand) return setErr("Create a brand first.");
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
      onGenerated();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid md:grid-cols-2 gap-5">
      <form onSubmit={submit} className="card space-y-3">
        <h2 className="font-semibold">Creative engine</h2>
        <div>
          <label className="text-xs uppercase tracking-wide muted">Brand</label>
          <select
            className="select mt-1"
            value={activeBrand}
            onChange={(e) => setActiveBrand(e.target.value)}
          >
            {brands.length === 0 && <option value="">— create a brand first —</option>}
            {brands.map((b) => (
              <option key={b.brand_id} value={b.brand_id}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs uppercase tracking-wide muted">Content type</label>
          <select
            className="select mt-1"
            value={contentType}
            onChange={(e) => setContentType(e.target.value)}
          >
            <option value="product_description">Product description</option>
            <option value="video_script">Video script</option>
            <option value="image_prompt">Image prompt</option>
            <option value="social_post">Social post</option>
            <option value="tagline">Tagline</option>
          </select>
        </div>
        <div>
          <label className="text-xs uppercase tracking-wide muted">Request</label>
          <textarea
            className="textarea mt-1"
            value={request}
            onChange={(e) => setRequest(e.target.value)}
          />
        </div>
        {err && <div className="text-red-400 text-sm">{err}</div>}
        <button className="btn btn-primary" disabled={busy} type="submit">
          {busy ? "Generating…" : "Run RAG + generate"}
        </button>
        <div className="text-xs muted">
          Try forbidden words like "cheap" in the request to see the conflict path.
        </div>
      </form>

      <div className="card">
        <h2 className="font-semibold mb-3">Output</h2>
        {!out && <div className="muted text-sm">Generation result + retrieved RAG chunks shown here.</div>}
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
                <div className="text-xs uppercase tracking-wide muted mb-1">RAG retrieval</div>
                <ul className="space-y-1 text-sm">
                  {out.retrieved_chunks.map((c) => (
                    <li key={c.chunk_id} className="flex justify-between">
                      <span>{c.section}</span>
                      <span className="muted">sim={c.similarity.toFixed(3)}</span>
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
    return <div className="card muted">Nothing yet — generate some content first.</div>;
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
              <div className="muted">Audit summary: {i.audit_result.summary}</div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
