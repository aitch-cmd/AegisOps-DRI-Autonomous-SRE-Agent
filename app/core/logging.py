import logging
import os

os.makedirs("logs", exist_ok=True)

def get_logger(name: str):
    """
    Creates and configures a reusable logger with file + console handlers.
    Logs stored in logs/<name>.log
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Prevent multiple handlers (duplicate logs)
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # File handler: all logs including debug
    file_handler = logging.FileHandler(f"logs/{name}.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console handler: only important logs
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Avoid double logging
    logger.propagate = False

    return logger