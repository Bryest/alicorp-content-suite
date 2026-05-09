"""
Audit context entities.

`AuditResult` is the structured outcome of a multimodal audit run.
It is *not* persisted as its own aggregate — it lives inside a
`ContentItem.audit_result` JSON column. Modeled here as a domain
entity so application + tests can build/validate it without
infrastructure imports.
"""


from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CheckItem:
    rule: str
    passed: bool
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"rule": self.rule, "passed": self.passed, "note": self.note}


@dataclass(frozen=True)
class AuditResult:
    compliant: bool
    summary: str
    checks: list[CheckItem] = field(default_factory=list)

    @property
    def final_status(self) -> str:
        return "approved" if self.compliant else "rejected"

    def to_dict(self) -> dict[str, Any]:
        return {
            "compliant": self.compliant,
            "checks": [c.to_dict() for c in self.checks],
            "summary": self.summary,
            "final_status": self.final_status,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AuditResult":
        checks = [
            CheckItem(
                rule=str(c.get("rule", "")),
                passed=bool(c.get("passed", False)),
                note=str(c.get("note", "")),
            )
            for c in (raw.get("checks") or [])
        ]
        return cls(
            compliant=bool(raw.get("compliant", False)),
            summary=str(raw.get("summary", "")),
            checks=checks,
        )
