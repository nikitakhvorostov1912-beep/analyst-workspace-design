"""Файловый логгер с ротацией.

На машине пользователя backend.exe запускается из Electron, его stdout/stderr
уходят в никуда. Если что-то ломается, коллеги не могут прислать ничего кроме
скриншота. Этот модуль настраивает запись логов в файл, чтобы:

  1) коллега мог открыть папку с логами и прислать файл;
  2) /diagnostics/log-path возвращал путь, чтобы UI кидал на «Открыть логи»;
  3) ротация по дням не давала логам расти бесконечно (7 файлов = неделя).

Расположение:
  - Windows: %LOCALAPPDATA%\\analyst-desktop\\logs\\backend.log
  - Other OS: ~/.local/share/analyst-desktop/logs/backend.log
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path


def _default_log_dir() -> Path:
    """Подбирает каталог для логов по платформе.

    Совпадает с тем, куда Electron пишет userData, чтобы один и тот же путь
    был понятен и коллеге, и саппорту.
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "analyst-desktop" / "logs"
    # *nix / fallback
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "analyst-desktop" / "logs"
    return Path.home() / ".local" / "share" / "analyst-desktop" / "logs"


_LOG_DIR: Path | None = None


def get_log_dir() -> Path:
    """Возвращает каталог логов, не создавая его. Используется в API."""
    global _LOG_DIR
    if _LOG_DIR is None:
        env = os.environ.get("ANALYST_LOG_DIR")
        _LOG_DIR = Path(env) if env else _default_log_dir()
    return _LOG_DIR


def get_log_file_path() -> Path:
    """Путь к текущему файлу логов (используется ротация по суффиксам)."""
    return get_log_dir() / "backend.log"


def setup_file_logging() -> Path | None:
    """Подключает FileHandler с дневной ротацией к root-логгеру.

    Идемпотентна: повторный вызов не плодит хендлеры. Возвращает путь к файлу
    логов, либо None если включить не удалось (нет прав на каталог и т.п.).
    Падать backend из-за логов не должен.
    """
    log_dir = get_log_dir()
    log_path = log_dir / "backend.log"

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        # Молча — backend важнее логов
        logging.getLogger(__name__).warning(
            "Не удалось создать каталог логов %s: %s", log_dir, exc
        )
        return None

    root = logging.getLogger()
    # Идемпотентность: не вешать второй хендлер на тот же путь
    for handler in root.handlers:
        if isinstance(handler, logging.handlers.TimedRotatingFileHandler):
            if Path(handler.baseFilename) == log_path:
                return log_path

    try:
        handler = logging.handlers.TimedRotatingFileHandler(
            filename=str(log_path),
            when="midnight",
            backupCount=7,  # неделя истории — компромисс между диагностикой и размером
            encoding="utf-8",
            utc=False,
        )
    except OSError as exc:
        logging.getLogger(__name__).warning(
            "Не удалось открыть файл логов %s: %s", log_path, exc
        )
        return None

    handler.setFormatter(
        logging.Formatter(
            '{"time": "%(asctime)s", "level": "%(levelname)s", '
            '"name": "%(name)s", "message": "%(message)s"}'
        )
    )
    root.addHandler(handler)
    return log_path
