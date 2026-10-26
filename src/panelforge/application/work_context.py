"""Optional correlation for work scheduled within a caller's synchronous scope."""
from contextvars import ContextVar

llm_owner_prefix: ContextVar[str] = ContextVar("llm_owner_prefix", default="llm")
