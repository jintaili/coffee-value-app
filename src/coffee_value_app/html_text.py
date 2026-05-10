from __future__ import annotations

from bs4 import BeautifulSoup


MAX_TEXT_CHARS = 120_000


def html_to_text(html: str, *, max_chars: int = MAX_TEXT_CHARS) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "canvas"]):
        tag.decompose()

    lines: list[str] = []
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if title:
        lines.append(f"Title: {title}")

    description = soup.find("meta", attrs={"name": "description"})
    if description and description.get("content"):
        lines.append(f"Description: {description['content'].strip()}")

    for selector in ["main", "[role=main]", "article", "body"]:
        node = soup.select_one(selector)
        if node is not None:
            text = node.get_text("\n", strip=True)
            if text:
                lines.append(text)
                break

    text = "\n".join(dedupe_lines(lines))
    return text[:max_chars]


def dedupe_lines(lines: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for block in lines:
        for line in block.splitlines():
            cleaned = " ".join(line.split())
            if not cleaned or cleaned in seen:
                continue
            output.append(cleaned)
            seen.add(cleaned)
    return output

