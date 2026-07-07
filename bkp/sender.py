#!/usr/bin/env python3
"""
===============================================================================
Module      : sender.py
Description : SMS Sender Module
Version     : 1.0
===============================================================================
"""

import threading
import time
from typing import Dict, List

from models import (
    SMSRecord,
    ApplicationStatistics,
    MessageCorrelation
)


class Sender:
    """
    Responsible for submitting validated SMS records to the SMPP client.

    Responsibilities
    ----------------
    - Submit SMS
    - Retry on failure
    - Rate limiting
    - Maintain MessageID correlation
    - Update statistics

    Does NOT:
    - Parse DLRs
    - Write CDRs
    - Archive files
    """

    def __init__(self, config, logger, smpp_client):

        self.config = config
        self.logger = logger
        self.smpp_client = smpp_client

        processing = config["processing"]

        self.rate_limit = processing.get(
            "rate_limit_per_second",
            50
        )

        self.max_retry = processing.get(
            "max_retry",
            3
        )

        self.retry_interval = processing.get(
            "retry_interval_seconds",
            5
        )

        self.statistics = ApplicationStatistics()

        #
        # MessageID -> MessageCorrelation
        #
        self.message_mapping: Dict[str, MessageCorrelation] = {}

        self.lock = threading.Lock()

    # =====================================================================
    # Public API
    # =====================================================================

    def send(
        self,
        records: List[SMSRecord]
    ) -> ApplicationStatistics:

        self.statistics.total_records = len(records)

        self.logger.info(
            "Starting SMS submission. Total records=%d",
            len(records)
        )

        delay = 1.0 / self.rate_limit if self.rate_limit > 0 else 0

        for record in records:

            self._submit_record(record)

            if delay > 0:
                time.sleep(delay)

        self.logger.info(
            "SMS submission completed."
        )

        return self.statistics

    # =====================================================================
    # Submit One Record
    # =====================================================================

    def _submit_record(
        self,
        record: SMSRecord
    ):

        attempts = 0

        while attempts <= self.max_retry:

            attempts += 1

            result = self.smpp_client.submit_sm(record)

            if result.success:

                self._submission_success(
                    record,
                    result.message_id
                )

                return

            self.logger.warning(
                "Submission failed for %s (Attempt %d/%d): %s",
                record.msisdn,
                attempts,
                self.max_retry + 1,
                result.error_message
            )

            record.increment_retry()

            if attempts <= self.max_retry:

                time.sleep(self.retry_interval)

        #
        # All retries exhausted
        #

        record.mark_failed(
            "SUBMIT_FAILED",
            "Maximum retry attempts exceeded"
        )

        with self.lock:

            self.statistics.failed_records += 1

        self.logger.error(
            "SMS permanently failed for %s",
            record.msisdn
        )

    # =====================================================================
    # Success Handler
    # =====================================================================

    def _submission_success(
        self,
        record: SMSRecord,
        message_id: str
    ):

        correlation = MessageCorrelation(
            message_id=message_id,
            msisdn=record.msisdn,
            source_addr=record.source_addr,
            encoding=record.encoding,
            sms_parts=record.sms_parts,
            submit_time=record.submit_time
        )

        with self.lock:

            self.message_mapping[message_id] = correlation

            self.statistics.submitted_records += 1
            self.statistics.total_sms_parts += record.sms_parts

        self.logger.info(
            "Submitted SMS: MessageID=%s MSISDN=%s Parts=%d",
            message_id,
            record.msisdn,
            record.sms_parts
        )
        # =====================================================================
    # Message Correlation
    # =====================================================================

    def get_correlation(
        self,
        message_id: str
    ):
        """
        Returns the MessageCorrelation object for a given SMPP Message ID.
        """

        with self.lock:
            return self.message_mapping.get(message_id)

    def get_all_correlations(self):
        """
        Returns a copy of the complete message mapping.
        """

        with self.lock:
            return dict(self.message_mapping)

    def remove_correlation(
        self,
        message_id: str
    ):
        """
        Removes a correlation once the corresponding DLR
        has been successfully processed.
        """

        with self.lock:

            if message_id in self.message_mapping:
                del self.message_mapping[message_id]

    # =====================================================================
    # Statistics
    # =====================================================================

    def get_statistics(self):

        with self.lock:
            return self.statistics

    def update_delivery_statistics(
        self,
        delivered: bool
    ):

        with self.lock:

            if delivered:
                self.statistics.delivered_records += 1
            else:
                self.statistics.failed_records += 1

    # =====================================================================
    # Batch Summary
    # =====================================================================

    def print_summary(self):

        stats = self.get_statistics()

        self.logger.info("=" * 70)
        self.logger.info("SMS Submission Summary")
        self.logger.info("=" * 70)
        self.logger.info(
            "Total Records      : %d",
            stats.total_records
        )
        self.logger.info(
            "Submitted          : %d",
            stats.submitted_records
        )
        self.logger.info(
            "Failed             : %d",
            stats.failed_records
        )
        self.logger.info(
            "SMS Parts          : %d",
            stats.total_sms_parts
        )
        self.logger.info("=" * 70)

    # =====================================================================
    # Pending Messages
    # =====================================================================

    def pending_messages(self) -> int:

        with self.lock:
            return len(self.message_mapping)

    # =====================================================================
    # Lookup by Message ID
    # =====================================================================

    def lookup_msisdn(
        self,
        message_id: str
    ):

        correlation = self.get_correlation(message_id)

        if correlation:
            return correlation.msisdn

        return None

    # =====================================================================
    # Wait Helper
    # =====================================================================

    def wait_for_completion(self):

        self.logger.info(
            "Submission completed. Pending DLR mappings=%d",
            self.pending_messages()
        )
        # =====================================================================
    # Message Mapping Persistence
    # =====================================================================

    def save_message_mapping(self):
        """
        Persist the current Message ID mapping to CSV so it can
        be used by receiver.py for DLR correlation.
        """

        output_file = self.config["paths"]["message_mapping_file"]

        import csv
        from pathlib import Path

        Path(output_file).parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with self.lock:

            with open(
                output_file,
                "w",
                newline="",
                encoding="utf-8"
            ) as fp:

                writer = csv.writer(fp)

                writer.writerow([
                    "MESSAGE_ID",
                    "MSISDN",
                    "SOURCE_ADDR",
                    "ENCODING",
                    "SMS_PARTS",
                    "SUBMIT_TIME"
                ])

                for correlation in self.message_mapping.values():

                    writer.writerow([
                        correlation.message_id,
                        correlation.msisdn,
                        correlation.source_addr,
                        correlation.encoding,
                        correlation.sms_parts,
                        correlation.submit_time
                    ])

        self.logger.info(
            "Message mapping saved: %s",
            output_file
        )

    # =====================================================================
    # Load Message Mapping
    # =====================================================================

    def load_message_mapping(self):
        """
        Reload previously saved mappings.
        """

        import csv
        from pathlib import Path

        mapping_file = self.config["paths"]["message_mapping_file"]

        if not Path(mapping_file).exists():

            return

        with self.lock:

            self.message_mapping.clear()

            with open(
                mapping_file,
                newline="",
                encoding="utf-8"
            ) as fp:

                reader = csv.DictReader(fp)

                for row in reader:

                    correlation = MessageCorrelation(
                        message_id=row["MESSAGE_ID"],
                        msisdn=row["MSISDN"],
                        source_addr=row["SOURCE_ADDR"],
                        encoding=row["ENCODING"],
                        sms_parts=int(row["SMS_PARTS"]),
                        submit_time=row["SUBMIT_TIME"]
                    )

                    self.message_mapping[
                        correlation.message_id
                    ] = correlation

        self.logger.info(
            "Loaded %d message mappings.",
            len(self.message_mapping)
        )

    # =====================================================================
    # Clear Mapping
    # =====================================================================

    def clear_message_mapping(self):

        with self.lock:

            self.message_mapping.clear()

        self.logger.info(
            "Message correlation cache cleared."
        )

    # =====================================================================
    # Health
    # =====================================================================

    def health(self):

        with self.lock:

            return {
                "pending_messages": len(self.message_mapping),
                "submitted": self.statistics.submitted_records,
                "failed": self.statistics.failed_records,
                "total_sms_parts": self.statistics.total_sms_parts
            }

    # =====================================================================
    # Reset Statistics
    # =====================================================================

    def reset(self):

        with self.lock:

            self.statistics = ApplicationStatistics()

            self.message_mapping.clear()

        self.logger.info(
            "Sender state reset."
        )

    # =====================================================================
    # Shutdown
    # =====================================================================

    def shutdown(self):

        self.save_message_mapping()

        self.logger.info(
            "Sender shutdown complete."
        )
    # =============================================================================
# Standalone Execution
# =============================================================================

if __name__ == "__main__":

    import argparse

    from config_loader import ConfigLoader
    from logger import Logger
    from validator import Validator
    from smpp_client import SMPPClient

    parser = argparse.ArgumentParser(
        description="SMS Sender"
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

    #
    # Load configuration
    #

    config = ConfigLoader(
        args.config
    ).load()

    logger = Logger.get_logger(config)

    validator = Validator(
        config,
        logger
    )

    validation_result = validator.process(
        args.input
    )

    if not validation_result.success:

        logger.error(
            "No valid records found. Exiting."
        )

        raise SystemExit(1)

    client = SMPPClient(
        config=config,
        logger=logger
    )

    if not client.start():

        logger.error(
            "Unable to establish SMPP session."
        )

        raise SystemExit(2)

    client.start_enquire_link_thread()

    sender = Sender(
        config=config,
        logger=logger,
        smpp_client=client
    )

    try:

        statistics = sender.send(
            validation_result.valid_records
        )

        sender.print_summary()

        logger.info(
            "Submission completed successfully."
        )

        logger.info(
            "Statistics: %s",
            statistics
        )

    except Exception as ex:

        logger.exception(
            "Unexpected sender error: %s",
            ex
        )

        raise SystemExit(3)

    finally:

        sender.shutdown()

        client.shutdown()

        Logger.shutdown()