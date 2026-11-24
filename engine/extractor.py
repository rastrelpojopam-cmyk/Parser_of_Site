import re
from typing import Any, Dict, List, Optional
from selectolax.lexbor import LexborHTMLParser, LexborNode

try:
    import trafilatura
except Exception:  # pragma: no cover - трафилатура опциональна
    trafilatura = None


class DataExtractor:
    """
    Извлекатель данных из HTML на базе Lexbor (selectolax).
    Поддерживает псевдо-селекторы:
      - 'selector::text' -> извлекает текстовое содержимое
      - 'selector::attr(name)' -> извлекает значение атрибута name
      - 'selector' (по умолчанию) -> извлекает очищенный текст
    """

    ATTR_PATTERN = re.compile(r"::attr\(([\w\-]+)\)$")

    NOISE_TAGS = {
        "script", "style", "noscript", "nav", "header", "footer",
        "aside", "form", "button", "svg", "iframe", "select", "option",
        "template", "input", "textarea",
    }
    NOISE_HINTS = (
        "menu", "nav", "footer", "header", "sidebar", "comment",
        "advert", "cookie", "breadcrumb", "pagination", "share",
        "social", "related", "recommend", "subscribe", "banner",
    )

    @classmethod
    def extract_field(cls, node: LexborNode, selector_rule: str) -> Optional[str]:
        selector_rule = selector_rule.strip()
        attr_name = None

        match = cls.ATTR_PATTERN.search(selector_rule)
        if match:
            attr_name = match.group(1)
            css_selector = selector_rule[: match.start()].strip()
        elif selector_rule.endswith("::text"):
            css_selector = selector_rule[:-6].strip()
        else:
            css_selector = selector_rule

        target_node = node
        if css_selector:
            target_node = node.css_first(css_selector)

        if not target_node:
            return None

        if attr_name:
            val = target_node.attributes.get(attr_name)
            return val.strip() if val else None

        text = target_node.text(deep=True, separator=" ")
        return cls._clean_text(text) if text else ""

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip() if text else ""

    @staticmethod
    def _clean_content(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()

    @classmethod
    def extract_all(
        cls,
        html: str,
        item_selector: str,
        fields: Dict[str, str],
        source_url: str = "",
    ) -> List[Dict[str, Any]]:
        tree = LexborHTMLParser(html)
        results: List[Dict[str, Any]] = []

        if item_selector and item_selector.strip():
            items = tree.css(item_selector.strip())
            for item_node in items:
                row: Dict[str, Any] = {}
                for field_name, rule in fields.items():
                    val = cls.extract_field(item_node, rule)
                    row[field_name] = val
                if row:
                    results.append(row)
        else:
            row: Dict[str, Any] = {}
            body_node = tree.body or tree.root
            if body_node:
                for field_name, rule in fields.items():
                    val = cls.extract_field(body_node, rule)
                    row[field_name] = val
            if row:
                results.append(row)

        if not results:
            results.append(cls.extract_article(html))

        return results

    @classmethod
    def extract_article(cls, html: str) -> Dict[str, Any]:
        tree = LexborHTMLParser(html)

        title = cls._extract_title(tree)
        description = cls._extract_description(tree)
        headings = cls._extract_headings(tree)
        content = cls._extract_article_text(html, tree)

        return {
            "title": title,
            "description": description,
            "headings": headings,
            "content": content,
        }

    @classmethod
    def _extract_article_text(cls, html: str, tree: LexborHTMLParser) -> str:
        content = ""

        if trafilatura is not None:
            try:
                extracted = trafilatura.extract(
                    html,
                    include_comments=False,
                    include_tables=False,
                    favor_precision=True,
                )
                content = cls._clean_content(extracted or "")
            except Exception:
                content = ""

        if len(content) < 200:
            content = cls._extract_generic_text(tree)

        return content

    @classmethod
    def _extract_title(cls, tree: LexborHTMLParser) -> str:
        h1 = tree.css_first("h1")
        if h1:
            text = cls._clean_text(h1.text(deep=True))
            if text:
                return text

        title_node = tree.css_first("title")
        if title_node:
            text = cls._clean_text(title_node.text())
            if text:
                return text

        og_title = tree.css_first('meta[property="og:title"]')
        if og_title and og_title.attributes.get("content"):
            return og_title.attributes["content"].strip()

        return ""

    @classmethod
    def _extract_description(cls, tree: LexborHTMLParser) -> str:
        for selector in (
            'meta[name="description"]',
            'meta[property="og:description"]',
            'meta[name="twitter:description"]',
        ):
            node = tree.css_first(selector)
            if node and node.attributes.get("content"):
                return node.attributes["content"].strip()
        return ""

    @classmethod
    def _extract_headings(cls, tree: LexborHTMLParser) -> str:
        headings = []
        for node in tree.css("h2, h3"):
            text = cls._clean_text(node.text(deep=True))
            if text and text not in headings:
                headings.append(text)
        return " | ".join(headings)

    @classmethod
    def _extract_generic_text(cls, tree: LexborHTMLParser) -> str:
        body = tree.body or tree.root
        if body is None:
            return ""

        cls._strip_noise(body)

        container = body.css_first("main") or body
        return cls._clean_content(container.text(deep=True, separator="\n"))

    @classmethod
    def _strip_noise(cls, body: LexborNode) -> None:
        for tag in cls.NOISE_TAGS:
            for node in body.css(tag):
                node.decompose()

        for node in body.css("[class], [id]"):
            attr = " ".join(
                filter(
                    None,
                    [
                        (node.attributes or {}).get("class", ""),
                        (node.attributes or {}).get("id", ""),
                    ],
                )
            ).lower()
            if attr and any(hint in attr for hint in cls.NOISE_HINTS):
                node.decompose()
