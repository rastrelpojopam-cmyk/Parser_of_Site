from pathlib import Path
from typing import Dict, List, Optional
import yaml
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ProgressBar,
    RichLog,
    Select,
    Switch,
    TabbedContent,
    TabPane,
)

from engine.models import ScrapeMode, ScraperConfig, ScrapedItem, ExportFormat
from engine.http_scraper import HttpScraper
from engine.browser_scraper import BrowserScraper
from storage import ResultStorage
from formatter import ResultFormatter


class ScraperApp(App):
    CSS = """
    Screen {
        background: $surface;
    }
    #top-bar {
        height: auto;
        padding: 1;
        background: $panel;
        border-bottom: heavy $primary;
    }
    .input-row {
        height: auto;
        margin-bottom: 1;
    }
    .input-label {
        width: 24;
        padding-top: 1;
        text-style: bold;
    }
    .settings-col {
        width: 1fr;
        padding-right: 1;
    }
    #preview-container {
        height: 1fr;
    }
    #actions-bar {
        height: auto;
        padding: 1;
        background: $panel;
        border-top: heavy $primary;
    }
    #log-pane {
        height: 12;
        border: solid $secondary;
        background: $boost;
    }
    Button {
        margin-right: 1;
    }
    """

    TITLE = "Web Scraper TUI"
    SUB_TITLE = "httpx + selectolax + Playwright"

    def __init__(self):
        super().__init__()
        self.config_data = self._load_config()
        self.items: List[ScrapedItem] = []
        self.current_scraper = None
        self.scraping_active = False
        self.storage = ResultStorage()
        self.table_initialized = False

    def _load_config(self) -> dict:
        cfg_path = Path(__file__).resolve().parent / "config.yaml"
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def compose(self) -> ComposeResult:
        yield Header()

        presets = self.config_data.get("presets", {})
        preset_options = [(p.get("name", k), k) for k, p in presets.items()]

        with Vertical(id="top-bar"):
            with Horizontal(classes="input-row"):
                yield Label("URL / Файл:", classes="input-label")
                yield Input(
                    id="url-input",
                    placeholder="https://books.toscrape.com/ или путь к .txt файлу",
                    value="https://books.toscrape.com/",
                )

            with Horizontal(classes="input-row"):
                with Horizontal(classes="settings-col"):
                    yield Label("Режим:", classes="input-label")
                    yield Select(
                        [("HTTPX (быстрый)", ScrapeMode.HTTPX.value), ("Playwright (JS)", ScrapeMode.PLAYWRIGHT.value)],
                        value=ScrapeMode.HTTPX.value,
                        id="mode-select",
                    )

                with Horizontal(classes="settings-col"):
                    yield Label("Пресет:", classes="input-label")
                    yield Select(
                        preset_options,
                        value="books_to_scrape" if "books_to_scrape" in presets else None,
                        id="preset-select",
                    )

            with Horizontal(classes="input-row"):
                with Horizontal(classes="settings-col"):
                    yield Label("CSS-селектор (необязательно):", classes="input-label")
                    yield Input(
                        id="item-selector-input",
                        placeholder="article.post (пусто — автоизвлечение всей статьи)",
                        value=presets.get("books_to_scrape", {}).get("item_selector", ""),
                    )
                with Horizontal(classes="settings-col"):
                    yield Label("Поля (k=css;):", classes="input-label")
                    fields_init = "; ".join(
                        f"{k}={v}" for k, v in presets.get("books_to_scrape", {}).get("fields", {}).items()
                    )
                    yield Input(
                        id="fields-input",
                        placeholder="title=h3 a::attr(title); price=.price_color::text",
                        value=fields_init,
                    )

            with Horizontal(classes="input-row"):
                with Horizontal(classes="settings-col"):
                    yield Label("Воркеры:", classes="input-label")
                    yield Input(id="workers-input", value="3", max_length=2)
                with Horizontal(classes="settings-col"):
                    yield Label("Задержка (сек):", classes="input-label")
                    yield Input(id="delay-input", value="0.5")
                with Horizontal(classes="settings-col"):
                    yield Label("Rotate UA:", classes="input-label")
                    yield Switch(value=True, id="ua-switch")

        with Container(id="preview-container"):
            with TabbedContent(initial="tab-table"):
                with TabPane("Таблица", id="tab-table"):
                    yield DataTable(id="data-table", zebra_stripes=True)
                with TabPane("Текст / Карточки", id="tab-cards"):
                    yield RichLog(id="cards-log", markup=True, wrap=True)
                with TabPane("Логи процесса", id="tab-logs"):
                    yield RichLog(id="process-log", markup=True, wrap=True)

        with Vertical(id="actions-bar"):
            yield ProgressBar(id="progress-bar", total=100, show_eta=True)
            with Horizontal():
                yield Button("▶ Старт", id="btn-start", variant="success")
                yield Button("⏹ Стоп", id="btn-stop", variant="error", disabled=True)
                yield Button("🗑 Очистить", id="btn-clear", variant="default")
                yield Label("  Экспорт (Табл):", classes="input-label")
                yield Button("CSV", id="btn-exp-csv", variant="primary")
                yield Button("XLSX", id="btn-exp-xlsx", variant="primary")
                yield Button("SQLite", id="btn-exp-sqlite", variant="primary")
                yield Label("  Экспорт (Текст):", classes="input-label")
                yield Button("TXT", id="btn-exp-txt", variant="warning")
                yield Button("MD", id="btn-exp-md", variant="warning")
                yield Button("JSON", id="btn-exp-json", variant="warning")

        yield Footer()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "preset-select" and event.value:
            preset_key = event.value
            preset = self.config_data.get("presets", {}).get(preset_key, {})
            item_sel_input = self.query_one("#item-selector-input", Input)
            fields_input = self.query_one("#fields-input", Input)
            item_sel_input.value = preset.get("item_selector", "")
            fields_str = "; ".join(f"{k}={v}" for k, v in preset.get("fields", {}).items())
            fields_input.value = fields_str
            self.log_message(f"[cyan]Применен пресет:[/] {preset.get('name', preset_key)}")

    def log_message(self, message: str) -> None:
        process_log = self.query_one("#process-log", RichLog)
        process_log.write(message)

    def _parse_fields(self, raw_str: str) -> Dict[str, str]:
        fields = {}
        parts = [p.strip() for p in raw_str.split(";") if p.strip()]
        for p in parts:
            if "=" in p:
                k, v = p.split("=", 1)
                fields[k.strip()] = v.strip()
        return fields

    def _get_urls(self, raw_input: str) -> List[str]:
        raw_input = raw_input.strip()
        path = Path(raw_input)
        if path.exists() and path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip() and not line.startswith("#")]
        return [raw_input] if raw_input else []

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-start":
            self.start_scraping()
        elif btn_id == "btn-stop":
            self.stop_scraping()
        elif btn_id == "btn-clear":
            self.clear_results()
        elif btn_id == "btn-exp-csv":
            self.export_action(ExportFormat.CSV)
        elif btn_id == "btn-exp-xlsx":
            self.export_action(ExportFormat.XLSX)
        elif btn_id == "btn-exp-sqlite":
            self.export_action(ExportFormat.SQLITE)
        elif btn_id == "btn-exp-txt":
            self.export_action(ExportFormat.TXT)
        elif btn_id == "btn-exp-md":
            self.export_action(ExportFormat.MD)
        elif btn_id == "btn-exp-json":
            self.export_action(ExportFormat.JSON)

    def clear_results(self) -> None:
        self.items.clear()
        table = self.query_one("#data-table", DataTable)
        table.clear(columns=True)
        self.table_initialized = False
        cards_log = self.query_one("#cards-log", RichLog)
        cards_log.clear()
        prog = self.query_one("#progress-bar", ProgressBar)
        prog.progress = 0
        self.log_message("[yellow]Таблицы и результаты очищены.[/]")

    def stop_scraping(self) -> None:
        if self.current_scraper:
            self.current_scraper.stop()
            self.log_message("[bold red]Остановка парсера...[/]")

    def start_scraping(self) -> None:
        if self.scraping_active:
            return

        url_input = self.query_one("#url-input", Input).value
        urls = self._get_urls(url_input)
        if not urls:
            self.notify("Укажите корректный URL или файл со ссылками!", severity="error")
            return

        mode_str = self.query_one("#mode-select", Select).value or ScrapeMode.HTTPX.value
        item_selector = self.query_one("#item-selector-input", Input).value
        fields_str = self.query_one("#fields-input", Input).value
        fields = self._parse_fields(fields_str)

        try:
            workers = int(self.query_one("#workers-input", Input).value or "3")
        except ValueError:
            workers = 3

        try:
            delay = float(self.query_one("#delay-input", Input).value or "0.5")
        except ValueError:
            delay = 0.5

        rotate_ua = self.query_one("#ua-switch", Switch).value

        config = ScraperConfig(
            mode=ScrapeMode(mode_str),
            workers=workers,
            delay=delay,
            rotate_ua=rotate_ua,
            item_selector=item_selector,
            fields=fields,
        )

        self.query_one("#btn-start", Button).disabled = True
        self.query_one("#btn-stop", Button).disabled = False
        self.scraping_active = True

        prog = self.query_one("#progress-bar", ProgressBar)
        prog.total = len(urls)
        prog.progress = 0

        self.log_message(f"[bold green]Запуск парсинга:[/] {len(urls)} URL, режим={mode_str}, воркеры={workers}")
        self.run_scrape_task(urls, config)

    @work(exclusive=True)
    async def run_scrape_task(self, urls: List[str], config: ScraperConfig) -> None:
        scraper_cls = HttpScraper if config.mode == ScrapeMode.HTTPX else BrowserScraper
        self.current_scraper = scraper_cls(config)

        table = self.query_one("#data-table", DataTable)
        cards_log = self.query_one("#cards-log", RichLog)
        prog = self.query_one("#progress-bar", ProgressBar)

        processed = 0
        try:
            async for batch in self.current_scraper.run(urls):
                processed += 1
                prog.advance(1)

                for item in batch:
                    self.items.append(item)

                    if not self.table_initialized and self.items:
                        columns = ["URL"] + list(item.data.keys()) + ["Ошибка"]
                        table.add_columns(*columns)
                        self.table_initialized = True

                    # Добавляем в таблицу
                    row = [item.url] + [str(v) for v in item.data.values()] + [item.error or ""]
                    table.add_row(*row)

                    # Добавляем в карточки
                    card_text = f"[bold cyan]URL:[/] {item.url}\n"
                    if item.error:
                        card_text += f"[bold red]Ошибка:[/] {item.error}\n"
                    for k, v in item.data.items():
                        card_text += f"[bold green]{k}:[/] {v}\n"
                    card_text += "[dim]----------------------------------------[/]"
                    cards_log.write(card_text)

                self.log_message(f"Обработан URL ({processed}/{len(urls)}), получено записей: {len(batch)}")

        except Exception as e:
            self.log_message(f"[bold red]Ошибка в процессе:[/] {e}")
        finally:
            self.scraping_active = False
            self.query_one("#btn-start", Button).disabled = False
            self.query_one("#btn-stop", Button).disabled = True
            self.log_message(f"[bold green]Парсинг завершен![/] Всего элементов собрано: {len(self.items)}")
            self.notify(f"Завершено! Найдено {len(self.items)} записей.")

    @work(exclusive=False)
    async def export_action(self, fmt: ExportFormat) -> None:
        if not self.items:
            self.notify("Нет данных для экспорта!", severity="warning")
            return

        try:
            path = await self.storage.export(self.items, fmt)
            self.log_message(f"[bold green]Экспорт успешно выполнен ({fmt.value}):[/] {path}")
            self.notify(f"Сохранено: {path}")
        except Exception as e:
            self.log_message(f"[bold red]Ошибка при экспорте:[/] {e}")
            self.notify(f"Ошибка экспорта: {e}", severity="error")


if __name__ == "__main__":
    app = ScraperApp()
    app.run()
