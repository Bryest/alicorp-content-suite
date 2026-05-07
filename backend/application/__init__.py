"""
Application services — orchestrate the domain + infrastructure layers.

This is where use cases live: BrandService for Module I, ContentService
for Module II, AuditService for Module III. Module IV (Langfuse tracing)
is woven into all three via a `Tracer` injected at construction.
"""
