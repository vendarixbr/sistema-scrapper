"""Logging configuration using the Rich library."""

import logging
from pathlib import Path
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from config import OUTPUT_DIR, LOG_LEVEL

Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

console = Console()

_LOGGERS: dict[str, logging.Logger] = {}


def get_logger(name: str) -> logging.Logger:
    """Return a Rich-formatted logger with file output."""
    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(name)
    if logger.handlers:
        _LOGGERS[name] = logger
        return logger

    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(logging.DEBUG)

    console_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        markup=True,
        show_path=False,
        level=level,
    )

    log_file = Path(OUTPUT_DIR) / "scraper.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = False

    _LOGGERS[name] = logger
    return logger


def create_progress() -> Progress:
    """Create an animated Rich progress bar for scraping operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=False,
    )


def print_summary_table(
    total: int,
    aprovados: int,
    descartados: int,
    quentes: int,
    qualificados: int,
    mornos: int,
    frios: int,
    tempo: float,
) -> None:
    """Print a formatted summary table to the terminal."""
    table = Table(
        title="\n[bold green]Resumo da Extração[/bold green]",
        show_header=True,
        header_style="bold white on dark_green",
        border_style="green",
    )
    table.add_column("Métrica", style="bold", min_width=30)
    table.add_column("Valor", justify="right", min_width=10)

    table.add_row("Total extraído", str(total))
    table.add_row("Profissionais aprovados", f"[green]{aprovados}[/green]")
    table.add_row("Clínicas / empresas descartadas", f"[red]{descartados}[/red]")
    table.add_row("🔥 Leads Quentes (score 80–100)", f"[bold red]{quentes}[/bold red]")
    table.add_row("⭐ Leads Qualificados (score 60–79)", f"[yellow]{qualificados}[/yellow]")
    table.add_row("👀 Leads Mornos (score 40–59)", f"[cyan]{mornos}[/cyan]")
    table.add_row("❄️  Leads Frios (score 0–39)", f"[blue]{frios}[/blue]")
    table.add_row("Tempo total de execução", f"{tempo:.1f}s")

    console.print(table)
