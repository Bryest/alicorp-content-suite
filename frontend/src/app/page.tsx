"use client";
import { useEffect, useState } from "react";
import { api, auth, landingPathForRole } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("creator@test.com");
  const [password, setPassword] = useState("Test1234!");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [demoUsers, setDemoUsers] = useState<
    Array<{ email: string; password: string; role: string }>
  >([]);
  const [mockMode, setMockMode] = useState<Record<string, boolean> | null>(null);

  useEffect(() => {
    if (auth.token()) {
      window.location.href = landingPathForRole(auth.role() || "creator");
      return;
    }
    api.demoUsers().then((d) => setDemoUsers(d.users)).catch(() => {});
    api.health().then((h) => setMockMode(h.mock_mode)).catch(() => {});
  }, []);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const r = await api.login(email, password);
      auth.set(r.access_token, r.role, r.email);
      window.location.href = landingPathForRole(r.role);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="max-w-md mx-auto px-6 pt-20">
      <div className="text-center mb-8">
        <div className="text-xs uppercase tracking-widest muted">
          Alicorp · IAGen Pleno Challenge
        </div>
        <h1 className="text-3xl font-bold mt-2">Content Suite</h1>
        <p className="muted text-sm mt-2">
          Brand-aware content generation with RAG + multimodal audit
        </p>
      </div>

      <form onSubmit={handleLogin} className="card space-y-4">
        <div>
          <label className="text-xs uppercase tracking-wide muted">Email</label>
          <input
            className="input mt-1"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="text-xs uppercase tracking-wide muted">Password</label>
          <input
            className="input mt-1"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        {err && <div className="text-red-400 text-sm">{err}</div>}
        <button className="btn btn-primary w-full justify-center" disabled={busy} type="submit">
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>

      {demoUsers.length > 0 && (
        <div className="mt-6 card">
          <div className="text-xs uppercase tracking-wide muted mb-3">Demo accounts</div>
          <div className="space-y-2">
            {demoUsers.map((u) => (
              <button
                key={u.email}
                onClick={() => {
                  setEmail(u.email);
                  setPassword(u.password);
                }}
                className="w-full text-left p-2 rounded-md hover:bg-white/5 transition flex justify-between items-center"
              >
                <div>
                  <div className="text-sm">{u.email}</div>
                  <div className="text-xs muted">{u.role}</div>
                </div>
                <div className="text-xs muted">tap to fill</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {mockMode && (
        <div className="mt-4 text-center text-xs muted">
          Mode: {Object.entries(mockMode).map(([k, v]) => `${k}:${v ? "mock" : "real"}`).join(" · ")}
        </div>
      )}
    </main>
  );
}
