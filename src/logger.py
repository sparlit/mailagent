import logging
import json
from logging.handlers import RotatingFileHandler
import sys
import os
from . import config

__all__ = ['setup_logging']

class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

def setup_logging(log_file='mailagent.log'):
    """
    Configure global logging settings, including console and file handlers.

    Parameters:
        log_file (str): The filename for the rotating log file.
    """
    logger = logging.getLogger()

    # Use log level from config
    try:
        level = getattr(logging, config.LOG_LEVEL)
    except AttributeError:
        level = logging.INFO
    logger.setLevel(level)

    use_json = os.getenv('LOG_FORMAT', 'text').lower() == 'json'

    if use_json:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating File handler
    file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
