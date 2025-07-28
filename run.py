# run.py (ФИНАЛЬНАЯ ВЕРСИЯ)
import sys
from pathlib import Path

# 1. Находим абсолютный путь к папке `src`
SRC_DIR = Path(__file__).resolve().parent / 'src'

# 2. Добавляем папку `src` в самое начало системных путей Python.
sys.path.insert(0, str(SRC_DIR))

# Теперь, когда путь настроен, мы можем импортировать `main` напрямую.
from main import main

if __name__ == "__main__":
    # Вызываем главную функцию, которая запустит все наше приложение.
    main()