import asyncio
from typing import AsyncGenerator, List
from fake_useragent import UserAgent
from playwright.async_api import async_playwright, Browser, BrowserContext

from engine.models import ScraperConfig, ScrapedItem
from engine.extractor import DataExtractor
from engine.utils import CHROME_USER_AGENT, normalize_url


class BrowserScraper:
    def __init__(self, config: ScraperConfig):
        self.config = config
        self._ua = UserAgent() if config.rotate_ua else None
        self._stopped = False

    def stop(self):
        self._stopped = True

    def _get_ua(self) -> str:
        if self._ua:
            return self._ua.random
        return CHROME_USER_AGENT

    async def scrape_url(
        self, context: BrowserContext, url: str
    ) -> List[ScrapedItem]:
        if self._stopped:
            return []

        url = normalize_url(url)

        page = None
        try:
            page = await context.new_page()
            await page.goto(
                url,
                timeout=int(self.config.timeout * 1000),
                wait_until="domcontentloaded",
            )
            # Небольшое ожидание динамической подгрузки JS
            await asyncio.sleep(0.5)

            html = await page.content()

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
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    async def run(
        self, urls: List[str]
    ) -> AsyncGenerator[List[ScrapedItem], None]:
        semaphore = asyncio.Semaphore(self.config.workers)

        async with async_playwright() as pw:
            browser: Browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"],
            )

            context: BrowserContext = await browser.new_context(
                user_agent=self._get_ua(),
                viewport={"width": 1280, "height": 800},
            )

            queue: asyncio.Queue[str] = asyncio.Queue()
            for url in urls:
                queue.put_nowait(url)

            try:
                while not queue.empty() and not self._stopped:
                    batch_tasks = []
                    batch_size = min(self.config.workers, queue.qsize())

                    for _ in range(batch_size):
                        url = queue.get_nowait()

                        async def worker_task(target_url=url):
                            async with semaphore:
                                if self._stopped:
                                    return []
                                items = await self.scrape_url(context, target_url)
                                if self.config.delay > 0:
                                    await asyncio.sleep(self.config.delay)
                                return items

                        batch_tasks.append(asyncio.create_task(worker_task()))

                    results = await asyncio.gather(*batch_tasks)
                    for res in results:
                        yield res
            finally:
                await context.close()
                await browser.close()
