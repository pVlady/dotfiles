"""
convert_wikilinks.py
Конвертирует Obsidian wikilinks в стандартный Markdown для Hugo.

Поддерживаемые форматы:
  [[Заметка]]              → [Заметка]({{< ref "заметка" >}})
  [[Заметка|Текст]]        → [Текст]({{< ref "заметка" >}})
  ![[image.png]]           → ![image.png](image.png)
  ![[Заметка]]             → {{< include "заметка" >}}  (embed)

Использование:
  python convert_wikilinks.py               # конвертирует content/ на месте
  python convert_wikilinks.py --dry-run     # только показывает что изменится
  python convert_wikilinks.py --src content --out content_converted  # в отдельную папку
"""

import re
import sys
import shutil
import argparse
from pathlib import Path

# ─── Настройки ────────────────────────────────────────────────────────────────

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp"}

# ─── Конвертеры ───────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    """Превращает имя файла/заметки в Hugo-совместимый slug."""
    # Убираем расширение если есть
    stem = Path(name).stem if "." in name else name
    # Hugo ref чувствителен к регистру, оставляем как есть
    # но заменяем пробелы на дефисы
    return stem.replace(" ", "-").lower()


def convert_image_embed(filename: str) -> str:
    """![[image.png]] → ![image.png](/images/image.png)"""
    return f"![{filename}](/images/{filename})"


def convert_note_embed(note_name: str) -> str:
    """![[Заметка]] → shortcode include (Hugo не поддерживает embeds нативно)"""
    slug = slugify(note_name)
    # Оставляем как комментарий — embed заметок Hugo не поддерживает
    return f'{{{{/* embed: [{note_name}]({{{{< ref "{slug}" >}}}}) */}}}}'


def convert_wikilink(note_name: str, alias: str | None) -> str:
    """[[Заметка]] или [[Заметка|Текст]] → [Текст]({{< ref "slug" >}})"""
    slug = slugify(note_name)
    display = alias if alias else note_name
    return f'[{display}]({{{{< ref "{slug}" >}}}})'


def process_line(line: str) -> str:
    """Обрабатывает одну строку, конвертируя все wikilinks."""

    # 1. ![[image.png]] — изображения (сначала, до обработки обычных embeds)
    def replace_image_embed(m):
        filename = m.group(1).strip()
        ext = Path(filename).suffix.lower()
        if ext in IMAGE_EXTENSIONS:
            return convert_image_embed(filename)
        else:
            # Это embed заметки, не картинки
            return convert_note_embed(filename)

    line = re.sub(r'!\[\[([^\]]+)\]\]', replace_image_embed, line)

    # 2. [[Заметка|Алиас]] — с алиасом
    def replace_aliased(m):
        note_name = m.group(1).strip()
        alias = m.group(2).strip()
        return convert_wikilink(note_name, alias)

    line = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', replace_aliased, line)

    # 3. [[Заметка]] — простая ссылка
    def replace_simple(m):
        note_name = m.group(1).strip()
        return convert_wikilink(note_name, None)

    line = re.sub(r'\[\[([^\]|]+)\]\]', replace_simple, line)

    return line


def process_file(src: Path, dst: Path, dry_run: bool = False) -> int:
    """Обрабатывает один .md файл. Возвращает количество замен."""
    text = src.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    new_lines = []
    changes = 0
    in_code_block = False

    for line in lines:
        # Не трогаем содержимое code blocks
        if line.strip().startswith("```"):
            in_code_block = not in_code_block

        if in_code_block:
            new_lines.append(line)
            continue

        new_line = process_line(line)
        if new_line != line:
            changes += 1
        new_lines.append(new_line)

    if changes > 0:
        new_text = "".join(new_lines)
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(new_text, encoding="utf-8")
        print(f"  {'[dry]' if dry_run else '[ok] '} {src}  ({changes} замен)")

    return changes


# ─── Главная логика ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Конвертер Obsidian wikilinks → Hugo Markdown")
    parser.add_argument("--src", default="content", help="Исходная папка (по умолчанию: content)")
    parser.add_argument("--out", default=None, help="Папка назначения (по умолчанию: src, конвертация на месте)")
    parser.add_argument("--dry-run", action="store_true", help="Только показать изменения, не писать файлы")
    args = parser.parse_args()

    src_root = Path(args.src)
    out_root = Path(args.out) if args.out else src_root
    in_place = (src_root == out_root)

    if not src_root.exists():
        print(f"Ошибка: папка '{src_root}' не найдена.")
        sys.exit(1)

    md_files = list(src_root.rglob("*.md"))
    if not md_files:
        print(f"Markdown-файлы в '{src_root}' не найдены.")
        sys.exit(0)

    print(f"Источник:    {src_root.resolve()}")
    print(f"Назначение:  {'(на месте)' if in_place else out_root.resolve()}")
    print(f"Режим:       {'dry-run' if args.dry_run else 'запись'}")
    print(f"Файлов:      {len(md_files)}")
    print()

    total_changes = 0
    total_files = 0

    for src_file in sorted(md_files):
        rel = src_file.relative_to(src_root)
        dst_file = out_root / rel

        changes = process_file(src_file, dst_file, dry_run=args.dry_run)
        if changes:
            total_files += 1
            total_changes += changes

    print()
    print(f"Готово: {total_files} файлов изменено, {total_changes} замен.")

    if args.dry_run:
        print("Это dry-run — файлы не изменены. Запустите без --dry-run для применения.")


if __name__ == "__main__":
    main()
