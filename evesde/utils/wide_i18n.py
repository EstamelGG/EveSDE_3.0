#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SDE 多语宽列：de_name / en_description 等，不含裸 name / description 列。"""

from typing import Any, Dict, List, Optional, Tuple

LANGS: Tuple[str, ...] = ("de", "en", "es", "fr", "ja", "ko", "ru", "zh")

NAME_COLS: List[str] = [f"{lang}_name" for lang in LANGS]
DESC_COLS: List[str] = [f"{lang}_description" for lang in LANGS]

TextMap = Dict[str, Optional[str]]


def _norm(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    return text or None


def wide_texts(value: Any) -> TextMap:
    if value is None:
        return {lang: None for lang in LANGS}
    if isinstance(value, str):
        text = value or None
        return {lang: text for lang in LANGS}
    if not isinstance(value, dict):
        return {lang: None for lang in LANGS}
    en = _norm(value.get("en"))
    out: TextMap = {}
    for lang in LANGS:
        text = _norm(value.get(lang))
        out[lang] = text if text is not None else en
    return out


def prefixed_name_cols(prefix: str) -> List[str]:
    return [f"{prefix}_{lang}_name" for lang in LANGS]


def prefixed_desc_cols(prefix: str) -> List[str]:
    return [f"{prefix}_{lang}_description" for lang in LANGS]


def names_ddl(prefix: str = "") -> str:
    cols = prefixed_name_cols(prefix) if prefix else NAME_COLS
    return ",\n                ".join(f"{c} TEXT" for c in cols)


def descs_ddl(prefix: str = "") -> str:
    cols = prefixed_desc_cols(prefix) if prefix else DESC_COLS
    return ",\n                ".join(f"{c} TEXT" for c in cols)


def names_row(texts: TextMap) -> Tuple[Optional[str], ...]:
    return tuple(texts[lang] for lang in LANGS)


DISPLAY_COLS: List[str] = [f"{lang}_display_name" for lang in LANGS]
TOOLTIP_COLS: List[str] = [f"{lang}_tooltip_description" for lang in LANGS]


def name_cols_sql(prefix: str = "") -> str:
    cols = prefixed_name_cols(prefix) if prefix else NAME_COLS
    return ", ".join(cols)


CONTENT_COLS: List[str] = [f"{lang}_content" for lang in LANGS]


def prefixed_content_cols(prefix: str) -> List[str]:
    return [f"{prefix}_{lang}_content" for lang in LANGS]


def contents_ddl(prefix: str = "") -> str:
    cols = prefixed_content_cols(prefix) if prefix else CONTENT_COLS
    return ",\n                ".join(f"{c} TEXT" for c in cols)


def contents_row(texts: TextMap) -> Tuple[Optional[str], ...]:
    return tuple(texts[lang] for lang in LANGS)


def row_to_texts(row: tuple) -> TextMap:
    return {lang: row[i] for i, lang in enumerate(LANGS)}
