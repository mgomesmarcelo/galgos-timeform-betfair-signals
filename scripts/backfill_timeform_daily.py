import sys
from pathlib import Path

import pandas as pd
from loguru import logger

# Ajuste de path para permitir "python scripts/..." executar imports de src
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from src.config import settings


def _ensure_output_dir(name: str) -> Path:
	out_dir = settings.DATA_DIR / name
	out_dir.mkdir(parents=True, exist_ok=True)
	return out_dir


def _iter_race_csvs(day_dir: Path):
	for child in sorted(day_dir.iterdir()):
		if child.is_dir():
			# ignora pastas de saída novas
			if child.name in {"TimeformForecast", "timeform_top3", "Result"}:
				continue
			for csv_path in sorted(child.glob("*.csv")):
				yield child.name, csv_path


def _derive_race_time_from_filename(stem: str) -> str:
	# Ex.: 2025-09-20T19_21 -> 2025-09-20T19:21
	return stem.replace("_", ":", 1) if "T" in stem else stem.replace("_", ":")


def consolidate_day(day_str: str) -> None:
	day_dir = settings.DATA_DIR / day_str
	if not day_dir.exists():
		logger.warning("Pasta do dia não encontrada: {}", day_dir)
		return

	forecast_rows: list[dict] = []
	top3_rows: list[dict] = []

	for track_folder_name, csv_path in _iter_race_csvs(day_dir):
		try:
			df = pd.read_csv(csv_path, encoding=settings.CSV_ENCODING)
		except Exception as e:
			logger.error("Falha ao ler {}: {}", csv_path, e)
			continue

		if df.empty:
			continue

		# Fallbacks
		track_name_fallback = track_folder_name.replace("_", " ")
		race_time_fallback = _derive_race_time_from_filename(csv_path.stem)

		# Forecast rows: presença de coluna TimeformForecast não nula
		if "TimeformForecast" in df.columns:
			mask_fc = df["TimeformForecast"].astype(str).str.strip().ne("")
			for _, r in df[mask_fc].iterrows():
				forecast_rows.append({
					"track_name": r.get("track_name", track_name_fallback),
					"race_time_iso": r.get("race_time_iso", race_time_fallback),
					"TimeformForecast": r.get("TimeformForecast", ""),
				})

		# Top3 rows: presença de qualquer TimeformTop*
		has_top_cols = any(col in df.columns for col in ["TimeformTop1", "TimeformTop2", "TimeformTop3"])
		if has_top_cols:
			mask_any = pd.Series([False] * len(df))
			for col in ["TimeformTop1", "TimeformTop2", "TimeformTop3"]:
				if col in df.columns:
					mask_any |= df[col].astype(str).str.strip().ne("")
			for _, r in df[mask_any].iterrows():
				row = {
					"track_name": r.get("track_name", track_name_fallback),
					"race_time_iso": r.get("race_time_iso", race_time_fallback),
					"TimeformTop1": r.get("TimeformTop1", pd.NA),
					"TimeformTop2": r.get("TimeformTop2", pd.NA),
					"TimeformTop3": r.get("TimeformTop3", pd.NA),
				}
				top3_rows.append(row)

	# Escreve saídas
	forecast_dir = _ensure_output_dir("TimeformForecast")
	forecast_path = forecast_dir / f"TimeformForecast_{day_str}.csv"
	if forecast_rows:
		pd.DataFrame(forecast_rows).to_csv(forecast_path, index=False, encoding=settings.CSV_ENCODING)
	else:
		pd.DataFrame([], columns=["track_name", "race_time_iso", "TimeformForecast"]).to_csv(forecast_path, index=False, encoding=settings.CSV_ENCODING)
	logger.info("Gerado: {} ({} linhas)", forecast_path.name, len(forecast_rows))

	top3_dir = _ensure_output_dir("timeform_top3")
	top3_path = top3_dir / f"timeform_top3_{day_str}.csv"
	if top3_rows:
		df_top = pd.DataFrame(top3_rows)
		for col in ["TimeformTop1", "TimeformTop2", "TimeformTop3"]:
			if col not in df_top.columns:
				df_top[col] = pd.NA
		df_top = df_top[["track_name", "race_time_iso", "TimeformTop1", "TimeformTop2", "TimeformTop3"]]
		df_top.to_csv(top3_path, index=False, encoding=settings.CSV_ENCODING)
	else:
		pd.DataFrame([], columns=["track_name", "race_time_iso", "TimeformTop1", "TimeformTop2", "TimeformTop3"]).to_csv(top3_path, index=False, encoding=settings.CSV_ENCODING)
	logger.info("Gerado: {} ({} linhas)", top3_path.name, len(top3_rows))


def main(argv: list[str] | None = None) -> int:
	argv = argv or sys.argv[1:]
	if not argv:
		logger.error("Uso: python scripts/backfill_timeform_daily.py YYYY-MM-DD [YYYY-MM-DD ...]")
		return 1

	logger.remove()
	logger.add(sys.stderr, level=settings.LOG_LEVEL)

	for day_str in argv:
		logger.info("Consolidando dia: {}", day_str)
		consolidate_day(day_str)

	logger.info("Backfill concluído.")
	return 0


if __name__ == "__main__":
	sys.exit(main())


