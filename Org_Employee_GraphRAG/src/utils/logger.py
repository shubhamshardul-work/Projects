"""
Logger utility — rich console + file logging.
"""
import logging
import sys
from rich.logging import RichHandler


def get_logger(name: str = "graphrag", level: int = logging.INFO) -> logging.Logger:
    """Return a configured logger with rich console output."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Rich console handler
    console = RichHandler(
        show_time=True,
        show_path=False,
        markup=True,
        rich_tracebacks=True,
    )
    console.setLevel(level)
    fmt = logging.Formatter("%(message)s", datefmt="[%X]")
    console.setFormatter(fmt)
    logger.addHandler(console)

    return logger


log = get_logger()
