import os
from pathlib import Path
import fnmatch


def get_project_structure(root_dir, ignore_patterns=None):
    """Собирает структуру проекта и содержимое .py файлов, игнорируя указанные шаблоны."""
    root_path = Path(root_dir)
    ignore_patterns = ignore_patterns or []

    def is_ignored(file_path):
        """Проверяет, соответствует ли путь одному из шаблонов игнорирования."""
        relative_path = str(file_path.relative_to(root_path))
        return any(fnmatch.fnmatch(relative_path, pattern) for pattern in ignore_patterns)

    # Собираем содержимое всех .py файлов
    code_output = []
    for file_path in root_path.rglob("*.py"):
        if is_ignored(file_path):
            continue
        relative_path = file_path.relative_to(root_path)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            code_output.append(f"[{relative_path}]\n```python\n{content}\n```")
        except Exception as e:
            code_output.append(f"[{relative_path}]\n```python\nОшибка чтения файла: {str(e)}\n```")

    # Собираем структуру директорий
    tree_output = ["Проект:"]

    def build_tree(path, prefix=""):
        items = sorted(path.iterdir())
        filtered_items = []
        for item in items:
            if item.is_file() and item.suffix == '.py' and not is_ignored(item):
                filtered_items.append(item)
            elif item.is_dir() and not is_ignored(item):
                filtered_items.append(item)

        for i, item in enumerate(filtered_items):
            is_last = i == len(filtered_items) - 1
            if item.is_dir():
                tree_output.append(f"{prefix}{'└── ' if is_last else '├── '}{item.name}/")
                build_tree(item, prefix + ("    " if is_last else "│   "))
            elif item.suffix == '.py':
                tree_output.append(f"{prefix}{'└── ' if is_last else '├── '}{item.name}")

    build_tree(root_path)

    return "\n\n".join(code_output), "\n".join(tree_output)


def main():
    # Текущая директория как корень проекта
    root_dir = os.getcwd() + '/eye_tracker'

    # Список шаблонов для игнорирования
    ignore_patterns = [
        "*.pyc",
        "*pycache*",
        "__init__.py"
        # "*test*",
        # "*tracker*",
        # "*dist*",
        # "*.git*",

        # Добавьте свои шаблоны здесь
    ]

    try:
        code_content, tree_structure = get_project_structure(root_dir, ignore_patterns)

        # Выводим результаты
        print("=== Структура проекта ===\n")
        print(tree_structure)
        print("\n=== Содержимое файлов ===\n")
        print(code_content)

    except Exception as e:
        print(f"Ошибка: {str(e)}")


if __name__ == "__main__":
    main()