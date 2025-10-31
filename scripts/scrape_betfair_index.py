import sys
from pathlib import Path

from loguru import logger

# Ajuste de path para permitir "python scripts/..." executar imports de src
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from src.config import settings
from src.utils.dates import ensure_day_folder
from src.utils.files import sanitize_name, ensure_dir, write_links_csv
from src.scrapers.betfair_index import scrape_betfair_index


def main() -> None:
	logger.remove()
	logger.add(sys.stderr, level=settings.LOG_LEVEL)

	day_dir = ensure_day_folder(settings.DATA_DIR)
	rows = scrape_betfair_index()

	# Criar pastas por pista e preparar estrutura
	track_dirs = {}
	for row in rows:
		track_name = row.get("track_name", "unknown_track")
		safe_track = sanitize_name(track_name)
		track_dir = day_dir / safe_track
		ensure_dir(track_dir)
		track_dirs[safe_track] = track_dir

	csv_path = write_links_csv(day_dir, rows)
	logger.info("race_links.csv salvo em: {}", csv_path)


if __name__ == "__main__":
	main()
