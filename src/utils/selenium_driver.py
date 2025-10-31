from __future__ import annotations

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from ..config import settings


def _build_options(use_headless_new: bool | None) -> Options:
	chrome_options = Options()
	if use_headless_new is True:
		chrome_options.add_argument("--headless=new")
	elif use_headless_new is False:
		chrome_options.add_argument("--headless")
	# quando None, roda com UI
	chrome_options.add_argument("--no-sandbox")
	chrome_options.add_argument("--disable-dev-shm-usage")
	chrome_options.add_argument("--window-size=1920,1080")
	chrome_options.add_argument("--disable-gpu")
	chrome_options.add_argument("--lang=en-GB")
	chrome_options.add_argument("--ignore-certificate-errors")
	chrome_options.add_argument("--allow-running-insecure-content")
	chrome_options.add_argument("--disable-blink-features=AutomationControlled")
	chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"]) 
	chrome_options.add_experimental_option("useAutomationExtension", False)
	chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
	# Acelera navegação (não espera todos os recursos)
	chrome_options.page_load_strategy = "eager"
	return chrome_options


def build_chrome_driver() -> webdriver.Chrome:
	# Tenta headless=new -> headless -> com UI
	attempts = []
	if settings.SELENIUM_HEADLESS:
		attempts = [True, False, None]
	else:
		attempts = [None]

	ex = None
	for headless_new in attempts:
		try:
			service = Service(ChromeDriverManager().install())
			driver = webdriver.Chrome(service=service, options=_build_options(headless_new))
			try:
				# Minimiza detecção de webdriver em runtime
				driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
					"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
				})
			except Exception:
				pass

			driver.set_page_load_timeout(settings.SELENIUM_PAGELOAD_TIMEOUT_SEC)
			# Estratégia sem implicit wait: usar somente WebDriverWait explícito
			driver.implicitly_wait(0)
			return driver
		except Exception as e:
			ex = e
			continue
	# Se chegou aqui, todas tentativas falharam
	raise ex if ex else RuntimeError("Falha ao inicializar ChromeDriver")


# Builder alternativo: undetected-chromedriver (para sites com Cloudflare/antibot)

def build_undetected_chrome_driver():
	import undetected_chromedriver as uc

	# Tenta headless=new -> headless -> com UI
	attempts = []
	if settings.SELENIUM_HEADLESS:
		attempts = [True, False, None]
	else:
		attempts = [None]

	ex = None
	for headless_new in attempts:
		try:
			# Descobre a versão do Chrome instalada e ajusta version_main
			try:
				chrome_ver = uc.utils.get_chrome_version()
			except Exception:
				chrome_ver = None
			version_main = None
			if chrome_ver:
				version_main = int(str(chrome_ver).split(".")[0])

			# Usa uc.ChromeOptions (sem experimental options incompatíveis)
			options = uc.ChromeOptions()
			headless_bool = False
			if headless_new is True:
				options.add_argument("--headless=new")
				headless_bool = True
			elif headless_new is False:
				options.add_argument("--headless")
				headless_bool = True
			# quando None, roda com UI
			options.add_argument("--no-sandbox")
			options.add_argument("--disable-dev-shm-usage")
			options.add_argument("--window-size=1920,1080")
			options.add_argument("--lang=en-GB")
			options.add_argument("--ignore-certificate-errors")
			options.add_argument("--allow-running-insecure-content")
			options.add_argument("--no-first-run")
			options.add_argument("--no-default-browser-check")
			options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")

			# Inicializa (força version_main quando possível)
			if version_main:
				driver = uc.Chrome(options=options, headless=headless_bool, version_main=version_main)
			else:
				driver = uc.Chrome(options=options, headless=headless_bool)

			driver.set_page_load_timeout(settings.SELENIUM_PAGELOAD_TIMEOUT_SEC)
			# Estratégia sem implicit wait: usar somente WebDriverWait explícito
			driver.implicitly_wait(0)
			return driver
		except Exception as e:
			ex = e
			continue
	raise ex if ex else RuntimeError("Falha ao inicializar undetected ChromeDriver")
