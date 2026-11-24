import asyncio
from pathlib import Path
from typing import Optional
import typer
import yaml
from rich.console import Console

from engine.models import ScrapeMode, ScraperConfig, ExportFormat
from engine.http_scraper import HttpScraper
from engine.browser_scraper import BrowserScraper
from formatter import ResultFormatter
from storage import ResultStorage

app = typer.Typer(help="Асинхронный веб-скрапер (TUI / CLI)")
console = Console()


def load_config() -> dict:
    cfg_path = Path(__file__).resolve().parent / "config.yaml"
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    url: Optional[str] = typer.Option(None, "--url", "-u", help="URL или путь к файлу со ссылками"),
    preset: Optional[str] = typer.Option(None, "--preset", "-p", help="Имя пресета из config.yaml"),
    mode: ScrapeMode = typer.Option(ScrapeMode.HTTPX, "--mode", "-m", help="Режим скрапинга: httpx или playwright"),
    format: str = typer.Option("table", "--format", "-f", help="Формат вывода в терминал: table | text | json"),
    export: Optional[ExportFormat] = typer.Option(None, "--export", "-e", help="Экспорт в файл: csv, xlsx, sqlite, txt, md, json"),
    workers: int = typer.Option(3, "--workers", "-w", help="Число параллельных воркеров"),
    delay: float = typer.Option(0.5, "--delay", "-d", help="Задержка между запросами в секундах"),
    item_selector: Optional[str] = typer.Option(None, "--item-sel", help="CSS селектор контейнера элемента"),
    fields: Optional[str] = typer.Option(None, "--fields", help="Поля 'name=sel; price=sel'"),
):
    """
    По умолчанию запускает TUI.
    Если передан параметр --url, выполняет парсинг в CLI режиме.
    """
    if ctx.invoked_subcommand is not None:
        return

    if url is None:
        # Запуск TUI интерфейса
        from tui import ScraperApp

        tui_app = ScraperApp()
        tui_app.run()
        return

    # CLI режим
    asyncio.run(
        run_cli_scraper(
            url_target=url,
            preset_name=preset,
            mode=mode,
            output_format=format,
            export_format=export,
            workers=workers,
            delay=delay,
            custom_item_selector=item_selector,
            custom_fields=fields,
        )
    )


async def run_cli_scraper(
    url_target: str,
    preset_name: Optional[str],
    mode: ScrapeMode,
    output_format: str,
    export_format: Optional[ExportFormat],
    workers: int,
    delay: float,
    custom_item_selector: Optional[str],
    custom_fields: Optional[str],
):
    cfg_data = load_config()
    presets = cfg_data.get("presets", {})

    target_item_sel = ""
    target_fields = {}

    if preset_name and preset_name in presets:
        p = presets[preset_name]
        target_item_sel = p.get("item_selector", "")
        target_fields = p.get("fields", {})

    if custom_item_selector is not None:
        target_item_sel = custom_item_selector

    if custom_fields:
        for part in custom_fields.split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                target_fields[k.strip()] = v.strip()

    # Считываем ссылки
    target_path = Path(url_target)
    if target_path.exists() and target_path.is_file():
        urls = [line.strip() for line in target_path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    else:
        urls = [url_target]

    scraper_cfg = ScraperConfig(
        mode=mode,
        workers=workers,
        delay=delay,
        item_selector=target_item_sel,
        fields=target_fields,
    )

    console.print(f"[bold green]Запуск CLI скрапера[/]: {len(urls)} URL, режим {mode.value}")
    scraper_cls = HttpScraper if mode == ScrapeMode.HTTPX else BrowserScraper
    scraper = scraper_cls(scraper_cfg)

    all_items = []
    async for batch in scraper.run(urls):
        all_items.extend(batch)

    # Вывод в консоль
    if output_format == "table":
        table = ResultFormatter.to_rich_table(all_items)
        console.print(table)
    elif output_format == "text":
        cards = ResultFormatter.to_cards_text(all_items)
        console.print(cards)
    elif output_format == "json":
        json_str = ResultFormatter.to_json(all_items)
        console.print(json_str)

    # Экспорт если указан
    if export_format:
        storage = ResultStorage()
        saved_path = await storage.export(all_items, export_format)
        console.print(f"[bold green]Результаты успешно сохранены в:[/] {saved_path}")


if __name__ == "__main__":
    app()
