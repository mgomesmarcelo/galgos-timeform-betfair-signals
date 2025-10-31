import subprocess
import sys
from pathlib import Path

from loguru import logger

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> int:
	logger.info("Executando: {}", " ".join(cmd))
	proc = subprocess.run(cmd, cwd=PROJECT_ROOT)
	return proc.returncode


def main() -> None:
	logger.remove()
	logger.add(sys.stderr, level="INFO")

	steps = [
		[sys.executable, "scripts/scrape_betfair_index.py"],
		[sys.executable, "scripts/scrape_timeform_update.py"],
	]

	for step in steps:
		code = run(step)
		if code != 0:
			logger.error("Falha ao executar: {} (código={})", step, code)
			sys.exit(code)

	logger.info("Pipeline diário concluído com sucesso.")


if __name__ == "__main__":
	main()
