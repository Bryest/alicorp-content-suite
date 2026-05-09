"use client";
import { useEffect, useState } from "react";
import { auth } from "@/lib/api";

export default function Header({ title }: { title: string }) {
  const [email, setEmail] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  useEffect(() => {
    setEmail(auth.email());
    setRole(auth.role());
  }, []);

  return (
    <header className="flex items-center justify-between mb-6 pb-4 border-b border-white/10">
      <div>
        <div className="text-xs uppercase tracking-widest text-white/50">
          Content Suite · Alicorp
        </div>
        <h1 className="text-2xl font-bold mt-1">{title}</h1>
      </div>
      <div className="flex items-center gap-3">
        {email && (
          <div className="text-right">
            <div className="text-sm">{email}</div>
            <div className="text-xs muted">{role}</div>
          </div>
        )}
        <button
          className="btn btn-secondary"
          onClick={() => {
            auth.clear();
            window.location.href = "/";
          }}
        >
          Cerrar sesión
        </button>
      </div>
    </header>
  );
}
