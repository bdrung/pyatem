# Copyright 2021 - 2022, Martijn Braam and the OpenAtem contributors
# SPDX-License-Identifier: GPL-3.0-only

import logging

class AtemLogFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    white = "\x1b[97;20m"
    blue = "\x1b[36;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = '[%(levelname)-8s %(threadName)-12s] %(name)-14s - %(message)s'

    FORMATS = {
        logging.DEBUG: blue + format + reset,
        logging.INFO: white + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def setup_logging(level: int | None) -> None:
    """Setup logging."""
    ch = logging.StreamHandler()
    ch.setFormatter(AtemLogFormatter())
    logging.basicConfig(level=level, handlers=[ch])
