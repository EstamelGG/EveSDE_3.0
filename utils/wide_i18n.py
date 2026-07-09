#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SDE 多语宽列：de_name / en_description 等，不含裸 name / description 列。"""

from typing import Any, Dict, List, Tuple

LANGS: Tuple[str, ...] = ("de", "en", "es", "fr", "ja", "ko", "ru", "zh")

NAME_COLS: List[str] = [f"{lang}_name" for lang in LANGS]
DESC_COLS: List[str] = [f"{lang}_description" for lang in LANGS]


def wide_texts(value: Any) -> Dict[str, str]:
    if value is None:
        return {lang: "" for lang in LANGS}
    if isinstance(value, str):
        return {lang: value for lang in LANGS}
    if not isinstance(value, dict):
        return {lang: "" for lang in LANGS}
    en = str(value.get("en") or "")
    return {lang: str(value.get(lang) or en) for lang in LANGS}


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


def names_row(texts: Dict[str, str]) -> Tuple[str, ...]:
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


def contents_row(texts: Dict[str, str]) -> Tuple[str, ...]:
    return tuple(texts[lang] for lang in LANGS)


def row_to_texts(row: tuple) -> Dict[str, str]:
    return {lang: (row[i] or "") for i, lang in enumerate(LANGS)}
