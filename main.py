"""CLI entry point for health-lead-extractor."""

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Fix asyncio on Windows with Python 3.10+
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from rich.console import Console
from rich.panel import Panel

from config import OUTPUT_DIR, ESPECIALIDADES_SLUGS
from scraper.browser_manager import BrowserManager
from scraper.doctoralia_scraper import DoctoraliaScraper
from filters.professional_filter import ProfessionalFilter
from filters.quality_scorer import QualityScorer
from exporters.csv_exporter import CSVExporter
from exporters.excel_exporter import ExcelExporter
from utils.logger import get_logger, print_summary_table, create_progress

logger = get_logger(__name__)
console = Console()

_BANNER = """
[bold green]  _   _            _ _   _       _               _
 | | | | ___  __ _| | |_| |__   | |    ___  __ _  __| |
 | |_| |/ _ \/ _` | | __| '_ \  | |   / _ \/ _` |/ _` |
 |  _  |  __/ (_| | | |_| | | | | |__|  __/ (_| | (_| |
 |_| |_|\___|\__,_|_|\__|_| |_| |_____\___|\__,_|\__,_|
[/bold green]
[dim]Extração de leads de profissionais de saúde — Doctoralia Brasil[/dim]
"""


def _print_banner() -> None:
    console.print(Panel(_BANNER.strip(), border_style="green", padding=(0, 2)))


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Extrai leads de profissionais de saúde do Doctoralia Brasil",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-e", "--especialidade", type=str, default="",
                   help="Especialidade (ex: ginecologista)")
    p.add_argument("-c", "--cidade", type=str, default="",
                   help="Cidade (ex: 'Nova Serrana')")
    p.add_argument("-s", "--estado", type=str, default="MG",
                   help="Sigla do estado (default: MG)")
    p.add_argument("--max-paginas", type=int, default=10,
                   help="Máximo de páginas (default: 10)")
    p.add_argument("--headless", action="store_true", default=True,
                   help="Rodar sem abrir browser (default)")
    p.add_argument("--debug", action="store_false", dest="headless",
                   help="Modo debug: browser visível + logs detalhados")
    p.add_argument("--output", type=str, default="leads",
                   help="Nome base dos arquivos de saída (default: leads)")
    p.add_argument("--formato", choices=["csv", "excel", "ambos"], default="ambos",
                   help="Formato de exportação (default: ambos)")
    p.add_argument("--min-score", type=int, default=0,
                   help="Exportar apenas leads com score >= N (default: 0)")
    return p


async def _run(args: argparse.Namespace) -> None:
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    especialidade = args.especialidade.strip()
    cidade = args.cidade.strip()

    # Interactive mode when no CLI arguments provided
    if not especialidade:
        console.print("\n[bold]Especialidades disponíveis:[/bold]")
        for i, esp in enumerate(ESPECIALIDADES_SLUGS, 1):
            console.print(f"  [cyan]{i:2}.[/cyan] {esp}")
        especialidade = console.input("\n[bold cyan]Digite a especialidade:[/bold cyan] ").strip()

    if not cidade:
        cidade = console.input("[bold cyan]Digite a cidade:[/bold cyan] ").strip()

    if not especialidade or not cidade:
        logger.error("Especialidade e cidade são obrigatórios.")
        return

    start_time = time.time()
    leads_raw: list = []
    approved: list = []
    discarded: list = []

    try:
        async with BrowserManager(headless=args.headless) as browser:
            scraper = DoctoraliaScraper(browser, max_pages=args.max_paginas)

            with create_progress() as progress:
                task_id = progress.add_task(
                    f"[green]Extraindo [bold]{especialidade}[/bold] em [bold]{cidade}[/bold]…",
                    total=None,
                )
                try:
                    leads_raw = await scraper.search(especialidade, cidade)
                except KeyboardInterrupt:
                    logger.warning("Interrompido pelo usuário. Salvando dados parciais…")
                    leads_raw = scraper._leads_collected
                finally:
                    progress.update(task_id, completed=True)

    except KeyboardInterrupt:
        logger.warning("Interrompido antes da extração iniciar.")
    except Exception as exc:
        logger.exception("Erro inesperado: %s", exc)

    if not leads_raw:
        logger.warning("Nenhum lead encontrado. Encerrando.")
        return

    # Filter clinics vs individuals
    prof_filter = ProfessionalFilter()
    approved, discarded = prof_filter.filter_list(leads_raw)

    # Score
    scorer = QualityScorer()
    approved = scorer.score_all(approved)

    # Optional score gate
    if args.min_score > 0:
        before = len(approved)
        approved = [l for l in approved if l.score_qualidade >= args.min_score]
        logger.info("Score filter (>=%d): %d → %d leads.", args.min_score, before, len(approved))

    # Summary
    elapsed = time.time() - start_time
    print_summary_table(
        total=len(leads_raw),
        aprovados=len(approved),
        descartados=len(discarded),
        quentes=sum(1 for l in approved if l.score_qualidade >= 80),
        qualificados=sum(1 for l in approved if 60 <= l.score_qualidade < 80),
        mornos=sum(1 for l in approved if 40 <= l.score_qualidade < 60),
        frios=sum(1 for l in approved if l.score_qualidade < 40),
        tempo=elapsed,
    )

    # Export
    output_files: list[str] = []

    if args.formato in ("csv", "ambos"):
        path = CSVExporter().save(approved, args.output)
        output_files.append(path)

    if args.formato in ("excel", "ambos"):
        path = ExcelExporter().save(approved, discarded, args.output)
        output_files.append(path)

    console.print("\n[bold green]Arquivos gerados:[/bold green]")
    for f in output_files:
        console.print(f"  [link=file://{f}]{f}[/link]")

    console.print()


def main() -> None:
    _print_banner()
    args = _build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
