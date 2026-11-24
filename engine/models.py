from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ScrapeMode(str, Enum):
    HTTPX = "httpx"
    PLAYWRIGHT = "playwright"


class ExportFormat(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"
    SQLITE = "sqlite"
    TXT = "txt"
    MD = "md"
    JSON = "json"


class PresetConfig(BaseModel):
    name: str
    description: str = ""
    item_selector: str = ""
    fields: Dict[str, str] = Field(default_factory=dict)


class ScraperConfig(BaseModel):
    mode: ScrapeMode = ScrapeMode.HTTPX
    workers: int = Field(default=3, ge=1, le=20)
    delay: float = Field(default=0.5, ge=0.0)
    rotate_ua: bool = True
    timeout: float = Field(default=15.0, ge=1.0)
    item_selector: str = ""
    fields: Dict[str, str] = Field(default_factory=dict)


class ScrapedItem(BaseModel):
    url: str
    data: Dict[str, Any]
    error: Optional[str] = None


class ScrapeResult(BaseModel):
    total_urls: int = 0
    success_count: int = 0
    fail_count: int = 0
    items: List[ScrapedItem] = Field(default_factory=list)
