"""
Centralized logging configuration for the Life Tracker application.
Logs are written to 'app.log' with automatic file rotation (max 2 MB, 3 backups)
and mirrored to the standard output console.
"""

import logging
from logging.handlers import RotatingFileHandler
import os

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")

# Ensure logs directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Define custom log format
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d - %(funcName)s()]: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Configure root logger
logger = logging.getLogger("LifeTracker")
logger.setLevel(logging.DEBUG)

# 1. Rotating File Handler (Max 2MB per file, keeps 3 backups)
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=2 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8"
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

# 2. Console Stream Handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

# Avoid duplicate handlers if imported multiple times
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)