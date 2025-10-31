from __future__ import annotations

import re
import unicodedata

_COUNTRY_SUFFIX_RE = re.compile(r"\s*\(([A-Z]{2,3})\)\s*$")
_APOSTROPHES_RE = re.compile(r"[\u2019\u2018\']+")
_NON_ALNUM_SPACE_RE = re.compile(r"[^0-9A-Za-z\s]+")
_WHITESPACE_RE = re.compile(r"\s+")
_PARENTHESES_CONTENT_RE = re.compile(r"\s*\([^\)]*\)")


def normalize_spaces(text: str) -> str:
	return _WHITESPACE_RE.sub(" ", text).strip()


def strip_country_suffix(text: str) -> str:
	return _COUNTRY_SUFFIX_RE.sub("", text)


def remove_apostrophes(text: str) -> str:
	return _APOSTROPHES_RE.sub("", text)


def strip_accents(text: str) -> str:
	nfkd = unicodedata.normalize("NFKD", text)
	return "".join([c for c in nfkd if not unicodedata.combining(c)])


def clean_horse_name(raw_name: str) -> str:
	# 1) remove sufixo país entre parênteses no fim
	name = strip_country_suffix(raw_name or "")
	# 2) normaliza espaços
	name = normalize_spaces(name)
	# 3) remove apóstrofos (Paul's -> Pauls)
	name = remove_apostrophes(name)
	# 4) remove acentos e caracteres não alfanuméricos (mantém espaços)
	name = strip_accents(name)
	name = _NON_ALNUM_SPACE_RE.sub(" ", name)
	# 5) normaliza espaços de novo
	name = normalize_spaces(name)
	# 6) Título padrão
	name = name.title()
	return name


def normalize_track_name(raw_name: str) -> str:
	name = raw_name or ""
	# remove conteúdos entre parênteses (ex.: (July))
	name = _PARENTHESES_CONTENT_RE.sub("", name)
	# remove apóstrofos e acentos
	name = remove_apostrophes(name)
	name = strip_accents(name)
	# remove sufixos comuns
	name = re.sub(r"\bDowns\b", "", name, flags=re.IGNORECASE)
	name = re.sub(r"\bRacecourse\b", "", name, flags=re.IGNORECASE)
	# remove qualquer caractere não alfanumérico exceto espaço
	name = _NON_ALNUM_SPACE_RE.sub(" ", name)
	# normaliza espaços e title case
	name = normalize_spaces(name).title()
	return name
