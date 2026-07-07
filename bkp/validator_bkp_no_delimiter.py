#!/usr/bin/env python3
"""
===============================================================================
Module      : validator.py
Description : CSV Validation Module
Version     : 1.0
===============================================================================
"""

import csv
from typing import List

from models import (
    SMSRecord,
    InvalidRecord,
    ValidationResult
)


class Validator:
    """
    Validates input CSV files before submission.
    """

    GSM7_BASIC = (
        "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ"
        "ÆæßÉ !\"#¤%&'()*+,-./"
        "0123456789:;<=>?"
        "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ`"
        "¿abcdefghijklmnopqrstuvwxyzäöñüà"
    )

    GSM7_EXTENDED = "^{}\\[~]|€"

    def __init__(self, config, logger):

        self.config = config
        self.logger = logger

        validation = config["validation"]

        self.expected_header = validation["expected_header"]

        self.min_msisdn_length = validation["min_msisdn_length"]

        self.max_msisdn_length = validation["max_msisdn_length"]

        self.max_message_length = validation["max_message_length"]

    # =====================================================================
    # Public API
    # =====================================================================

    def validate(self, input_file: str) -> ValidationResult:

        result = ValidationResult(success=False)

        try:

            with open(
                input_file,
                newline="",
                encoding="utf-8"
            ) as fp:
                
                reader = csv.reader(fp)

                try:
                    header = next(reader)
                except StopIteration:
                    raise ValueError("Input CSV is empty.")

                self._validate_header(header)

                for row_number, row in enumerate(reader, start=2):

                    result.total_records += 1

                    if len(row) != 2:

                        result.invalid_records.append(
                            InvalidRecord(
                                row_number=row_number,
                                msisdn="",
                                message="",
                                reason="Invalid column count"
                            )
                        )

                        continue

                    msisdn = row[0].strip()

                    message = row[1].strip()

                    valid, reason = self._validate_msisdn(msisdn)

                    if not valid:

                        result.invalid_records.append(
                            InvalidRecord(
                                row_number=row_number,
                                msisdn=msisdn,
                                message=message,
                                reason=reason
                            )
                        )

                        continue

                    valid, reason = self._validate_message(message)

                    if not valid:

                        result.invalid_records.append(
                            InvalidRecord(
                                row_number=row_number,
                                msisdn=msisdn,
                                message=message,
                                reason=reason
                            )
                        )

                        continue

                    encoding = self.detect_encoding(message)

                    sms_parts = self.calculate_sms_parts(
                        message,
                        encoding
                    )

                    result.valid_records.append(
                        SMSRecord(
                            row_number=row_number,
                            msisdn=msisdn,
                            message=message,
                            encoding=encoding,
                            sms_parts=sms_parts
                        )
                    )

        except Exception as ex:

            self.logger.exception(
                "Validation failed: %s",
                ex
            )

            raise

        result.valid_count = len(result.valid_records)

        result.invalid_count = len(result.invalid_records)

        result.success = result.valid_count > 0

        self.logger.info(
            "Validation completed. Total=%d Valid=%d Invalid=%d",
            result.total_records,
            result.valid_count,
            result.invalid_count
        )

        return result

    # =====================================================================
    # Header Validation
    # =====================================================================

    def _validate_header(self, header):

        if header != self.expected_header:

            raise ValueError(
                f"Invalid CSV header. Expected: {self.expected_header}"
            )

    # =====================================================================
    # MSISDN Validation
    # =====================================================================

    def _validate_msisdn(self, msisdn):

        if not msisdn:

            return False, "MSISDN is empty"

        if not msisdn.isdigit():

            return False, "MSISDN must contain only digits"

        if len(msisdn) < self.min_msisdn_length:

            return False, "MSISDN too short"

        if len(msisdn) > self.max_msisdn_length:

            return False, "MSISDN too long"

        return True, ""
    
        # =====================================================================
    # Message Validation
    # =====================================================================

    def _validate_message(self, message):

        if message is None:

            return False, "Message is NULL"

        message = str(message)

        if len(message.strip()) == 0:

            return False, "Message is empty"

        if len(message) > self.max_message_length:

            return False, (
                f"Message exceeds maximum supported length "
                f"({self.max_message_length})"
            )

        return True, ""

    # =====================================================================
    # GSM 03.38 Detection
    # =====================================================================

    def is_gsm7(self, message: str) -> bool:

        for ch in message:

            if ch in self.GSM7_BASIC:
                continue

            if ch in self.GSM7_EXTENDED:
                continue

            return False

        return True

    # =====================================================================
    # Encoding Detection
    # =====================================================================

    def detect_encoding(self, message: str) -> str:

        if self.is_gsm7(message):

            return "GSM7"

        return "UCS2"

    # =====================================================================
    # GSM Septet Length
    # =====================================================================

    def gsm7_length(self, message: str) -> int:
        """
        Extended GSM characters occupy two septets.
        """

        length = 0

        for ch in message:

            if ch in self.GSM7_EXTENDED:

                length += 2

            else:

                length += 1

        return length

    # =====================================================================
    # SMS Part Calculation
    # =====================================================================

    def calculate_sms_parts(
        self,
        message: str,
        encoding: str
    ) -> int:

        if encoding == "GSM7":

            length = self.gsm7_length(message)

            #
            # Single GSM SMS
            #

            if length <= 160:

                return 1

            #
            # Concatenated GSM
            #

            return ((length - 1) // 153) + 1

        #
        # UCS2
        #

        length = len(message)

        if length <= 70:

            return 1

        #
        # Concatenated UCS2
        #

        return ((length - 1) // 67) + 1

    # =====================================================================
    # Record Statistics
    # =====================================================================

    def calculate_statistics(self, records: List[SMSRecord]):

        statistics = {

            "gsm7": 0,

            "ucs2": 0,

            "single_part": 0,

            "multi_part": 0,

            "total_sms_parts": 0

        }

        for record in records:

            if record.encoding == "GSM7":

                statistics["gsm7"] += 1

            else:

                statistics["ucs2"] += 1

            if record.sms_parts == 1:

                statistics["single_part"] += 1

            else:

                statistics["multi_part"] += 1

            statistics["total_sms_parts"] += record.sms_parts

        return statistics

    # =====================================================================
    # Logging
    # =====================================================================

    def log_statistics(self, statistics):

        self.logger.info("=" * 70)
        self.logger.info("Validation Statistics")
        self.logger.info("=" * 70)
        self.logger.info(
            "GSM7 Messages      : %d",
            statistics["gsm7"]
        )
        self.logger.info(
            "Unicode Messages   : %d",
            statistics["ucs2"]
        )
        self.logger.info(
            "Single Part SMS    : %d",
            statistics["single_part"]
        )
        self.logger.info(
            "Multipart SMS      : %d",
            statistics["multi_part"]
        )
        self.logger.info(
            "Total SMS Parts    : %d",
            statistics["total_sms_parts"]
        )
        self.logger.info("=" * 70)
    
        # =====================================================================
    # Invalid Record Writer
    # =====================================================================

    def write_invalid_records(
        self,
        invalid_records: List[InvalidRecord]
    ):

        if not invalid_records:

            self.logger.info("No invalid records found.")
            return

        output_file = self.config["paths"]["invalid_record_file"]

        try:

            with open(
                output_file,
                "w",
                newline="",
                encoding="utf-8"
            ) as fp:

                writer = csv.writer(fp)

                writer.writerow([
                    "ROW_NUMBER",
                    "MSISDN",
                    "MESSAGE",
                    "REASON"
                ])

                for record in invalid_records:

                    writer.writerow([
                        record.row_number,
                        record.msisdn,
                        record.message,
                        record.reason
                    ])

            self.logger.info(
                "Invalid record file created: %s",
                output_file
            )

        except Exception as ex:

            self.logger.exception(
                "Failed writing invalid record file: %s",
                ex
            )

            raise

    # =====================================================================
    # File Validation
    # =====================================================================

    def validate_file(self, input_file: str):

        try:

            with open(
                input_file,
                "r",
                encoding="utf-8"
            ) as fp:

                if fp.read(1) == "":

                    raise ValueError(
                        "Input CSV file is empty."
                    )

            return True

        except Exception:

            raise

    # =====================================================================
    # Validation Summary
    # =====================================================================

    def print_summary(self, result: ValidationResult):

        self.logger.info("=" * 70)
        self.logger.info("Validation Summary")
        self.logger.info("=" * 70)

        self.logger.info(
            "Total Records   : %d",
            result.total_records
        )

        self.logger.info(
            "Valid Records   : %d",
            result.valid_count
        )

        self.logger.info(
            "Invalid Records : %d",
            result.invalid_count
        )

        self.logger.info("=" * 70)

    # =====================================================================
    # Process Result
    # =====================================================================

    def finalize(
        self,
        result: ValidationResult
    ) -> ValidationResult:

        #
        # Write invalid records
        #

        self.write_invalid_records(
            result.invalid_records
        )

        #
        # Statistics
        #

        statistics = self.calculate_statistics(
            result.valid_records
        )

        self.log_statistics(
            statistics
        )

        self.print_summary(
            result
        )

        return result

    # =====================================================================
    # Validate And Finalize
    # =====================================================================

    def validate_input_file(
        self,
        input_file: str
    ) -> ValidationResult:

        self.validate_file(
            input_file
        )

        result = self.validate(
            input_file
        )

        return self.finalize(
            result
        )
        # =====================================================================
    # Validation Report
    # =====================================================================

    def generate_report(self, result: ValidationResult) -> dict:
        """
        Returns validation summary as dictionary.
        """

        return {
            "success": result.success,
            "total_records": result.total_records,
            "valid_records": result.valid_count,
            "invalid_records": result.invalid_count
        }

    # =====================================================================
    # Print Invalid Records
    # =====================================================================

    def print_invalid_records(
        self,
        result: ValidationResult
    ):

        if not result.invalid_records:
            return

        self.logger.warning("=" * 70)
        self.logger.warning("Invalid Records")
        self.logger.warning("=" * 70)

        for record in result.invalid_records:

            self.logger.warning(
                "Row=%d MSISDN=%s Reason=%s",
                record.row_number,
                record.msisdn,
                record.reason
            )

        self.logger.warning("=" * 70)

    # =====================================================================
    # Validate Convenience Method
    # =====================================================================

    def process(self, input_file: str) -> ValidationResult:
        """
        Main entry point used by send_sms.py
        """

        result = self.validate_input_file(input_file)

        self.print_invalid_records(result)

        return result


# =============================================================================
# Standalone Execution
# =============================================================================

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
        help="Input CSV File"
    )

    args = parser.parse_args()

    #
    # Load Configuration
    #

    config = ConfigLoader(
        args.config
    ).load()

    logger = Logger.get_logger(config)

    validator = Validator(
        config,
        logger
    )

    try:

        result = validator.process(
            args.input
        )

        logger.info(
            "Validation Status : %s",
            "SUCCESS" if result.success else "FAILED"
        )

        logger.info(
            "Valid Records Returned : %d",
            len(result.valid_records)
        )

        raise SystemExit(0)

    except Exception as ex:

        logger.exception(
            "Validation failed : %s",
            ex
        )

        raise SystemExit(1)
