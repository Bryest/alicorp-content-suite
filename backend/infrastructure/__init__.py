"""
Infrastructure layer.

Each adapter implements a domain port. Every external integration is
written so that, when its API key is absent, the adapter switches to
a deterministic in-memory implementation. The system runs end-to-end
with zero credentials — perfect for evaluators trying it locally before
provisioning accounts.
"""
