from __future__ import annotations

from typing import Dict, List
from urllib.parse import urljoin

from loguru import logger
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from ..config import settings
from ..utils.selenium_driver import build_chrome_driver
from ..utils.dates import hhmm_to_today_iso


# Retorna lista de dicts com: track_name, race_time_label, race_time_iso, race_url


def _try_click_cookie_button(driver) -> bool:
	wait = WebDriverWait(driver, 5)
	xpaths = [
		"//button[contains(., 'Allow all cookies')]",
		"//button[contains(., 'Allow All Cookies')]",
		"//button[contains(., 'Accept all')]",
		"//button[contains(., 'Accept All')]",
		"//button[@id='onetrust-accept-btn-handler']",
	]
	for xp in xpaths:
		try:
			btn = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
			btn.click()
			return True
		except Exception:
			continue
	return False


def _aceitar_cookies(driver) -> None:
	# Primeiro tenta no documento principal
	if _try_click_cookie_button(driver):
		logger.debug("Cookies aceitos no documento principal.")
		return
	# Se não deu, tenta dentro de iframes (ex.: Sourcepoint/OneTrust)
	frames = driver.find_elements(By.TAG_NAME, "iframe")
	for frame in frames:
		try:
			driver.switch_to.frame(frame)
			if _try_click_cookie_button(driver):
				logger.debug("Cookies aceitos dentro de iframe.")
				return
		except Exception:
			pass
		finally:
			driver.switch_to.default_content()
	logger.debug("Botão de cookies não encontrado ou já aceito.")


def _selecionar_aba_gb_ire(driver) -> None:
	try:
		wait = WebDriverWait(driver, settings.SELENIUM_EXPLICIT_WAIT_SEC)
		wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.country-tab, .country-tab")))
		abas = driver.find_elements(By.CSS_SELECTOR, "li.country-tab, .country-tab")
		for aba in abas:
			label = aba.text.strip().replace("\n", " ")
			if ("GB" in label and "IRE" in label) or ("GB & IRE" in label):
				if "active" not in (aba.get_attribute("class") or ""):
					aba.click()
					break
		# Aguarda conteúdo de meetings
		WebDriverWait(driver, settings.SELENIUM_EXPLICIT_WAIT_SEC + 10).until(
			EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".meeting-label"))
		)
		logger.debug("Aba GB & IRE selecionada e meetings carregados.")
	except Exception as e:
		logger.warning(f"Erro ao selecionar/aguardar aba GB & IRE: {e}")


def scrape_betfair_index() -> List[Dict[str, str]]:
	logger.info("Iniciando scrape do índice da Betfair: {}", settings.BETFAIR_GREYHOUND_RACING_URL)
	driver = build_chrome_driver()
	try:
		driver.get(settings.BETFAIR_GREYHOUND_RACING_URL)
		_aceitar_cookies(driver)
		_selecionar_aba_gb_ire(driver)

		rows: List[Dict[str, str]] = []
		try:
			wait = WebDriverWait(driver, settings.SELENIUM_EXPLICIT_WAIT_SEC + 10)
			wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".meeting-label")))
			meetings = driver.find_elements(By.CSS_SELECTOR, ".country-content li.meeting-item, li.meeting-item")
			if not meetings:
				meetings = driver.find_elements(By.CSS_SELECTOR, ".meeting-label")
				logger.debug("Fallback: usando labels de meeting.")
			for meeting in meetings:
				# Nome da pista
				track_name = ""
				try:
					track_name = meeting.find_element(By.CSS_SELECTOR, ".meeting-label").text.strip()
				except Exception:
					try:
						track_name = meeting.text.strip()
					except Exception:
						pass

				# Corridas e horários
				race_links = []
				try:
					race_links = meeting.find_elements(By.CSS_SELECTOR, "ul.race-list li.race-information a.race-link")
				except Exception:
					pass
				for a in race_links:
					try:
						time_label = a.find_element(By.CSS_SELECTOR, ".label").text.strip()
					except Exception:
						time_label = ""

					href = a.get_attribute("href") or a.get_attribute("ng-href") or a.get_attribute("data-href")
					if not href:
						href = a.get_attribute("attr.href") or ""

					# Normaliza URL completa
					if href and not href.startswith("http"):
						href = urljoin(settings.BETFAIR_BASE_URL, href.lstrip("/"))

					rows.append({
						"track_name": track_name,
						"race_time_label": time_label,
						"race_time_iso": hhmm_to_today_iso(time_label) if time_label else "",
						"race_url": href,
					})
		except TimeoutException:
			logger.error("Timeout aguardando meetings. A página pode estar bloqueando headless/precisando de consentimento diferente.")

		logger.info("Total de corridas encontradas: {}", len(rows))
		return rows
	finally:
		driver.quit()
