const STATUS_LABELS: Record<string, string> = {
  pending: "Pendiente",
  approved_text: "Texto aprobado",
  approved: "Publicación aprobada",
  rejected: "Rechazado",
  blocked: "Necesita ajuste",
};

export default function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "pending"
      ? "badge badge-pending"
      : status === "approved_text"
      ? "badge badge-text"
      : status === "approved"
      ? "badge badge-approved"
      : status === "rejected"
      ? "badge badge-rejected"
      : "badge badge-blocked";
  const label = STATUS_LABELS[status] || status.replace("_", " ");
  return <span className={cls}>{label}</span>;
}
