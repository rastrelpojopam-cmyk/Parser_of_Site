import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List
import aiosqlite
import openpyxl

from engine.models import ScrapedItem, ExportFormat
from formatter import ResultFormatter


class ResultStorage:
    def __init__(self, output_dir: str | None = None):
        self.output_dir = (
            Path(output_dir) if output_dir else Path(__file__).resolve().parent / "output"
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _generate_filename(self, ext: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.output_dir / f"scrape_{timestamp}.{ext}"

    async def export(self, items: List[ScrapedItem], fmt: ExportFormat) -> str:
        if fmt == ExportFormat.CSV:
            return self.export_csv(items)
        elif fmt == ExportFormat.XLSX:
            return self.export_xlsx(items)
        elif fmt == ExportFormat.SQLITE:
            return await self.export_sqlite(items)
        elif fmt == ExportFormat.TXT:
            return self.export_txt(items)
        elif fmt == ExportFormat.MD:
            return self.export_md(items)
        elif fmt == ExportFormat.JSON:
            return self.export_json(items)
        raise ValueError(f"Неизвестный формат: {fmt}")

    def export_csv(self, items: List[ScrapedItem]) -> str:
        filepath = self._generate_filename("csv")
        keys = set()
        for it in items:
            keys.update(it.data.keys())
        fieldnames = ["url"] + sorted(list(keys)) + ["error"]

        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for it in items:
                row = {"url": it.url, "error": it.error or ""}
                row.update(it.data)
                writer.writerow(row)
        return str(filepath)

    def export_xlsx(self, items: List[ScrapedItem]) -> str:
        filepath = self._generate_filename("xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Results"

        keys = set()
        for it in items:
            keys.update(it.data.keys())
        fieldnames = ["url"] + sorted(list(keys)) + ["error"]

        ws.append(fieldnames)
        for it in items:
            row = [it.url]
            for k in sorted(list(keys)):
                val = it.data.get(k, "")
                row.append(str(val) if val is not None else "")
            row.append(it.error or "")
            ws.append(row)

        wb.save(filepath)
        return str(filepath)

    async def export_sqlite(self, items: List[ScrapedItem]) -> str:
        filepath = self._generate_filename("db")
        keys = set()
        for it in items:
            keys.update(it.data.keys())
        clean_keys = [k.replace("-", "_").replace(" ", "_") for k in sorted(list(keys))]

        col_defs = ", ".join([f'"{k}" TEXT' for k in clean_keys])
        col_clause = f", {col_defs}" if col_defs else ""

        async with aiosqlite.connect(filepath) as db:
            await db.execute(
                f"""CREATE TABLE IF NOT EXISTS scraped_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT,
                    error TEXT{col_clause}
                )"""
            )

            columns = ["url", "error"] + clean_keys
            col_names = ", ".join([f'"{c}"' for c in columns])
            placeholders = ", ".join(["?"] * len(columns))

            for it in items:
                vals = [it.url, it.error or ""]
                for orig_k in sorted(list(keys)):
                    vals.append(str(it.data.get(orig_k, "")))
                await db.execute(
                    f"INSERT INTO scraped_data ({col_names}) VALUES ({placeholders})",
                    vals,
                )
            await db.commit()

        return str(filepath)

    def export_txt(self, items: List[ScrapedItem]) -> str:
        filepath = self._generate_filename("txt")
        content = ResultFormatter.to_cards_text(items)
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)

    def export_md(self, items: List[ScrapedItem]) -> str:
        filepath = self._generate_filename("md")
        content = ResultFormatter.to_markdown(items)
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)

    def export_json(self, items: List[ScrapedItem]) -> str:
        filepath = self._generate_filename("json")
        content = ResultFormatter.to_json(items)
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)
