# Universal Fast & Resilient Web Scraper

Асинхронный веб-скрапер на Python с интерактивным терминальным интерфейсом (**Textual TUI**), пакетным режимом (**Typer CLI**), двумя движками парсинга (**httpx + selectolax** и **Playwright**) и экспортом результатов в CSV, Excel, SQLite, JSON, Markdown и TXT.

## Возможности

- **Два режима парсинга:**
  - 🚀 `httpx` — быстрый асинхронный сбор статических страниц через `httpx` и HTML-парсер `selectolax` (Lexbor).
  - 🌐 `playwright` — headless Chromium для сайтов с JavaScript, SPA и динамической подгрузкой контента.
- **Два интерфейса:**
  - 💻 **TUI (Textual):** URL, пресеты, селекторы, воркеры, задержка, ротация User-Agent, таблица результатов, карточки, логи, прогресс-бар, старт/стоп и кнопки экспорта.
  - ⚡ **CLI (Typer):** парсинг одной командой с выводом в терминал (`table`, `text`, `json`) и сохранением в файл.
- **Гибкое извлечение данных:**
  - CSS-селекторы для контейнера элемента и отдельных полей;
  - псевдоселекторы `::text` и `::attr(name)`;
  - автоматическое извлечение содержимого статьи (заголовок, описание, подзаголовки, текст через `trafilatura`), если селекторы не заданы или ничего не нашли.
- **Пресеты** селекторов в `config.yaml` — из коробки есть `books_to_scrape`, `quotes_to_scrape`, `hacker_news` и `custom`.
- **Экспорт:** `CSV`, `XLSX`, `SQLite`, `JSON`, `MD`, `TXT`.
- **Устойчивость:** таймауты, обработка сетевых ошибок и HTTP-статусов, ограничение параллелизма, задержка между запросами, ротация User-Agent, нормализация URL (добавляет `https://`, если схема не указана).
- **Пакетная обработка:** список URL можно передать файлом (по одному на строку; строки, начинающиеся с `#`, пропускаются).

## Требования

- Python **3.10+**
- Git — для клонирования репозитория.
- Для браузерного режима — Chromium, устанавливаемый через Playwright.

## Установка

```bash
git clone https://github.com/<username>/<repo>.git
cd <repo>

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

> В Windows виртуальное окружение активируется командой `.venv\Scripts\activate`.

Опционально — браузер для режима `playwright`:

```bash
playwright install chromium
# если не хватает системных библиотек:
# playwright install-deps chromium
```

## Запуск

### TUI (по умолчанию)

```bash
python main.py
```

Откроется полноэкранный интерфейс:

1. Укажите **URL** или путь к файлу со ссылками.
2. Выберите **режим** (`HTTPX` или `Playwright`) и **пресет** — поля селекторов заполнятся автоматически.
3. При необходимости отредактируйте CSS-селектор контейнера и список полей.
4. Настройте число воркеров, задержку и ротацию User-Agent.
5. Нажмите **▶ Старт**. Результаты появятся во вкладках «Таблица», «Текст / Карточки» и «Логи процесса».
6. Кнопками внизу сохраните данные в нужный формат.

### CLI

CLI-режим включается, если передан `--url`. Без `--url` запускается TUI. Подкоманд нет — все параметры передаются флагами:

```bash
python main.py --help
```

| Опция | По умолчанию | Описание |
|---|---|---|
| `--url`, `-u` | — | URL или путь к файлу со списком URL |
| `--preset`, `-p` | — | Имя пресета из `config.yaml` |
| `--mode`, `-m` | `httpx` | Движок: `httpx` или `playwright` |
| `--format`, `-f` | `table` | Вывод в терминал: `table`, `text`, `json` |
| `--export`, `-e` | — | Сохранить в файл: `csv`, `xlsx`, `sqlite`, `txt`, `md`, `json` |
| `--workers`, `-w` | `3` | Число параллельных воркеров (1–20) |
| `--delay`, `-d` | `0.5` | Задержка между запросами в секундах |
| `--item-sel` | — | CSS-селектор контейнера элемента |
| `--fields` | — | Поля в формате `name=селектор; name2=селектор2` |

> `--export` принимает **один** формат за запуск. Для сохранения сразу в несколько форматов используйте TUI или запустите команду несколько раз.

#### Примеры

Парсинг с готовым пресетом:

```bash
python main.py -u "https://books.toscrape.com/" -p books_to_scrape
```

Сохранение в Excel:

```bash
python main.py -u "https://quotes.toscrape.com/" -p quotes_to_scrape -e xlsx
```

Пакетная обработка списка URL из файла:

```bash
python main.py -u urls.txt -p hacker_news -m httpx -w 5 -d 0.3 -f json
```

Свои селекторы без пресета:

```bash
python main.py -u "https://news.ycombinator.com/" \
  --item-sel "tr.athing" \
  --fields "title=span.titleline > a::text; link=span.titleline > a::attr(href)" \
  -f table -e csv
```

Динамический сайт через браузер:

```bash
python main.py -u "https://example.com/" -m playwright \
  --item-sel "div.card" \
  --fields "name=h3::text; url=a::attr(href)" \
  -f json -e json
```

## Селекторы

Селектор контейнера (`item_selector`) задаёт повторяющийся блок страницы (карточка товара, строка таблицы, пост). Селекторы полей ищутся **внутри** этого блока.

Поддерживаемые правила для полей:

| Правило | Что извлекает |
|---|---|
| `h3 a` | Текст элемента (по умолчанию) |
| `h3 a::text` | Текст элемента (явно) |
| `a::attr(href)` | Значение атрибута `href` |
| `p.star-rating::attr(class)` | Значение атрибута `class` |

- Поля задаются строкой `title=...; price=...` в CLI/TUI или словарём `fields` в `config.yaml`.
- Если `item_selector` пуст, поля извлекаются со всей страницы (одна запись).
- Если ничего не найдено или селекторы не заданы, срабатывает автоизвлечение статьи: `title`, `description`, `headings`, `content`. Текст очищается от навигации, рекламы, футера и других шумовых блоков; основной контент извлекается через `trafilatura` с fallback на очищенный текст `<main>`/`<body>`.

## Пресеты и config.yaml

```yaml
presets:
  books_to_scrape:
    name: "Books to Scrape"
    description: "Каталог книг (books.toscrape.com)"
    item_selector: "article.product_pod"
    fields:
      title: "h3 a::attr(title)"
      price: ".price_color::text"
      availability: ".availability::text"
      rating: "p.star-rating::attr(class)"
      link: "h3 a::attr(href)"
```

Чтобы добавить свой пресет, допишите секцию в `presets` — он появится в списке TUI и станет доступен через `--preset`.

> Секция `defaults` в `config.yaml` пока не применяется при запуске: параметры задаются флагами CLI или в TUI.

## Экспорт

Все файлы сохраняются в `output/` с именем вида `scrape_20261124_153000.<ext>`.

| Формат | Расширение | Особенности |
|---|---|---|
| `csv` | `.csv` | Кодировка `utf-8-sig`, колонки `url`, поля, `error` |
| `xlsx` | `.xlsx` | Лист `Results` |
| `sqlite` | `.db` | Таблица `scraped_data` |
| `json` | `.json` | Массив объектов `{url, data, error}` |
| `md` | `.md` | Markdown-карточки записей |
| `txt` | `.txt` | Текстовые карточки записей |

Ошибки по конкретному URL не прерывают весь запуск: запись сохраняется с заполненным полем `error`.

## Структура проекта

```
.
├── config.yaml             # Пресеты селекторов
├── main.py                 # Точка входа: TUI по умолчанию + CLI (Typer)
├── tui.py                  # Интерфейс Textual
├── formatter.py            # Таблица Rich, карточки, Markdown, JSON
├── storage.py              # Экспорт в CSV/XLSX/SQLite/JSON/MD/TXT
├── requirements.txt        # Зависимости
├── output/                 # Сохранённые результаты
└── engine/
    ├── __init__.py         # Публичный API пакета
    ├── models.py           # Pydantic-модели и enum'ы
    ├── http_scraper.py     # Асинхронный HTTP-скрапер (httpx)
    ├── browser_scraper.py  # Скрапер на Playwright
    ├── extractor.py        # CSS-извлечение и автоизвлечение статьи
    └── utils.py            # Заголовки браузера, нормализация URL
```

## Как это работает

1. URL (или файл со списком) попадает в очередь.
2. `HttpScraper` или `BrowserScraper` обрабатывает очередь с ограничением параллелизма (`workers`) и задержкой (`delay`).
3. HTML передаётся в `DataExtractor`, который извлекает поля по CSS-селекторам либо запускает автоизвлечение статьи.
4. Каждый результат — `ScrapedItem(url, data, error)`; ошибки перехватываются на уровне URL.
5. `ResultFormatter` выводит данные в терминал, `ResultStorage` сохраняет их в выбранный формат.

## Ограничения

- Поддерживаются только **CSS-селекторы** (Lexbor); XPath, `BeautifulSoup` и `lxml` не используются.
- Нет автоматического обхода пагинации и перехода по ссылкам — передавайте готовый список URL.
- Нет встроенной поддержки прокси и обхода CAPTCHA.
- В режиме `httpx` отключена проверка TLS-сертификата (`verify=False`).
- В режиме `playwright` после `domcontentloaded` фиксированно ждётся 0.5 с; для «медленных» SPA этого может не хватить.

## Дисклеймер

Используйте парсер с учётом `robots.txt`, правил сайта и законодательства. Не создавайте чрезмерную нагрузку на чужие серверы: увеличивайте `--delay` и уменьшайте `--workers`.
