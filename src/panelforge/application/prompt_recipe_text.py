"""Recipe-scoped instruction templates; historical callers retain exact defaults."""
from contextlib import contextmanager
from contextvars import ContextVar
from string import Formatter


_texts = ContextVar("prompt_recipe_texts", default=None)


@contextmanager
def using_prompt_texts(texts):
    token = _texts.set(texts)
    try:
        yield
    finally:
        _texts.reset(token)


def prompt_text(key, default, **values):
    texts = _texts.get()
    template = texts.get(key, default) if texts is not None else default
    return template.format_map(values) if values else template


def template_fields(value):
    return {field for _, field, _, _ in Formatter().parse(value) if field is not None}


def validate_template(value, baseline):
    # Only named substitutions from the shipped template; no attributes/indexing.
    fields = template_fields(value)
    if fields != template_fields(baseline) or any(not name.isidentifier() for name in fields):
        raise ValueError("Conservez exactement les variables entre accolades de la consigne initiale.")
    if any(spec and ("{" in spec or "}" in spec) for _, _, spec, _ in Formatter().parse(value)):
        raise ValueError("Les variables imbriquées ne sont pas autorisées.")
