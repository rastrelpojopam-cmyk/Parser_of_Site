import asyncio
from typing import AsyncGenerator, List, Optional
import httpx
from fake_useragent import UserAgent

from engine.models import ScraperConfig, ScrapedItem
from engine.extractor import DataExtractor
from engine.utils import browser_headers, normalize_url


class HttpScraper:
    def __init__(self, config: ScraperConfig):
        self.config = config
        self._ua = UserAgent() if config.rotate_ua else None
        self._stopped = False

    def stop(self):
        self._stopped = True

    def _get_headers(self) -> dict:
        user_agent = self._ua.random if self._ua else None
        return browser_headers(user_agent)

    async def scrape_url(
        self, client: httpx.AsyncClient, url: str
    ) -> List[ScrapedItem]:
        if self._stopped:
            return []

        url = normalize_url(url)

        try:
            headers = self._get_headers()
            response = await client.get(
                url,
                headers=headers,
                timeout=self.config.timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
            html = response.text

            rows = DataExtractor.extract_all(
                html=html,
                item_selector=self.config.item_selector,
                fields=self.config.fields,
                source_url=url,
            )

            if not rows:
                return [ScrapedItem(url=url, data={"content": "Ничего не найдено по селекторам"})]

            return [ScrapedItem(url=url, data=row) for row in rows]

        except Exception as e:
            return [ScrapedItem(url=url, data={}, error=str(e))]

    async def run(
        self, urls: List[str]
    ) -> AsyncGenerator[List[ScrapedItem], None]:
        semaphore = asyncio.Semaphore(self.config.workers)

        async with httpx.AsyncClient(verify=False) as client:
            queue: asyncio.Queue[str] = asyncio.Queue()
            for url in urls:
                queue.put_nowait(url)

            while not queue.empty() and not self._stopped:
                batch_tasks = []
                batch_size = min(self.config.workers, queue.qsize())

                for _ in range(batch_size):
                    url = queue.get_nowait()

                    async def worker_task(target_url=url):
                        async with semaphore:
                            if self._stopped:
                                return []
                            items = await self.scrape_url(client, target_url)
                            if self.config.delay > 0:
                                await asyncio.sleep(self.config.delay)
                            return items

                    batch_tasks.append(asyncio.create_task(worker_task()))

                results = await asyncio.gather(*batch_tasks)
                for res in results:
                    yield res
