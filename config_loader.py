#!/usr/bin/env python3
"""
===============================================================================
Module      : config_loader.py
Description : Configuration Loader
Version     : 1.1
===============================================================================
"""

import json
from pathlib import Path

from utils import Utils


class ConfigLoader:
    """
    Loads and validates the application configuration.
    """

    REQUIRED_SECTIONS = [
        "application",
        "input",
        "smpp",
        "paths",
        "processing",
        "delivery_report"
    ]

    def __init__(self, config_file: str):
        self.config_file = config_file
        self.config = None

    # =========================================================================
    # Load
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
    # Validate
    # =========================================================================

    def _validate(self):

        for section in self.REQUIRED_SECTIONS:

            if section not in self.config:
                raise ValueError(
                    f"Missing configuration section: {section}"
                )

        self._validate_application()
        self._validate_input()
        self._validate_smpp()
        self._validate_paths()
        self._validate_processing()
        self._validate_delivery_report()

    # =========================================================================
    # Application
    # =========================================================================

    def _validate_application(self):

        self._check_required(
            self.config["application"],
            [
                "name",
                "version",
                "environment"
            ],
            "application"
        )

    # =========================================================================
    # Input
    # =========================================================================

    def _validate_input(self):

        self._check_required(
            self.config["input"],
            [
                "delimiter",
                "has_header",
                "encoding"
            ],
            "input"
        )

    # =========================================================================
    # SMPP
    # =========================================================================

    def _validate_smpp(self):

        smpp = self.config["smpp"]

        self._check_required(
            smpp,
            [
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
            ],
            "smpp"
        )

        if smpp["bind_type"] not in (
            "transmitter",
            "receiver",
            "transceiver"
        ):
            raise ValueError(
                "bind_type must be transmitter, receiver or transceiver."
            )

        port = int(smpp["port"])

        if port < 1 or port > 65535:
            raise ValueError("Invalid SMPP port.")

    # =========================================================================
    # Paths
    # =========================================================================

    def _validate_paths(self):

        self._check_required(
            self.config["paths"],
            [
                "input_directory",
                "archive_directory",
                "failed_directory",
                "delivery_report_directory",
                "invalid_record_file",
                "message_mapping_file",
                "log_directory"
            ],
            "paths"
        )

    # =========================================================================
    # Processing
    # =========================================================================

    def _validate_processing(self):

        self._check_required(
            self.config["processing"],
            [
                "rate_limit_per_second",
                "max_retry",
                "retry_interval_seconds",
                "min_msisdn_length",
                "max_msisdn_length"
            ],
            "processing"
        )

    # =========================================================================
    # Delivery Report
    # =========================================================================

    def _validate_delivery_report(self):

        self._check_required(
            self.config["delivery_report"],
            [
                "enabled",
                "wait_timeout_seconds",
                "delimiter",
                "output_file_prefix"
            ],
            "delivery_report"
        )

    # =========================================================================
    # Helper
    # =========================================================================

    @staticmethod
    def _check_required(section, fields, section_name):

        for field in fields:

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
