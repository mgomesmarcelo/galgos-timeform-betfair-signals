from dataclasses import dataclass
from pathlib import Path

# Entrada (tipo de aposta) — rótulos
ENTRY_TYPE_LABELS: dict[str, str] = {
    "back": "back",
    "lay": "lay",
}
ENTRY_TYPE_LABELS_INV: dict[str, str] = {v: k for k, v in ENTRY_TYPE_LABELS.items()}

# Regras (estratégias de seleção) — ids e rótulos
RULE_LABELS: dict[str, str] = {
    "lider_volume_total": "líder volume total",
    "terceiro_queda50": "terceiro_queda50",
}
RULE_LABELS_INV: dict[str, str] = {v: k for k, v in RULE_LABELS.items()}


@dataclass(frozen=True)
class Settings:
	# Diretórios
	DATA_DIR: Path = Path(__file__).resolve().parents[1] / "data"

	# URLs bases (ajuste conforme necessário/região)
	BETFAIR_BASE_URL: str = "https://www.betfair.com/exchange/plus/"
	BETFAIR_GREYHOUND_RACING_URL: str = "https://www.betfair.com/exchange/plus/en/greyhound-racing-betting-4339"
	TIMEFORM_BASE_URL: str = "https://www.timeform.com/greyhound-racing"
	ODDSCHECKER_BASE_URL: str = "https://www.oddschecker.com"
	ODDSCHECKER_HORSE_RACING_URL: str = "https://www.oddschecker.com/horse-racing"

	# Selenium/driver
	SELENIUM_HEADLESS: bool = False
	SELENIUM_PAGELOAD_TIMEOUT_SEC: int = 45
	SELENIUM_IMPLICIT_WAIT_SEC: int = 5
	SELENIUM_EXPLICIT_WAIT_SEC: int = 15

	# Throttling (Timeform)
	TIMEFORM_MIN_DELAY_SEC: float = 0.5
	TIMEFORM_MAX_DELAY_SEC: float = 1.0



	# CSV
	CSV_ENCODING: str = "utf-8-sig"

	# Logs
	LOG_LEVEL: str = "INFO"


settings = Settings()
