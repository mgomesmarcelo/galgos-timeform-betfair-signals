### Raspagem diária de corridas de galgos (Betfair, Timeform)

Coleta diária de dados das corridas de galgos e geração de sinais (BACK/LAY) a partir do cruzamento Timeform x Betfair. Saídas ficam em `data/` e podem ser exploradas via dashboard (Streamlit).

- **Stack**: Selenium, pandas, Streamlit, loguru
- **Horário**: ISO 8601 (`YYYY-MM-DDTHH:MM`)
- **Estrutura de pastas** (principais):
  - `data/YYYY-MM-DD/` (pasta do dia)
    - `race_links.csv` (links e metadados das corridas)
    - `Pista_ABC/` (uma pasta por pista; CSVs por corrida)
  - `data/Result/` (CSVs consolidados Betfair `dwbfgreyhoundwin*` e `dwbfgreyhoundplace*`)
  - `data/timeform_top3/` e `data/TimeformForecast/` (consolidados Timeform do dia)
  - `data/signals/` (arquivos `signals_{source}_{market}_{rule}.csv`)

### Pré-requisitos
- Python 3.10+
- Google Chrome instalado (usado pelo `webdriver-manager`/Selenium)

### Instalação
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows PowerShell
pip install -r requirements.txt
```

### Execução da raspagem
- Índice Betfair (pistas/corridas do dia):
```bash
python scripts/scrape_betfair_index.py
```
- Enriquecimento Timeform (mesmos horários/pistas):
```bash
python scripts/scrape_timeform_update.py
```
- Pipeline diário (orquestra os passos acima):
```bash
python scripts/run_daily.py
```
- Opcional: limpar CSVs em `data/Result/` (formata colunas, remove AUS/NZL):
```bash
python scripts/clean_results.py          # use --force para reformatar todos
```

### Backfill/Consolidação Timeform por dia
Gera arquivos de um dia a partir dos CSVs por corrida já existentes em `data/YYYY-MM-DD/...`:
```bash
python scripts/backfill_timeform_daily.py 2025-09-20 2025-09-21
```
Saídas:
- `data/TimeformForecast/TimeformForecast_YYYY-MM-DD.csv`
- `data/timeform_top3/timeform_top3_YYYY-MM-DD.csv`

### Geração de sinais (BACK e LAY)
Os sinais são gerados combinando Betfair (volumes/BSP) e Timeform (Top3/Forecast), com duas regras disponíveis:
- **terceiro_queda50**: 2º por volume está >50% acima do 3º; alvo = 3º
- **líder volume total**: participação do líder ≥ limite; alvo = 1º por volume (limite padrão 50%)

Comando geral:
```bash
python scripts/generate_signals.py \
  --source {top3|forecast|both} \
  --market {win|place|both} \
  --rule {terceiro_queda50|lider_volume_total|both} \
  --entry_type {back|lay|both} \
  --leader_share_min 0.5
```

Exemplos:
```bash
# Tudo (todas combinações) — gera múltiplos CSVs em data/signals/
python scripts/generate_signals.py --source both --market both --rule both --entry_type both

# Apenas WIN com Timeform Top3, regra terceiro_queda50, entradas LAY
python scripts/generate_signals.py --source top3 --market win --rule terceiro_queda50 --entry_type lay

# Apenas PLACE com Forecast, regra líder ≥ 60%, entradas BACK
python scripts/generate_signals.py --source forecast --market place --rule lider_volume_total --entry_type back --leader_share_min 0.6
```

Arquivos gerados (exemplos):
- `data/signals/signals_top3_win_terceiro_queda50.csv`
- `data/signals/signals_top3_place_lider_volume_total.csv`
- `data/signals/signals_forecast_win_terceiro_queda50.csv`

Colunas principais presentes em cada CSV de sinais:
- date, track_name, race_time_iso
- tf_top1, tf_top2, tf_top3; vol_top1, vol_top2, vol_top3
- second_name_by_volume, third_name_by_volume, ratio_second_over_third, pct_diff_second_vs_third
- leader_name_by_volume, leader_volume_share_pct
- entry_type ∈ {back, lay}
- back_target_name/back_target_bsp ou lay_target_name/lay_target_bsp
- stake_fixed_10, liability_from_stake_fixed_10, stake_for_liability_10, liability_fixed_10
- win_lose, is_green, pnl_stake_fixed_10, pnl_liability_fixed_10, roi_row_*
- **num_runners** (número final de corredores por corrida)

Notas de cálculo:
- BACK: pnl por stake fixa de 10 (com taxa 6.5%);
- LAY: pnl por stake fixa de 10 e por liability fixa de 10 (com taxa 6.5%).
- Para mercado PLACE, o BSP considerado é do PLACE; seleção por volume usa sempre WIN.

### Dashboard (Streamlit)
Execute de uma das formas:
```bash
# Forma direta
streamlit run scripts/streamlit_app.py

# Launcher com args (porta/endereço)
python scripts/run_streamlit.py --port 8501 --address 0.0.0.0
```
O app lê os CSVs em `data/signals/` (`signals_{source}_{market}_{rule}.csv`), traz filtros por data/pista/categoria, seleção de regra/mercado/fonte e mostra métricas, PnL (stake/liability), além de tabelas e gráficos.

#### Novo: filtro “Número de corredores”
- Multiselect dinâmico com todos os valores observados (3, 4, 5, 6, ...), selecionados por padrão.
- KPIs, tabelas e gráficos passam a respeitar essa seleção.
- Se os CSVs de sinais não tiverem a coluna `num_runners`, a UI calcula on‑the‑fly a partir dos arquivos `dwbfgreyhoundwin*.csv` (fallback automático).

#### Novos gráficos
- Evolução (PnL acumulado) por número de corredores — BACK e LAY.
- Evolução por categoria × número de corredores e por pista × número de corredores (linhas; opção de eixo Dia/Bet; títulos mostram a contagem de bets).
- Evolução por subcategoria (A1/A2/D1/OR3/...) e por subcategoria × pista (linhas; opção de eixo Dia/Bet; títulos com contagem de bets).
- Heatmaps por categoria × número de corredores e por pista × número de corredores (métrica selecionável: ROI, PnL ou Assertividade).

#### Filtros de categoria e subcategoria
- `Categoria` (letra): A, B, D, H, I, O, S, ...
- `Subcategorias` (token completo): A1, A2, D1, OR3, etc. O multiselect de subcategorias é dinâmico (tudo selecionado por padrão) e integra com os demais filtros (Datas, Pistas, Número de corredores, BSP, Tipo de entrada).

### Configuração
Edite `src/config.py` para ajustar:
- `DATA_DIR`, URLs base, tempos de espera Selenium, codificação CSV (`utf-8-sig`), nível de log
- `SELENIUM_HEADLESS` (True/False) conforme seu ambiente
- Rótulos de regras/entradas usados pela UI (Streamlit)

### Fluxo típico
```bash
# 1) Raspagem diária
python scripts/run_daily.py

# 2) (Opcional) limpeza dos resultados
python scripts/clean_results.py --force

# 3) Geração dos sinais desejados
python scripts/generate_signals.py --source both --market both --rule both --entry_type both

# 4) Dashboard
python scripts/run_streamlit.py
```

### Publicação/Privacidade
- Recomenda-se **não versionar** dados rasos/largos em `data/` (incluindo `Result/`, `TimeformForecast/`, `timeform_top3/` e `signals/`). Use `.gitignore` para ignorar essas pastas e manter o repositório leve.
- Não há chaves de API/senhas no código por padrão. Ainda assim, se futuramente adicionar credenciais, armazene em variáveis de ambiente ou `.env` (e mantenha `.env` no `.gitignore`).
- Verifique e respeite os termos de uso dos sites alvo (Betfair/Timeform). Este projeto é para estudo/análise; não há garantias de disponibilidade/estabilidade.

### .gitignore sugerido
Crie um arquivo `.gitignore` na raiz com, por exemplo:
```
# Ambientes/artefatos
.venv/
__pycache__/
*.pyc
*.log

# Dados gerados/baixados
data/
New folder/

# Arquivos locais
.env
.DS_Store
Thumbs.db
```
