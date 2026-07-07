#!/usr/bin/env python3
"""
===============================================================================
Module      : validator.py
Description : Input CSV Validator
Version     : 1.2
===============================================================================
"""

import csv
import math
import re
from pathlib import Path

from models import (
    SMSRecord,
    ValidationResult,
    InvalidRecord
)


class Validator:
    """
    Validates the input CSV file and converts valid rows
    into SMSRecord objects.
    """

    GSM7_REGEX = re.compile(r'^[\x00-\x7F]*$')

    def __init__(self, config, logger):

        self.config = config
        self.logger = logger

        input_cfg = config.get("input", {})
        paths = config["paths"]

        self.delimiter = input_cfg.get(
            "delimiter",
            ","
        )

        self.encoding = input_cfg.get(
            "encoding",
            "utf-8"
        )

        self.has_header = input_cfg.get(
            "has_header",
            True
        )

        self.invalid_record_file = paths[
            "invalid_record_file"
        ]

        self.min_msisdn_length = config["processing"].get(
            "min_msisdn_length",
            8
        )

        self.max_msisdn_length = config["processing"].get(
            "max_msisdn_length",
            15
        )

    # =====================================================================
    # Process File
    # =====================================================================

    def process(self, input_file):

        self.logger.info(
            "Processing input file: %s",
            input_file
        )

        self.logger.info(
            "Delimiter : '%s'",
            self.delimiter
        )

        result = ValidationResult()

        invalid_rows = []

        with open(
            input_file,
            "r",
            encoding=self.encoding,
            newline=""
        ) as fp:

            reader = csv.DictReader(
                fp,
                delimiter=self.delimiter
            )

            expected = [
                "MSISDN",
                "Message"
            ]

            if self.has_header:

                if reader.fieldnames != expected:

                    raise ValueError(
                        "Invalid header. Expected: "
                        + self.delimiter.join(expected)
                    )

            for line_number, row in enumerate(
                reader,
                start=2
            ):

                record, error = self._validate_row(row)

                if error:

                    invalid = InvalidRecord(
                        row_number=line_number,
                        msisdn=row.get("MSISDN", ""),
                        message=row.get("Message", ""),
                        reason=error
                    )

                    result.invalid_records.append(
                        invalid
                    )

                    result.invalid_count += 1

                    invalid_rows.append([
                        line_number,
                        row.get("MSISDN", ""),
                        row.get("Message", ""),
                        error
                    ])

                else:

                    record.row_number = line_number

                    result.valid_records.append(
                        record
                    )

                    result.valid_count += 1

        result.total_records = (
            result.valid_count +
            result.invalid_count
        )

        result.success = (
            result.valid_count > 0
        )

        if invalid_rows:

            self._write_invalid_records(
                invalid_rows
            )

        self.logger.info(
            "Validation complete. Valid=%d Invalid=%d",
            result.valid_count,
            result.invalid_count
        )

        return result
        # =====================================================================
    # Validate One Row
    # =====================================================================

    def _validate_row(self, row):

        msisdn = str(
            row.get("MSISDN", "")
        ).strip()

        message = str(
            row.get("Message", "")
        ).strip()

        # ---------------------------------------------------------------
        # MSISDN Validation
        # ---------------------------------------------------------------

        if not msisdn:
            return None, "MSISDN is empty"

        if not msisdn.isdigit():
            return None, "MSISDN must contain only digits"

        if len(msisdn) < self.min_msisdn_length:
            return None, (
                f"MSISDN must be at least "
                f"{self.min_msisdn_length} digits"
            )

        if len(msisdn) > self.max_msisdn_length:
            return None, (
                f"MSISDN must not exceed "
                f"{self.max_msisdn_length} digits"
            )

        # ---------------------------------------------------------------
        # Message Validation
        # ---------------------------------------------------------------

        if not message:
            return None, "Message is empty"

        encoding = self._detect_encoding(
            message
        )

        sms_parts = self._calculate_sms_parts(
            message,
            encoding
        )

        record = SMSRecord(
            msisdn=msisdn,
            message=message,
            encoding=encoding,
            sms_parts=sms_parts
        )

        return record, None

    # =====================================================================
    # Encoding Detection
    # =====================================================================

    def _detect_encoding(
        self,
        message: str
    ) -> str:

        if self.GSM7_REGEX.fullmatch(message):
            return "GSM7"

        return "UCS2"

    # =====================================================================
    # SMS Parts Calculation
    # =====================================================================

    def _calculate_sms_parts(
        self,
        message: str,
        encoding: str
    ) -> int:

        length = len(message)

        if encoding == "GSM7":

            if length <= 160:
                return 1

            return math.ceil(length / 153)

        # UCS2

        if length <= 70:
            return 1

        return math.ceil(length / 67)

    # =====================================================================
    # Write Invalid Records
    # =====================================================================

    def _write_invalid_records(
        self,
        rows
    ):

        output = Path(
            self.invalid_record_file
        )

        output.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(
            output,
            "w",
            newline="",
            encoding=self.encoding
        ) as fp:

            writer = csv.writer(
                fp,
                delimiter=self.delimiter
            )

            writer.writerow([
                "LINE_NUMBER",
                "MSISDN",
                "MESSAGE",
                "ERROR"
            ])

            writer.writerows(rows)

        self.logger.info(
            "Invalid records written to %s",
            output
        )    # =====================================================================
    # Verify Input File
    # =====================================================================

    def verify(self, input_file):

        file_path = Path(input_file)

        if not file_path.exists():
            raise FileNotFoundError(
                f"Input file not found: {input_file}"
            )

        if not file_path.is_file():
            raise ValueError(
                f"Not a valid file: {input_file}"
            )

        if file_path.stat().st_size == 0:
            raise ValueError(
                "Input file is empty."
            )

        self.logger.info(
            "Input file verified successfully."
        )

        return True

    # =====================================================================
    # Validation Summary
    # =====================================================================

    def summary(self, result):

        self.logger.info("=" * 70)
        self.logger.info("Validation Summary")
        self.logger.info("=" * 70)

        self.logger.info(
            "Total Records : %d",
            result.total_records
        )

        self.logger.info(
            "Valid Records : %d",
            result.valid_count
        )

        self.logger.info(
            "Invalid Records : %d",
            result.invalid_count
        )

        self.logger.info("=" * 70)


# ============================================================================
# Standalone Test
# ============================================================================

if __name__ == "__main__":

    import argparse

    from config_loader import ConfigLoader
    from logger import Logger

    parser = argparse.ArgumentParser(
        description="CSV Validator"
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Configuration JSON"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Input CSV file"
    )

    args = parser.parse_args()

    config = ConfigLoader(
        args.config
    ).load()

    logger = Logger.get_logger(config)

    validator = Validator(
        config,
        logger
    )

    try:

        validator.verify(args.input)

        result = validator.process(args.input)

        validator.summary(result)

        if result.success:

            logger.info(
                "Validation completed successfully."
            )

            raise SystemExit(0)

        logger.error(
            "No valid records found."
        )

        raise SystemExit(1)

    except Exception as ex:

        logger.exception(
            "Validation failed: %s",
            ex
        )

        raise SystemExit(2)

    finally:

        Logger.shutdown()
