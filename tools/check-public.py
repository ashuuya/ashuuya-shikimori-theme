#!/usr/bin/env python3
"""Проверка публичного репозитория темы перед коммитом.

Что проверяется:
  * состав файлов: только разрешённые типы, без AGENTS.md и без посторонних артефактов;
  * разметка CSS: баланс скобок, отсутствие @charset и активных @import;
  * обязательные детали: экранированный селектор .de\\73 cription, отсутствие личных маркеров;
  * токены: нет строк вида authenticity_token, csrf, sessionid, длинных base64;
  * если установлен tinycss2 — дополнительный разбор CSS на ошибки.

Запуск: python3 tools/check-public.py
Код возврата: 0 — всё хорошо, 1 — есть проблемы.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "ashuuya-shikimori-theme.css"
README = ROOT / "README.md"

FORBIDDEN_EXT = {
    ".html", ".htm", ".png", ".jpg", ".jpeg", ".webp", ".gif",
    ".zip", ".7z", ".log", ".sqlite", ".sqlite3", ".db", ".pdf",
}
PERSONAL_MARKERS = [
    "[removed]", "[removed]", "[removed]", "[removed]", "[removed]",
]
SECRET_PATTERNS = [
    re.compile(r"authenticity_token", re.I),
    re.compile(r"csrf[-_]?token", re.I),
    re.compile(r"session_?id\s*[:=]", re.I),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"[A-Za-z0-9+/]{100,}={0,2}"),
]


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files"],
            check=True, capture_output=True, text=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return sorted(p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts)
    return [ROOT / line for line in out.splitlines() if line.strip()]


def check_files(problems: list[str]) -> None:
    for path in tracked_files():
        rel = path.relative_to(ROOT)
        if path.name == "AGENTS.md":
            problems.append(f"AGENTS.md попал в индекс: {rel}")
            continue
        if path.suffix.lower() in FORBIDDEN_EXT:
            problems.append(f"запрещённый тип файла: {rel}")


def check_text(problems: list[str]) -> None:
    itself = Path(__file__).resolve()
    # data-URI шрифтов и картинок в CSS — это ресурсы темы, не секреты
    data_uri = re.compile(r"data:(?:font|image)/[a-z0-9.+-]+;base64,[A-Za-z0-9+/=]+")
    for path in tracked_files():
        if path.resolve() == itself:
            continue  # в самом скрипте перечислены шаблоны секретов — это не утечка
        if path.suffix.lower() not in {".css", ".md", ".txt", ".json", ".yml", ".yaml", ".py"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            problems.append(f"не UTF-8: {path.relative_to(ROOT)}")
            continue
        text = data_uri.sub("<data-uri>", text)
        for pattern in SECRET_PATTERNS:
            match = pattern.search(text)
            if match:
                problems.append(
                    f"похоже на секрет в {path.relative_to(ROOT)}: «{match.group(0)[:24]}…»"
                )


def check_css(problems: list[str]) -> None:
    if not CSS.exists():
        problems.append("нет ashuuya-shikimori-theme.css")
        return
    text = CSS.read_text(encoding="utf-8")
    if text.count("{") != text.count("}"):
        problems.append(f"несбалансированные скобки: {text.count('{')} открывающих, {text.count('}')} закрывающих")
    if "@charset" in text:
        problems.append("в CSS есть @charset")
    if re.search(r"^\s*@import", text, re.M):
        problems.append("в CSS есть активный @import")
    if ".de\\73 cription" not in text:
        problems.append("потерян экранированный селектор .de\\73 cription")
    for marker in PERSONAL_MARKERS:
        if marker in text:
            problems.append(f"личный маркер в CSS: {marker}")
    try:
        import tinycss2  # noqa: F401
    except ImportError:
        return
    import tinycss2
    rules = tinycss2.parse_stylesheet(text, skip_comments=True, skip_whitespace=True)
    for node in rules:
        if node.type == "error":
            problems.append(
                f"ошибка разбора CSS: {node.message} (строка {node.source_line})"
            )
    if not rules:
        problems.append("CSS не разобран: пустой результат")


def check_readme(problems: list[str]) -> None:
    if not README.exists():
        problems.append("нет README.md")
        return
    text = README.read_text(encoding="utf-8")
    if "ashuuya-shikimori-theme.css" not in text:
        problems.append("README не ссылается на файл темы")
    if "@import" not in text:
        problems.append("README не содержит строки установки @import")


def main() -> int:
    problems: list[str] = []
    check_files(problems)
    check_text(problems)
    check_css(problems)
    check_readme(problems)
    if problems:
        print("проблемы:")
        for item in problems:
            print(f"  - {item}")
        return 1
    print("проверки пройдены")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
