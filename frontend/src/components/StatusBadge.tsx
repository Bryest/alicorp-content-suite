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
  return <span className={cls}>{status.replace("_", " ")}</span>;
}
