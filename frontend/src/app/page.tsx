"use client";
import { useEffect, useState } from "react";
import { api, auth, landingPathForRole } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (auth.token()) {
      window.location.href = landingPathForRole(auth.role() || "creator");
    }
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
        <h1 className="text-3xl font-bold">Content Suite</h1>
        <p className="muted text-sm mt-3">
          Generación de contenido alineada a marca con RAG
        </p>
      </div>

      <form onSubmit={handleLogin} className="card space-y-4">
        <div>
          <label className="text-xs uppercase tracking-wide muted">Correo</label>
          <input
            className="input mt-1"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </div>
        <div>
          <label className="text-xs uppercase tracking-wide muted">Contraseña</label>
          <input
            className="input mt-1"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </div>
        {err && <div className="text-red-400 text-sm">{err}</div>}
        <button className="btn btn-primary w-full justify-center" disabled={busy} type="submit">
          {busy ? "Iniciando sesión…" : "Iniciar sesión"}
        </button>
      </form>
    </main>
  );
}
