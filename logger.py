#!/usr/bin/env python3
"""
===============================================================================
Module      : logger.py
Description : Centralized Logging Utility
Version     : 1.1
===============================================================================
"""

import os
import logging
from logging.handlers import RotatingFileHandler


class Logger:

    _logger = None

    @staticmethod
    def get_logger(config):

        if Logger._logger is not None:
            return Logger._logger

        #
        # Read configuration safely
        #

        log_cfg = config.get("logging", {})
        path_cfg = config.get("paths", {})

        log_directory = path_cfg.get(
            "log_directory",
            "./logs"
        )

        log_file = path_cfg.get(
            "log_file",
            "sms_sender.log"
        )

        os.makedirs(
            log_directory,
            exist_ok=True
        )

        log_path = os.path.join(
            log_directory,
            log_file
        )

        logger = logging.getLogger("SMS_SENDER")
        logger.propagate = False

        if logger.hasHandlers():
            logger.handlers.clear()

        level = log_cfg.get(
            "level",
            "INFO"
        ).upper()

        logger.setLevel(
            getattr(
                logging,
                level,
                logging.INFO
            )
        )

        formatter = logging.Formatter(
            fmt=(
                "%(asctime)s | "
                "%(levelname)-8s | "
                "%(threadName)-15s | "
                "%(filename)s:%(lineno)d | "
                "%(message)s"
            ),
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        #
        # File logging
        #

        if log_cfg.get("file", True):

            rotation = log_cfg.get(
                "rotation",
                {}
            )

            max_size = (
                rotation.get(
                    "max_file_size_mb",
                    50
                ) * 1024 * 1024
            )

            backup_count = rotation.get(
                "backup_count",
                10
            )

            file_handler = RotatingFileHandler(
                filename=log_path,
                maxBytes=max_size,
                backupCount=backup_count,
                encoding="utf-8"
            )

            file_handler.setFormatter(formatter)

            logger.addHandler(file_handler)

        #
        # Console logging
        #

        if log_cfg.get("console", True):

            console_handler = logging.StreamHandler()

            console_handler.setFormatter(formatter)

            logger.addHandler(console_handler)

        Logger._logger = logger

        logger.info("=" * 80)
        logger.info("Logger Initialized")
        logger.info("Log File : %s", log_path)
        logger.info("Log Level: %s", level)
        logger.info("=" * 80)

        return logger

    @staticmethod
    def shutdown():

        if Logger._logger:

            handlers = Logger._logger.handlers[:]

            for handler in handlers:

                try:
                    handler.flush()
                    handler.close()
                finally:
                    Logger._logger.removeHandler(handler)

            logging.shutdown()

            Logger._logger = None
