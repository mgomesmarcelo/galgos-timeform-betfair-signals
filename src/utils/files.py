from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Dict, List

import pandas as pd

from ..config import settings


_INVALID_CHARS = r"[^\w\-\. ]+"
_WHITESPACE = re.compile(r"\s+")


def sanitize_name(name: str) -> str:
	clean = re.sub(_INVALID_CHARS, " ", name)
	clean = _WHITESPACE.sub(" ", clean).strip()
	return clean.replace(" ", "_")


def ensure_dir(path: Path) -> None:
	path.mkdir(parents=True, exist_ok=True)


def write_links_csv(day_dir: Path, rows: Iterable[Dict[str, object]]) -> Path:
	csv_path = day_dir / "race_links.csv"
	df = pd.DataFrame(list(rows))
	if not df.empty:
		df.to_csv(csv_path, index=False, encoding=settings.CSV_ENCODING)
	else:
		pd.DataFrame([]).to_csv(csv_path, index=False, encoding=settings.CSV_ENCODING)
	return csv_path


def append_or_create_csv(csv_path: Path, row: Dict[str, object]) -> None:
	if csv_path.exists():
		df = pd.read_csv(csv_path)
		df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
		df.to_csv(csv_path, index=False, encoding=settings.CSV_ENCODING)
	else:
		pd.DataFrame([row]).to_csv(csv_path, index=False, encoding=settings.CSV_ENCODING)


def upsert_single_row_csv(csv_path: Path, update_row: Dict[str, object]) -> None:
	"""Garante um único registro no CSV. Se existir, atualiza colunas; senão cria.
	Mantém campos existentes e aplica os do update_row por cima.
	"""
	if csv_path.exists():
		try:
			df_existing = pd.read_csv(csv_path)
			base = {}
			if not df_existing.empty:
				# usa a última linha como base
				base = df_existing.iloc[-1].to_dict()
			base.update(update_row)
			pd.DataFrame([base]).to_csv(csv_path, index=False, encoding=settings.CSV_ENCODING)
			return
		except Exception:
			# em caso de erro de leitura, cria do zero
			pass
	# cria do zero
	pd.DataFrame([update_row]).to_csv(csv_path, index=False, encoding=settings.CSV_ENCODING)


def condense_csv_to_single_row(csv_path: Path) -> None:
	"""Condensa um CSV potencialmente duplicado em uma única linha combinando colunas.
	- Mantém a última ocorrência não vazia para cada coluna.
	- Se o arquivo estiver vazio, mantém como CSV vazio com cabeçalhos (se houver).
	"""
	if not csv_path.exists():
		return
	try:
		df = pd.read_csv(csv_path)
		if df.empty:
			# mantém vazio
			df.to_csv(csv_path, index=False, encoding=settings.CSV_ENCODING)
			return
		aggregated: Dict[str, object] = {}
		for col in df.columns:
			series = df[col]
			# pega a última célula não nula/não vazia
			val = None
			for item in series[::-1]:
				if pd.notna(item) and str(item).strip() != "":
					val = item
					break
			aggregated[col] = val if val is not None else (series.iloc[-1] if len(series) > 0 else None)
		pd.DataFrame([aggregated]).to_csv(csv_path, index=False, encoding=settings.CSV_ENCODING)
	except Exception:
		# Se falhar por qualquer motivo, não altera o arquivo
		return


def upsert_row_by_keys(csv_path: Path, new_row: Dict[str, object], key_fields: List[str]) -> None:
	"""Mantém múltiplas linhas por corrida, mas 1 por combinação de chaves.
	Se existir linha com as mesmas chaves, substitui totalmente por new_row;
	senão, acrescenta uma nova linha.
	"""
	if csv_path.exists():
		try:
			df = pd.read_csv(csv_path)
			if not df.empty and all(k in df.columns for k in key_fields):
				mask = pd.Series([True] * len(df))
				for k in key_fields:
					mask &= (df[k].astype(str) == str(new_row.get(k, "")))
				if mask.any():
					# substitui a(s) linhas encontradas pelo new_row, sem preservar colunas antigas extras
					out_df = pd.concat([df[~mask], pd.DataFrame([new_row])], ignore_index=True)
					# restringe colunas ao superset das colunas desejadas
					out_df = out_df[list(new_row.keys())]
					out_df.to_csv(csv_path, index=False, encoding=settings.CSV_ENCODING)
					return
			# não encontrou linha com as chaves -> append
			df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
			df.to_csv(csv_path, index=False, encoding=settings.CSV_ENCODING)
			return
		except Exception:
			pass
	# arquivo não existe ou erro de leitura -> cria novo
	pd.DataFrame([new_row]).to_csv(csv_path, index=False, encoding=settings.CSV_ENCODING)
