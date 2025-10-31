import sys
import argparse
from pathlib import Path

import pandas as pd
from loguru import logger

# Ajuste de path para permitir "python scripts/..." executar imports de src
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from src.config import settings
from src.config import RULE_LABELS
from src.analysis.signals import generate_signals, write_signals_csv


def main(argv: list[str] | None = None) -> int:
    logger.remove()
    logger.add(sys.stderr, level=settings.LOG_LEVEL)

    parser = argparse.ArgumentParser(description="Gerar sinais por regra (com entradas back e lay)")
    parser.add_argument("--source", choices=["top3", "forecast", "both"], default="both")
    parser.add_argument("--market", choices=["win", "place", "both"], default="both")
    parser.add_argument("--rule", choices=["lider_volume_total", "terceiro_queda50", "both"], default="both")
    parser.add_argument("--entry_type", choices=["back", "lay", "both"], default="both")
    parser.add_argument("--leader_share_min", type=float, default=0.5, help="Participação mínima do líder (0-1) para a regra líder_volume_total")
    args = parser.parse_args(argv)
    source = args.source
    market = args.market
    rule = args.rule
    entry_type = args.entry_type
    leader_share_min = float(args.leader_share_min)

    def _run_for(source_val: str, market_val: str, rule_val: str) -> None:
        df = generate_signals(source=source_val, market=market_val, rule=rule_val, leader_share_min=leader_share_min, entry_type=entry_type)
        path = write_signals_csv(df, source=source_val, market=market_val, rule=rule_val)
        rule_label = RULE_LABELS.get(rule_val, rule_val)
        logger.info("Concluído {} ({} - {} ). Sinais: {}", source_val, market_val, rule_label, len(df))
        print(str(path))

    sources = [source] if source != "both" else ["top3", "forecast"]
    markets = [market] if market != "both" else ["win", "place"]
    rules = [rule] if rule != "both" else ["lider_volume_total", "terceiro_queda50"]

    for s in sources:
        for m in markets:
            for r in rules:
                _run_for(s, m, r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


