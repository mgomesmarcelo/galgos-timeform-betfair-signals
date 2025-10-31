from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd
from dateutil import parser as date_parser
from loguru import logger

from ..config import settings
from ..config import RULE_LABELS
from ..utils.text import clean_horse_name, normalize_track_name


_TRAP_PREFIX_RE = re.compile(r"^\s*\d+\.\s*")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _strip_trap_prefix(name: str) -> str:
    return _TRAP_PREFIX_RE.sub("", name or "").strip()


def _extract_track_from_menu_hint(menu_hint: str) -> str:
    # Pega trecho inicial até o primeiro dígito (ex.: "Romford 19th Sep" -> "Romford")
    text = menu_hint or ""
    m = re.match(r"^([A-Za-z\s]+?)(?:\s*\d|$)", text)
    base = m.group(1) if m else text
    return normalize_track_name(base)


def _to_iso_yyyy_mm_dd_thh_mm(value: str) -> str:
    # event_dt exemplo: "19-09-2025 20:01"
    try:
        dt = date_parser.parse(value, dayfirst=True)
        return dt.strftime("%Y-%m-%dT%H:%M")
    except Exception:
        return ""


def _parse_forecast_top3(text: str) -> List[str]:
    """Extrai apenas os 3 primeiros nomes previstos da string TimeformForecast.

    Suporta formatos como:
    - "TimeformForecast : 2.50 Nome A, 3.50 Nome B, 4.50 Nome C, ..."
    - "Nome A (2/1), Nome B (5/2), Nome C (4/1), ..."
    - "2.50 Nome A, 3.50 Nome B, 4.50 Nome C"
    """
    if not isinstance(text, str):
        return []
    s = re.sub(r"(?i)\btimeformforecast\s*:\s*", "", text.strip())
    parts = [p.strip() for p in s.split(",") if p and isinstance(p, str)]
    names: List[str] = []
    for p in parts:
        # remove odds no início (ex.: 2.50 Nome A)
        m1 = re.match(r"^\s*\d+(?:\.\d+)?\s+(.+)$", p)
        if m1:
            candidate = m1.group(1).strip()
        else:
            # remove odds entre parênteses no final (ex.: Nome A (2/1))
            candidate = re.sub(r"\s*\([^\)]*\)\s*$", "", p).strip()
        candidate = _strip_trap_prefix(candidate)
        cleaned = clean_horse_name(candidate)
        if cleaned and cleaned not in names:
            names.append(cleaned)
        if len(names) >= 3:
            break
    return names


@dataclass
class RunnerBF:
    selection_name_raw: str
    selection_name_clean: str
    pptradedvol: float
    bsp: float
    win_lose: int


def load_betfair_win() -> Dict[Tuple[str, str], Dict[str, RunnerBF]]:
    """Carrega todos os CSVs dwbfgreyhoundwin*.csv e indexa por (track_key, race_iso)."""
    result_dir = settings.DATA_DIR / "Result"
    all_files = sorted(result_dir.glob("dwbfgreyhoundwin*.csv"))
    index: Dict[Tuple[str, str], Dict[str, RunnerBF]] = {}

    for csv_path in all_files:
        try:
            df = pd.read_csv(csv_path, encoding=settings.CSV_ENCODING)
        except Exception as e:
            logger.error("Falha ao ler {}: {}", csv_path.name, e)
            continue

        # Garante colunas
        for col in ["menu_hint", "event_dt", "selection_name", "pptradedvol", "bsp", "win_lose"]:
            if col not in df.columns:
                df[col] = ""

        # Limpeza e normalização
        df["track_key"] = df["menu_hint"].astype(str).map(_extract_track_from_menu_hint)
        df["race_iso"] = df["event_dt"].astype(str).map(_to_iso_yyyy_mm_dd_thh_mm)
        df["selection_name_raw"] = df["selection_name"].astype(str)
        df["selection_name_clean"] = df["selection_name_raw"].map(_strip_trap_prefix).map(clean_horse_name)
        df["pptradedvol"] = pd.to_numeric(df["pptradedvol"], errors="coerce").fillna(0.0)
        df["bsp"] = pd.to_numeric(df["bsp"], errors="coerce")
        df["win_lose"] = pd.to_numeric(df["win_lose"], errors="coerce").fillna(0).astype(int)

        for (track_key, race_iso), grp in df.groupby(["track_key", "race_iso" ], dropna=False):
            if not track_key or not race_iso:
                continue
            runners: Dict[str, RunnerBF] = index.setdefault((track_key, race_iso), {})
            for _, r in grp.iterrows():
                name_clean = r["selection_name_clean"]
                if not isinstance(name_clean, str) or not name_clean:
                    continue
                runners[name_clean] = RunnerBF(
                    selection_name_raw=r["selection_name_raw"],
                    selection_name_clean=name_clean,
                    pptradedvol=float(r["pptradedvol"]),
                    bsp=float(r["bsp"]) if pd.notna(r["bsp"]) else float("nan"),
                    win_lose=int(r["win_lose"]),
                )

    logger.info("Betfair WIN index criado: {} corridas", len(index))
    return index


def load_betfair_place() -> Dict[Tuple[str, str], Dict[str, RunnerBF]]:
    """Carrega todos os CSVs dwbfgreyhoundplace*.csv e indexa por (track_key, race_iso)."""
    result_dir = settings.DATA_DIR / "Result"
    all_files = sorted(result_dir.glob("dwbfgreyhoundplace*.csv"))
    index: Dict[Tuple[str, str], Dict[str, RunnerBF]] = {}

    for csv_path in all_files:
        try:
            df = pd.read_csv(csv_path, encoding=settings.CSV_ENCODING)
        except Exception as e:
            logger.error("Falha ao ler {}: {}", csv_path.name, e)
            continue

        # Garante colunas
        for col in ["menu_hint", "event_dt", "selection_name", "pptradedvol", "bsp", "win_lose"]:
            if col not in df.columns:
                df[col] = ""

        # Limpeza e normalização
        df["track_key"] = df["menu_hint"].astype(str).map(_extract_track_from_menu_hint)
        df["race_iso"] = df["event_dt"].astype(str).map(_to_iso_yyyy_mm_dd_thh_mm)
        df["selection_name_raw"] = df["selection_name"].astype(str)
        df["selection_name_clean"] = df["selection_name_raw"].map(_strip_trap_prefix).map(clean_horse_name)
        df["pptradedvol"] = pd.to_numeric(df["pptradedvol"], errors="coerce").fillna(0.0)
        df["bsp"] = pd.to_numeric(df["bsp"], errors="coerce")
        df["win_lose"] = pd.to_numeric(df["win_lose"], errors="coerce").fillna(0).astype(int)

        for (track_key, race_iso), grp in df.groupby(["track_key", "race_iso" ], dropna=False):
            if not track_key or not race_iso:
                continue
            runners: Dict[str, RunnerBF] = index.setdefault((track_key, race_iso), {})
            for _, r in grp.iterrows():
                name_clean = r["selection_name_clean"]
                if not isinstance(name_clean, str) or not name_clean:
                    continue
                runners[name_clean] = RunnerBF(
                    selection_name_raw=r["selection_name_raw"],
                    selection_name_clean=name_clean,
                    pptradedvol=float(r["pptradedvol"]),
                    bsp=float(r["bsp"]) if pd.notna(r["bsp"]) else float("nan"),
                    win_lose=int(r["win_lose"]),
                )

    logger.info("Betfair PLACE index criado: {} corridas", len(index))
    return index

def load_timeform_top3() -> List[dict]:
    """Carrega todos os CSVs timeform_top3_*.csv e retorna linhas normalizadas."""
    tf_dir = settings.DATA_DIR / "timeform_top3"
    rows: List[dict] = []
    for csv_path in sorted(tf_dir.glob("timeform_top3_*.csv")):
        try:
            # Usa engine=python e on_bad_lines='skip' para tolerar linhas malformadas
            df = pd.read_csv(csv_path, encoding=settings.CSV_ENCODING, engine="python", on_bad_lines="skip")
        except Exception as e:
            logger.error("Falha ao ler {}: {}", csv_path.name, e)
            continue

        # Esperado: track_name, race_time_iso, TimeformTop1/2/3
        for col in ["track_name", "race_time_iso", "TimeformTop1", "TimeformTop2", "TimeformTop3"]:
            if col not in df.columns:
                df[col] = pd.NA

        for _, r in df.iterrows():
            track = normalize_track_name(str(r.get("track_name", "")))
            race_iso = str(r.get("race_time_iso", ""))
            names = [clean_horse_name(str(r.get(c, ""))) for c in ["TimeformTop1", "TimeformTop2", "TimeformTop3"]]
            if not track or not race_iso or not any(names):
                continue
            rows.append({
                "track_key": track,
                "race_iso": race_iso,
                "top_names": names,
                "raw": r.to_dict(),
            })
    logger.info("Timeform Top3 carregado: {} corridas", len(rows))
    return rows


def load_timeform_forecast_top3() -> List[dict]:
    """Carrega TimeformForecast_*.csv e retorna linhas com apenas os 3 primeiros previstos.

    Mantém o mesmo formato de saída de load_timeform_top3, preenchendo
    os campos TimeformTop1/2/3 com os nomes extraídos.
    """
    tf_dir = settings.DATA_DIR / "TimeformForecast"
    rows: List[dict] = []
    for csv_path in sorted(tf_dir.glob("TimeformForecast_*.csv")):
        try:
            df = pd.read_csv(csv_path, encoding=settings.CSV_ENCODING, engine="python", on_bad_lines="skip")
        except Exception as e:
            logger.error("Falha ao ler {}: {}", csv_path.name, e)
            continue

        for col in ["track_name", "race_time_iso", "TimeformForecast"]:
            if col not in df.columns:
                df[col] = pd.NA

        for _, r in df.iterrows():
            track = normalize_track_name(str(r.get("track_name", "")))
            race_iso = str(r.get("race_time_iso", ""))
            names = _parse_forecast_top3(str(r.get("TimeformForecast", "")))
            if not track or not race_iso or not names:
                continue
            # garante 3 posições
            while len(names) < 3:
                names.append("")
            raw_like = {
                "track_name": track,
                "race_time_iso": race_iso,
                "TimeformTop1": names[0],
                "TimeformTop2": names[1],
                "TimeformTop3": names[2],
            }
            rows.append({
                "track_key": track,
                "race_iso": race_iso,
                "top_names": names[:3],
                "raw": raw_like,
            })

    logger.info("Timeform Forecast(Top3) carregado: {} corridas", len(rows))
    return rows


def _calc_signals_for_race(
    tf_row: dict,
    bf_win_index: Dict[Tuple[str, str], Dict[str, RunnerBF]],
    bf_place_index: Dict[Tuple[str, str], Dict[str, RunnerBF]] | None = None,
    market: str = "win",
    rule: str = "terceiro_queda50",
    leader_share_min: float = 0.5,
) -> List[dict]:
    track_key = tf_row["track_key"]
    race_iso = tf_row["race_iso"]
    top_names = [n for n in tf_row["top_names"] if isinstance(n, str) and n]
    # Seleção por volume sempre no mercado WIN
    group = bf_win_index.get((track_key, race_iso))
    if not group:
        return []
    # Número final de corredores (linhas por corrida no WIN index)
    num_runners = len(group)

    # Coleta volumes e BSP para os três de referência
    triples: List[Tuple[str, float, float]] = []  # (name_clean, vol, bsp)
    for name in top_names:
        r = group.get(name)
        if not r or pd.isna(r.bsp):
            return []
        triples.append((name, max(0.0, float(r.pptradedvol)), float(r.bsp)))

    if len(triples) < 3:
        return []

    # Ordena por volume desc entre os Top3 de referência
    triples_sorted = sorted(triples, key=lambda t: t[1], reverse=True)
    first, second, third = triples_sorted[0], triples_sorted[1], triples_sorted[2]

    # Métricas auxiliares entre 2º e 3º
    vol2, vol3 = second[1], third[1]
    pct_diff = (vol2 - vol3) / vol2 if vol2 > 0 else float("inf")
    ratio = (vol2 / vol3) if vol3 > 0 else float("inf")
    
    # Seleção conforme regra
    target_name_clean: str | None = None
    target_bsp_win: float | None = None
    leader_share = 0.0
    if rule == "terceiro_queda50":
        if vol3 <= 0 or pct_diff <= 0.5:
            return []
        target_name_clean = third[0]
        target_bsp_win = third[2]
    else:
        total_vol_race = 0.0
        for _name, r in bf_win_index.get((track_key, race_iso), {}).items():
            total_vol_race += max(0.0, float(r.pptradedvol))
        leader_share = (first[1] / total_vol_race) if total_vol_race > 0 else 0.0
        if leader_share < float(leader_share_min):
            return []
        target_name_clean = first[0]
        target_bsp_win = first[2]

    if not target_name_clean:
        return []

    # Recupera runner conforme mercado (win/place) para obter BSP/label corretos
    if market == "place" and bf_place_index is not None:
        target_runner = bf_place_index.get((track_key, race_iso), {}).get(target_name_clean)
    else:
        target_runner = bf_win_index.get((track_key, race_iso), {}).get(target_name_clean)
    if not target_runner:
        return []
    target_win_lose = int(target_runner.win_lose)

    # Para place, usar BSP do mercado PLACE; para win, BSP do WIN
    odd = float(target_runner.bsp) if market == "place" and target_runner is not None else float(target_bsp_win)

    # Stake base
    stake_fix10 = 10.00

    # Comissão aplicada a todos os ganhos (BACK e LAY)
    commission_rate = 0.065

    # Calcula ambos os tipos de entrada sobre o mesmo alvo
    back_is_green = (target_win_lose == 1)
    if back_is_green:
        back_profit_gross = stake_fix10 * max(0.0, odd - 1.0)
        back_pnl_stake10 = back_profit_gross * (1.0 - commission_rate)
    else:
        back_pnl_stake10 = -stake_fix10

    liability_from_stake10 = stake_fix10 * max(0.0, odd - 1.0)
    liability_fix10 = 10.00
    stake_from_liab10 = (liability_fix10 / max(0.001, odd - 1.0))
    if target_win_lose == 1:
        lay_pnl_stake10 = -liability_from_stake10
        lay_pnl_liab10 = -liability_fix10
        lay_is_green = False
    else:
        lay_pnl_stake10 = stake_fix10 * (1.0 - commission_rate)
        lay_pnl_liab10 = stake_from_liab10 * (1.0 - commission_rate)
        lay_is_green = True

    raw = tf_row["raw"]
    # Helpers seguros para obter volumes dos Top1/2/3
    def _vol_for(name_raw: object) -> float:
        name = clean_horse_name(str(name_raw)) if isinstance(name_raw, (str,)) else ""
        return next((v for n, v, _ in triples if n == name), 0.0)

    base = {
        "date": race_iso.split("T")[0],
        "track_name": raw.get("track_name", ""),
        "race_time_iso": race_iso,
        "tf_top1": raw.get("TimeformTop1", ""),
        "tf_top2": raw.get("TimeformTop2", ""),
        "tf_top3": raw.get("TimeformTop3", ""),
        "vol_top1": _vol_for(raw.get("TimeformTop1")),
        "vol_top2": _vol_for(raw.get("TimeformTop2")),
        "vol_top3": _vol_for(raw.get("TimeformTop3")),
        "second_name_by_volume": second[0],
        "third_name_by_volume": third[0],
        "ratio_second_over_third": round(ratio, 2),
        # Percentual agora relativo ao volume do 2º colocado por volume
        "pct_diff_second_vs_third": round(pct_diff * 100.0, 2),
        # Participação do líder (sempre calculada com base no WIN)
        "leader_name_by_volume": first[0],
        "leader_volume_share_pct": round(leader_share * 100.0, 2),
        "num_runners": int(num_runners),
        "market": market,
        "rule": rule,
        "rule_label": RULE_LABELS.get(rule, rule),
    }

    out_back = {
        **base,
        "entry_type": "back",
        "back_target_name": target_name_clean,
        "back_target_bsp": round(odd, 2),
        "lay_target_name": "",
        "lay_target_bsp": float("nan"),
        "stake_fixed_10": round(stake_fix10, 2),
        "liability_from_stake_fixed_10": 0.0,
        "stake_for_liability_10": 0.0,
        "liability_fixed_10": 0.0,
        "win_lose": target_win_lose,
        "is_green": back_is_green,
        "pnl_stake_fixed_10": round(back_pnl_stake10, 2),
        "pnl_liability_fixed_10": 0.0,
        "roi_row_stake_fixed_10": round((back_pnl_stake10 / stake_fix10) if stake_fix10 > 0 else 0.0, 4),
        "roi_row_liability_fixed_10": 0.0,
    }

    out_lay = {
        **base,
        "entry_type": "lay",
        "back_target_name": "",
        "back_target_bsp": float("nan"),
        "lay_target_name": target_name_clean,
        "lay_target_bsp": round(odd, 2),
        "stake_fixed_10": round(stake_fix10, 2),
        "liability_from_stake_fixed_10": round(liability_from_stake10, 2),
        "stake_for_liability_10": round(stake_from_liab10, 2),
        "liability_fixed_10": round(liability_fix10, 2),
        "win_lose": target_win_lose,
        "is_green": lay_is_green,
        "pnl_stake_fixed_10": round(lay_pnl_stake10, 2),
        "pnl_liability_fixed_10": round(lay_pnl_liab10, 2),
        "roi_row_stake_fixed_10": round((lay_pnl_stake10 / liability_from_stake10) if liability_from_stake10 > 0 else 0.0, 4),
        "roi_row_liability_fixed_10": round((lay_pnl_liab10 / liability_fix10) if liability_fix10 > 0 else 0.0, 4),
    }

    return [out_back, out_lay]


def generate_signals(source: str = "top3", market: str = "win", rule: str = "terceiro_queda50", leader_share_min: float = 0.5, entry_type: str = "both") -> pd.DataFrame:
    bf_win_index = load_betfair_win()
    bf_place_index = load_betfair_place() if market == "place" else None
    if source == "forecast":
        tf_rows = load_timeform_forecast_top3()
    else:
        tf_rows = load_timeform_top3()

    signals_rows: List[dict] = []
    for row in tf_rows:
        results = _calc_signals_for_race(row, bf_win_index, bf_place_index, market=market, rule=rule, leader_share_min=leader_share_min)
        for r in results:
            if entry_type in ("both", r.get("entry_type")):
                signals_rows.append(r)

    df = pd.DataFrame(signals_rows)
    logger.info("Sinais encontrados (source={}, market={}, rule={}, leader_share_min={}, entry_type={}): {}", source, market, rule, leader_share_min, entry_type, len(df))
    return df


def write_signals_csv(df: pd.DataFrame, source: str = "top3", market: str = "win", rule: str = "terceiro_queda50") -> Path:
    out_dir = settings.DATA_DIR / "signals"
    _ensure_dir(out_dir)
    out_path = out_dir / f"signals_{source}_{market}_{rule}.csv"
    df = df.copy()
    df["source"] = source
    df["market"] = market
    df["rule"] = rule
    df["rule_label"] = RULE_LABELS.get(rule, rule)
    if df.empty:
        # cria CSV vazio com cabeçalhos padrão
        df_sorted = pd.DataFrame([], columns=[
            "date","track_name","race_time_iso",
            "tf_top1","tf_top2","tf_top3",
            "vol_top1","vol_top2","vol_top3",
            "second_name_by_volume","third_name_by_volume",
            "ratio_second_over_third","pct_diff_second_vs_third",
            "num_runners",
            "lay_target_name","lay_target_bsp",
            "back_target_name","back_target_bsp",
            "leader_name_by_volume","leader_volume_share_pct",
            "stake_fixed_10","liability_from_stake_fixed_10",
            "stake_for_liability_10","liability_fixed_10",
            "win_lose","is_green","pnl_stake_fixed_10","pnl_liability_fixed_10",
            "roi_row_stake_fixed_10","roi_row_liability_fixed_10",
            "source","market","rule","rule_label","entry_type",
        ])
    else:
        df_sorted = df.sort_values(["date", "track_name", "race_time_iso", "entry_type"]).reset_index(drop=True)
    df_sorted.to_csv(out_path, index=False, encoding=settings.CSV_ENCODING)
    logger.info("Gerado: {} ({} linhas)", out_path, len(df_sorted))
    return out_path


