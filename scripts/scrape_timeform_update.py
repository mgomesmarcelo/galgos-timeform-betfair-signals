import sys
from pathlib import Path

import pandas as pd
from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from src.config import settings
from src.utils.dates import ensure_day_folder
from src.scrapers.timeform import scrape_timeform_for_races


def _ensure_output_dir(name: str) -> Path:
	"""Garante diretório base em data/<name> e retorna o caminho."""
	out_dir = settings.DATA_DIR / name
	out_dir.mkdir(parents=True, exist_ok=True)
	return out_dir


def main() -> None:
	logger.remove()
	logger.add(sys.stderr, level=settings.LOG_LEVEL)

	day_dir = ensure_day_folder(settings.DATA_DIR)
	links_csv = day_dir / "race_links.csv"
	if not links_csv.exists():
		logger.error("Arquivo não encontrado: {}. Execute primeiro scripts/scrape_betfair_index.py", links_csv)
		return

	df = pd.read_csv(links_csv)
	rows = df.to_dict(orient="records")

	# Acumula todas as corridas do dia
	forecast_rows: list[dict] = []
	top3_rows: list[dict] = []

	for upd in scrape_timeform_for_races(rows):
		if upd.get("TimeformForecast"):
			forecast_rows.append({
				"track_name": upd["track_name"],
				"race_time_iso": upd["race_time_iso"],
				"TimeformForecast": upd["TimeformForecast"],
			})
			logger.info("Coletado (TimeformForecast): {} {}", upd["track_name"], upd["race_time_iso"])

		top_fields = {k: upd.get(k) for k in ["TimeformTop1", "TimeformTop2", "TimeformTop3"] if upd.get(k)}
		if top_fields:
			row = {
				"track_name": upd["track_name"],
				"race_time_iso": upd["race_time_iso"],
			}
			row.update(top_fields)
			top3_rows.append(row)
			logger.info("Coletado (TimeformTop3): {} {}", upd["track_name"], upd["race_time_iso"])

	# Escreve dois CSVs diários: data/TimeformForecast/YYYY-MM-DD.csv e data/timeform_top3/YYYY-MM-DD.csv
	from src.utils.dates import today_str
	date_str = today_str()

	forecast_dir = _ensure_output_dir("TimeformForecast")
	forecast_path = forecast_dir / f"TimeformForecast_{date_str}.csv"
	if forecast_rows:
		pd.DataFrame(forecast_rows).to_csv(forecast_path, index=False, encoding=settings.CSV_ENCODING)
	else:
		pd.DataFrame([], columns=["track_name", "race_time_iso", "TimeformForecast"]).to_csv(forecast_path, index=False, encoding=settings.CSV_ENCODING)
	logger.info("Arquivo consolidado salvo: {}", forecast_path)

	top3_dir = _ensure_output_dir("timeform_top3")
	top3_path = top3_dir / f"timeform_top3_{date_str}.csv"
	if top3_rows:
		df_top = pd.DataFrame(top3_rows)
		for col in ["TimeformTop1", "TimeformTop2", "TimeformTop3"]:
			if col not in df_top.columns:
				df_top[col] = pd.NA
		df_top = df_top[["track_name", "race_time_iso", "TimeformTop1", "TimeformTop2", "TimeformTop3"]]
		df_top.to_csv(top3_path, index=False, encoding=settings.CSV_ENCODING)
	else:
		pd.DataFrame([], columns=["track_name", "race_time_iso", "TimeformTop1", "TimeformTop2", "TimeformTop3"]).to_csv(top3_path, index=False, encoding=settings.CSV_ENCODING)
	logger.info("Arquivo consolidado salvo: {}", top3_path)


if __name__ == "__main__":
	main()
