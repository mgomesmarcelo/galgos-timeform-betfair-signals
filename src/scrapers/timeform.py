from __future__ import annotations

import random
import time
from typing import Dict, List, Iterable
import re
from urllib.parse import urljoin

from loguru import logger
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from ..config import settings
from ..utils.selenium_driver import build_chrome_driver
from ..utils.text import clean_horse_name, normalize_track_name
from ..utils.dates import iso_to_hhmm


_TIMEFORM_HOME = settings.TIMEFORM_BASE_URL
_TIMEFORM_BASE = "https://www.timeform.com/greyhound-racing"


def _sleep_jitter(label: str = "") -> None:
	low = max(0.0, settings.TIMEFORM_MIN_DELAY_SEC)
	high = max(low, settings.TIMEFORM_MAX_DELAY_SEC)
	delay = random.uniform(low, high)
	logger.debug("Delay{}: {:.2f}s", f" {label}" if label else "", delay)
	time.sleep(delay)


def _accept_cookies(driver) -> None:
	try:
		wait = WebDriverWait(driver, settings.SELENIUM_EXPLICIT_WAIT_SEC)
		# Aguarda o banner estar presente (se aparecer)
		banner = None
		try:
			banner = wait.until(EC.presence_of_element_located((By.ID, "onetrust-banner-sdk")))
		except Exception:
			banner = None

		# Se o banner estiver presente/visível, tenta clicar no botão Allow All Cookies
		if banner and banner.is_displayed():
			# Tenta via ID direto
			try:
				btn = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
				btn.click()
			except Exception:
				# Fallback: JS click
				try:
					driver.execute_script("document.getElementById('onetrust-accept-btn-handler')?.click();")
				except Exception:
					# Último recurso: busca por texto
					try:
						btn2 = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@id='onetrust-accept-btn-handler' or contains(., 'Allow All Cookies')]")))
						driver.execute_script("arguments[0].click();", btn2)
					except Exception:
						logger.debug("Falha ao clicar no botão de cookies do Timeform.")

			# Aguarda desaparecer
			try:
				WebDriverWait(driver, 5).until(EC.invisibility_of_element_located((By.ID, "onetrust-banner-sdk")))
			except Exception:
				logger.debug("Banner de cookies ainda visível após clique.")
			_sleep_jitter("cookies")
		else:
			logger.debug("Banner de cookies (Timeform) não presente.")
	except Exception:
		logger.debug("Botão/banner de cookies (Timeform) não encontrado ou já aceito.")


def _list_cards(driver) -> List[Dict[str, str]]:
	# Prioriza a estrutura atual do site (wfr-bytrack-content) e mantém fallback para seletor antigo
	cards: List[Dict[str, str]] = []

	# Tentativa 1: estrutura nova por pista
	try:
		container_list = driver.find_elements(By.CSS_SELECTOR, ".wfr-bytrack-content")
		for container in container_list:
			meetings = container.find_elements(By.CSS_SELECTOR, ".wfr-meeting")
			for sec in meetings:
				try:
					track_name = sec.find_element(By.CSS_SELECTOR, "b.wfr-track").text.strip()
					links = sec.find_elements(By.CSS_SELECTOR, "ul li a.wfr-race")
					for a in links:
						hhmm = a.text.strip()
						link = a.get_attribute("href") or a.get_attribute("ng-href")
						if link and not link.startswith("http"):
							link = urljoin(_TIMEFORM_BASE, link)
						cards.append({
							"track_name": track_name,
							"track_key": normalize_track_name(track_name),
							"hhmm": hhmm,
							"url": link,
						})
				except Exception:
					continue
	except Exception:
		pass

	# Fallback: seletor antigo
	if not cards:
		sections = driver.find_elements(By.CSS_SELECTOR, ".w-cards-results section")
		for sec in sections:
			try:
				track_name = sec.find_element(By.TAG_NAME, "h3").text.strip()
				links = sec.find_elements(By.CSS_SELECTOR, "li a")
				for a in links:
					hhmm = a.text.strip()
					link = a.get_attribute("href") or a.get_attribute("ng-href")
					if link and not link.startswith("http"):
						link = urljoin(_TIMEFORM_BASE, link)
					cards.append({
						"track_name": track_name,
						"track_key": normalize_track_name(track_name),
						"hhmm": hhmm,
						"url": link,
					})
			except Exception:
				continue

	return cards


def _extract_forecast(driver) -> str:
	# Busca o parágrafo que contém o rótulo Betting Forecast
	try:
		p = driver.find_element(By.XPATH, "//p[b[contains(., 'Betting Forecast')]]")
		text = p.text.strip()
		# Normaliza prefixo para TimeformForecast e mantém frações + nomes
		# Exemplo de text: "Betting Forecast : 5/2 Arundel, 4/1 Made All, ..."
		if text.lower().startswith("betting forecast"):
			text = text.split(":", 1)[-1].strip()
			return f"TimeformForecast : {_convert_forecast_to_decimal(text)}"
		return ""
	except Exception:
		return ""


def _extract_top3(driver) -> List[str]:
	"""Extrai os 3 primeiros nomes do bloco de veredito do Timeform."""
	try:
		container = driver.find_element(By.CSS_SELECTOR, ".rpf-verdict-container")
		selections = container.find_elements(By.CSS_SELECTOR, ".rpf-verdict-selection")
		top_names: List[str] = []
		for sel in selections[:3]:
			try:
				name_el = sel.find_element(By.CSS_SELECTOR, ".rpf-verdict-selection-name a")
				name = name_el.text.strip()
				if name:
					top_names.append(clean_horse_name(name))
			except Exception:
				continue
		return top_names
	except Exception:
		return []


def _convert_forecast_to_decimal(raw: str) -> str:
	"""Converte o trecho do Betting Forecast de odds fracionárias para decimais.

	Entrada exemplo: "3/1 Starproof, 9/2 Royal Accord, 11/2 Sarafina Mshairi"
	Saída: "4.00 Starproof, 5.50 Royal Accord, 6.50 Sarafina Mshairi"
	Regras: decimal = numerador/denominador + 1, arredondado a 2 casas decimais.
	Suporta também 'Evs'/'Evens' como 1/1 (2.00).
	"""
	items = [part.strip() for part in raw.split(",") if part.strip()]
	converted: List[str] = []
	frac_re = re.compile(r"^(\d+)\s*/\s*(\d+)(?:\b|\s)(.*)$")
	evens_re = re.compile(r"^(?:evs|evens)\b\s*(.*)$", re.IGNORECASE)
	for item in items:
		m = frac_re.match(item)
		if m:
			num = int(m.group(1))
			den = int(m.group(2)) if int(m.group(2)) != 0 else 1
			name = m.group(3).strip()
			value = (num / den) + 1.0
			converted.append(f"{value:.2f} {name}" if name else f"{value:.2f}")
			continue
		e = evens_re.match(item)
		if e:
			name = e.group(1).strip()
			converted.append(f"2.00 {name}" if name else "2.00")
			continue
		# Caso não bata regex, mantém item original
		converted.append(item)
	return ", ".join(converted)


def scrape_timeform_for_races(race_rows: Iterable[Dict[str, str]]) -> Iterable[Dict[str, object]]:
	"""
	Para cada corrida em race_rows (com chaves track_name, race_time_iso),
	busca na home do Timeform a corrida correspondente por pista e horário (HH:MM).
	Ao achar, abre o link e extrai TimeformForecast e o Top3.
	Gera (yield) um dict por corrida encontrada com track_name, race_time_iso, TimeformForecast e TimeformTop1/2/3 (se existirem).
	"""
	logger.info("Iniciando raspagem Timeform para corridas filtradas pelo Betfair race_links.csv")
	driver = build_chrome_driver()
	try:
		driver.get(_TIMEFORM_HOME)
		_accept_cookies(driver)
		_sleep_jitter("home")

		cards = _list_cards(driver)
		logger.debug("Total de cards Timeform capturados: {}", len(cards))

		# Index simples para match rápido: (track_normalizado, HH:MM) -> url
		index: Dict[tuple, str] = {}
		for c in cards:
			track_key = c.get("track_key") or normalize_track_name(c.get("track_name", ""))
			hhmm = c.get("hhmm", "")
			url = c.get("url", "")
			if track_key and hhmm and url:
				index[(track_key, hhmm)] = url

		for row in race_rows:
			track = row.get("track_name", "")
			race_time_iso = row.get("race_time_iso", "")
			match_key = (normalize_track_name(track), iso_to_hhmm(race_time_iso))
			url = index.get(match_key)
			if not url:
				continue

			# Abre página da corrida e extrai forecast com delay entre navegações
			driver.get(url)
			_sleep_jitter("race")
			forecast = _extract_forecast(driver)
			if forecast:
				row = {
					"track_name": track,
					"race_time_iso": race_time_iso,
					"TimeformForecast": forecast,
				}
				# Coleta Top3 no mesmo carregamento da página
				top3 = _extract_top3(driver)
				if len(top3) > 0:
					row["TimeformTop1"] = top3[0]
				if len(top3) > 1:
					row["TimeformTop2"] = top3[1]
				if len(top3) > 2:
					row["TimeformTop3"] = top3[2]
				logger.info("TimeformForecast coletado: {} {}", track, race_time_iso)
				yield row
			_sleep_jitter("post-race")

		return
	finally:
		driver.quit()
