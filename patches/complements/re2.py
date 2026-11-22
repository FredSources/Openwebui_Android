"""re2 — shim sur `re` (google-re2 est natif et non fourni sur Android).

API utilisée par open_webui (knowledge_fs) : Options(), compile(pattern,
options=...), error. Les attributs max_mem/log_errors de Options sont acceptés
et ignorés : `re` (backtracking) remplace RE2, suffisant pour la recherche
dans les fichiers de connaissances et les skills.
"""
import re as _re
from re import error, escape, match, search, split, sub, findall, finditer  # noqa: F401


class Options:
    case_sensitive: bool = True
    literal: bool = False
    max_mem: int = 0
    log_errors: bool = True


def compile(pattern, options=None, flags=0):  # noqa: A001
    if options is not None:
        if not getattr(options, "case_sensitive", True):
            flags |= _re.IGNORECASE
        if getattr(options, "literal", False):
            pattern = _re.escape(pattern)
    return _re.compile(pattern, flags)
