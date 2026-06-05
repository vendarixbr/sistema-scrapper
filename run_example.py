"""
Exemplos de uso do health-lead-extractor.

Execute com:
    python run_example.py

Cada função demonstra um caso de uso diferente.
"""

import asyncio
import sys
from pathlib import Path

# Garante que o diretório do projeto está no Python path
sys.path.insert(0, str(Path(__file__).parent))

# Corrige asyncio no Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from config import OUTPUT_DIR
from scraper.browser_manager import BrowserManager
from scraper.doctoralia_scraper import DoctoraliaScraper
from filters.professional_filter import ProfessionalFilter
from filters.quality_scorer import QualityScorer
from exporters.csv_exporter import CSVExporter
from exporters.excel_exporter import ExcelExporter
from utils.logger import get_logger

logger = get_logger("run_example")


# ===========================================================================
# EXEMPLO 1 — Ginecologistas em Nova Serrana - MG
#   Caso de uso: prospecção em cidade menor onde a concorrência é mais baixa.
#   Exporta CSV com todos os profissionais aprovados.
# ===========================================================================
async def example_1_ginecologistas_nova_serrana() -> None:
    print("\n" + "=" * 65)
    print("EXEMPLO 1: Ginecologistas em Nova Serrana - MG")
    print("=" * 65)

    async with BrowserManager(headless=True) as browser:
        scraper = DoctoraliaScraper(browser, max_pages=5)
        leads = await scraper.search("ginecologista", "Nova Serrana")

    prof_filter = ProfessionalFilter()
    approved, discarded = prof_filter.filter_list(leads)

    scorer = QualityScorer()
    approved = scorer.score_all(approved)

    path = CSVExporter().save(approved, "ginecologistas_nova_serrana")

    print(f"  Total extraído  : {len(leads)}")
    print(f"  Aprovados       : {len(approved)}")
    print(f"  Descartados     : {len(discarded)}")
    print(f"  Arquivo gerado  : {path}")


# ===========================================================================
# EXEMPLO 2 — Psicólogos em Belo Horizonte - MG
#   Caso de uso: busca em cidade grande com exportação Excel e duas abas
#   (todos + leads quentes). Filtra apenas leads com score >= 40.
# ===========================================================================
async def example_2_psicologos_belo_horizonte() -> None:
    print("\n" + "=" * 65)
    print("EXEMPLO 2: Psicólogos em Belo Horizonte - MG")
    print("=" * 65)

    async with BrowserManager(headless=True) as browser:
        scraper = DoctoraliaScraper(browser, max_pages=3)
        leads = await scraper.search("psicologo", "Belo Horizonte")

    prof_filter = ProfessionalFilter()
    approved, discarded = prof_filter.filter_list(leads)

    scorer = QualityScorer()
    approved = scorer.score_all(approved)

    # Exporta apenas leads com score satisfatório
    filtered = [l for l in approved if l.score_qualidade >= 40]

    path = ExcelExporter().save(filtered, discarded, "psicologos_bh")

    hot = sum(1 for l in filtered if l.score_qualidade >= 80)
    print(f"  Total extraído  : {len(leads)}")
    print(f"  Score >= 40     : {len(filtered)}")
    print(f"  🔥 Leads quentes : {hot}")
    print(f"  Arquivo gerado  : {path}")


# ===========================================================================
# EXEMPLO 3 — Dentistas em Contagem - MG
#   Caso de uso: exportação dupla (CSV + Excel) para diferentes membros
#   da equipe. Demonstra uso simultâneo dos dois exportadores.
# ===========================================================================
async def example_3_dentistas_contagem() -> None:
    print("\n" + "=" * 65)
    print("EXEMPLO 3: Dentistas em Contagem - MG")
    print("=" * 65)

    async with BrowserManager(headless=True) as browser:
        scraper = DoctoraliaScraper(browser, max_pages=4)
        leads = await scraper.search("dentista", "Contagem")

    prof_filter = ProfessionalFilter()
    approved, discarded = prof_filter.filter_list(leads)

    scorer = QualityScorer()
    approved = scorer.score_all(approved)

    csv_path = CSVExporter().save(approved, "dentistas_contagem")
    xl_path = ExcelExporter().save(approved, discarded, "dentistas_contagem")

    print(f"  Total extraído  : {len(leads)}")
    print(f"  Aprovados       : {len(approved)}")
    print(f"  CSV             : {csv_path}")
    print(f"  Excel           : {xl_path}")


# ===========================================================================
# Runner principal
# ===========================================================================
async def main() -> None:
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    print("\n🚀  Iniciando exemplos de uso do health-lead-extractor…\n")

    # Rode apenas o exemplo desejado comentando/descomentando as linhas abaixo:
    await example_1_ginecologistas_nova_serrana()
    await example_2_psicologos_belo_horizonte()
    await example_3_dentistas_contagem()

    print("\n✅  Todos os exemplos concluídos! Verifique a pasta output/\n")


if __name__ == "__main__":
    asyncio.run(main())
