#!/usr/bin/env python3
"""
===============================================================================
Module      : config_loader.py
Description : Configuration Loader
Version     : 1.0
===============================================================================
"""

import json
from pathlib import Path

from utils import Utils


class ConfigLoader:
    """
    Loads and validates JSON configuration.
    """

    REQUIRED_SECTIONS = [
        "application",
        "smpp",
        "paths",
        "processing",
        "validation",
        "logging",
        "delivery_report"
    ]

    def __init__(self, config_file: str):

        self.config_file = config_file

        self.config = None

    # =========================================================================
    # Load Configuration
    # =========================================================================

    def load(self):

        config_path = Path(self.config_file)

        if not config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}"
            )

        with open(config_path, "r", encoding="utf-8") as fp:

            self.config = json.load(fp)

        self._validate()

        Utils.ensure_directories(self.config)

        return self.config

    # =========================================================================
    # Validate Configuration
    # =========================================================================

    def _validate(self):

        for section in self.REQUIRED_SECTIONS:

            if section not in self.config:

                raise ValueError(
                    f"Missing configuration section: {section}"
                )

        self._validate_application()

        self._validate_smpp()

        self._validate_paths()

        self._validate_processing()

        self._validate_validation()

        self._validate_logging()

        self._validate_delivery_report()

    # =========================================================================
    # Application
    # =========================================================================

    def _validate_application(self):

        required = [
            "name",
            "version",
            "environment"
        ]

        self._check_required(
            self.config["application"],
            required,
            "application"
        )

    # =========================================================================
    # SMPP
    # =========================================================================

    def _validate_smpp(self):

        smpp = self.config["smpp"]

        required = [

            "host",

            "port",

            "system_id",

            "password",

            "bind_type",

            "source_addr",

            "addr_ton",

            "addr_npi",

            "dest_ton",

            "dest_npi",

            "data_coding",

            "registered_delivery",

            "connection_timeout",

            "socket_timeout",

            "enquire_link_interval",

            "reconnect_interval"

        ]

        self._check_required(
            smpp,
            required,
            "smpp"
        )

        if not (1 <= int(smpp["port"]) <= 65535):

            raise ValueError("Invalid SMPP port.")

    # =========================================================================
    # Paths
    # =========================================================================

    def _validate_paths(self):

        required = [

            "input_directory",

            "archive_directory",

            "failed_directory",

            "delivery_report_directory",

            "log_directory",

            "log_file"

        ]

        self._check_required(

            self.config["paths"],

            required,

            "paths"

        )

    # =========================================================================
    # Processing
    # =========================================================================

    def _validate_processing(self):

        processing = self.config["processing"]

        required = [

            "batch_size",

            "rate_limit_per_second",

            "max_retry",

            "retry_interval_seconds"

        ]

        self._check_required(

            processing,

            required,

            "processing"

        )

    # =========================================================================
    # Validation
    # =========================================================================

    def _validate_validation(self):

        validation = self.config["validation"]

        required = [

            "expected_header",

            "min_msisdn_length",

            "max_msisdn_length",

            "max_message_length"

        ]

        self._check_required(

            validation,

            required,

            "validation"

        )

    # =========================================================================
    # Logging
    # =========================================================================

    def _validate_logging(self):

        logging_cfg = self.config["logging"]

        required = [

            "level",

            "console",

            "file"

        ]

        self._check_required(

            logging_cfg,

            required,

            "logging"

        )

    # =========================================================================
    # Delivery Report
    # =========================================================================

    def _validate_delivery_report(self):

        dlr = self.config["delivery_report"]

        required = [

            "enabled",

            "output_file_prefix",

            "delimiter"

        ]

        self._check_required(

            dlr,

            required,

            "delivery_report"

        )

    # =========================================================================
    # Helper
    # =========================================================================

    @staticmethod
    def _check_required(section, required_fields, section_name):

        for field in required_fields:

            if field not in section:

                raise ValueError(
                    f"Missing '{field}' in section '{section_name}'"
                )

    # =========================================================================
    # Getter
    # =========================================================================

    def get(self):

        if self.config is None:

            return self.load()

        return self.config