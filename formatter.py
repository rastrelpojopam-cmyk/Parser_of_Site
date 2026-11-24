import json
from typing import Any, Dict, List
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from engine.models import ScrapedItem


class ResultFormatter:
    @staticmethod
    def to_rich_table(items: List[ScrapedItem], title: str = "Результаты парсинга") -> Table:
        table = Table(title=title, expand=True, show_lines=True)
        table.add_column("№", style="cyan", width=5)
        table.add_column("URL", style="blue", max_width=30, overflow="ellipsis")

        # Определяем уникальные ключи колонок
        keys: List[str] = []
        for it in items:
            for k in it.data.keys():
                if k not in keys:
                    keys.append(k)

        for k in keys:
            table.add_column(k, style="green")

        table.add_column("Ошибка", style="red")

        for idx, it in enumerate(items, 1):
            row_data = [str(idx), it.url]
            for k in keys:
                val = it.data.get(k, "")
                row_data.append(str(val) if val is not None else "")
            row_data.append(it.error or "")
            table.add_row(*row_data)

        return table

    @staticmethod
    def to_cards_text(items: List[ScrapedItem]) -> str:
        blocks = []
        for idx, it in enumerate(items, 1):
            lines = [f"=== Запись #{idx} ===", f"URL: {it.url}"]
            if it.error:
                lines.append(f"Ошибка: {it.error}")
            for k, v in it.data.items():
                lines.append(f"{k}: {v}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    @staticmethod
    def to_markdown(items: List[ScrapedItem]) -> str:
        lines = ["# Результаты скрапинга\n"]
        for idx, it in enumerate(items, 1):
            lines.append(f"### Запись {idx}")
            lines.append(f"- **URL**: {it.url}")
            if it.error:
                lines.append(f"- **Ошибка**: {it.error}")
            for k, v in it.data.items():
                lines.append(f"- **{k}**: {v}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def to_json(items: List[ScrapedItem], indent: int = 2) -> str:
        payload = [it.model_dump() for it in items]
        return json.dumps(payload, ensure_ascii=False, indent=indent)
