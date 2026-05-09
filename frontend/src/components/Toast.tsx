"use client";
import { useEffect } from "react";

type ToastVariant = "success" | "error" | "info";

export interface ToastProps {
  message: string;
  variant?: ToastVariant;
  durationMs?: number;
  onDismiss: () => void;
}

const VARIANT_CLASSES: Record<ToastVariant, string> = {
  success: "border-green-400/50 bg-green-500/15 text-green-100",
  error: "border-red-400/50 bg-red-500/15 text-red-100",
  info: "border-sky-400/50 bg-sky-500/15 text-sky-100",
};

const VARIANT_ICONS: Record<ToastVariant, string> = {
  success: "✓",
  error: "✗",
  info: "ⓘ",
};

export default function Toast({
  message,
  variant = "success",
  durationMs = 3500,
  onDismiss,
}: ToastProps) {
  useEffect(() => {
    if (durationMs <= 0) return;
    const t = setTimeout(onDismiss, durationMs);
    return () => clearTimeout(t);
  }, [durationMs, onDismiss]);

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed top-6 right-6 z-50 max-w-sm animate-in fade-in slide-in-from-top-2"
    >
      <div
        className={`flex items-start gap-3 px-4 py-3 rounded-lg border shadow-lg backdrop-blur-sm ${VARIANT_CLASSES[variant]}`}
      >
        <span className="text-lg leading-none mt-0.5">{VARIANT_ICONS[variant]}</span>
        <div className="flex-1 text-sm">{message}</div>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Cerrar notificación"
          className="text-white/60 hover:text-white text-lg leading-none"
        >
          ×
        </button>
      </div>
    </div>
  );
}
