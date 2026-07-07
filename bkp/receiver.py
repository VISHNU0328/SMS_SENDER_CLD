#!/usr/bin/env python3
"""
===============================================================================
Module      : receiver.py
Description : SMPP Delivery Report Receiver
Version     : 1.0
===============================================================================
"""

import threading
import time

from dlr_parser import DLRParser


class Receiver:
    """
    Background receiver responsible for:

    - Reading deliver_sm PDUs
    - Parsing delivery reports
    - Correlating Message IDs
    - Writing CDRs
    - Updating sender statistics
    """

    def __init__(
        self,
        config,
        logger,
        smpp_client,
        sender,
        cdr_writer
    ):

        self.config = config
        self.logger = logger

        self.smpp_client = smpp_client
        self.sender = sender
        self.cdr_writer = cdr_writer

        self.parser = DLRParser(logger)

        self.shutdown_event = threading.Event()

        self.thread = None

    # =====================================================================
    # Start Receiver
    # =====================================================================

    def start(self):

        if self.thread and self.thread.is_alive():
            return

        self.thread = threading.Thread(
            target=self._receive_loop,
            name="ReceiverThread",
            daemon=True
        )

        self.thread.start()

        self.logger.info(
            "Receiver thread started."
        )

    # =====================================================================
    # Receive Loop
    # =====================================================================

    def _receive_loop(self):

        self.logger.info(
            "Waiting for Delivery Reports..."
        )

        while not self.shutdown_event.is_set():

            try:

                pdu = self.smpp_client.read_pdu()

                if pdu is None:

                    time.sleep(0.2)
                    continue

                self._process_pdu(pdu)

            except Exception as ex:

                self.logger.exception(
                    "Receiver loop error: %s",
                    ex
                )

                time.sleep(1)

        self.logger.info(
            "Receiver thread stopped."
        )

    # =====================================================================
    # Process PDU
    # =====================================================================

    def _process_pdu(self, pdu):

        #
        # Ignore non-deliver_sm PDUs
        #

        if not hasattr(pdu, "command"):

            return

        if str(pdu.command) != "deliver_sm":

            return

        report = self.parser.parse(pdu)

        self._process_delivery_report(report)
    
        # =====================================================================
    # Process Delivery Report
    # =====================================================================

    def _process_delivery_report(self, report):

        correlation = self.sender.get_correlation(
            report.message_id
        )

        if correlation is None:

            self.logger.warning(
                "No correlation found for MessageID=%s",
                report.message_id
            )

            return

        #
        # Populate MSISDN from sender mapping
        #

        report.msisdn = correlation.msisdn

        #
        # Write Delivery Report
        #

        self.cdr_writer.write(report)

        #
        # Update sender statistics
        #

        delivered = report.status.upper() == "DELIVRD"

        self.sender.update_delivery_statistics(
            delivered
        )

        #
        # Remove processed correlation
        #

        self.sender.remove_correlation(
            report.message_id
        )

        self.logger.info(
            "DLR processed. "
            "MessageID=%s MSISDN=%s Status=%s",
            report.message_id,
            report.msisdn,
            report.status
        )

    # =====================================================================
    # Pending Delivery Reports
    # =====================================================================

    def pending(self):

        return self.sender.pending_messages()

    # =====================================================================
    # Receiver Statistics
    # =====================================================================

    def statistics(self):

        return {
            "pending_messages": self.pending(),
            "thread_alive": self.thread.is_alive()
            if self.thread else False
        }

    # =====================================================================
    # Health
    # =====================================================================

    def health(self):

        return {
            "receiver_running":
                self.thread.is_alive()
                if self.thread else False,

            "pending_messages":
                self.pending()
        }
        # =====================================================================
    # Wait for Pending DLRs
    # =====================================================================

    def wait_for_pending(
        self,
        timeout=None
    ):
        """
        Wait until all pending message correlations have been
        processed or the timeout expires.
        """

        start = time.time()

        while not self.shutdown_event.is_set():

            pending = self.pending()

            if pending == 0:

                self.logger.info(
                    "All pending delivery reports processed."
                )

                return True

            if timeout is not None:

                if (time.time() - start) >= timeout:

                    self.logger.warning(
                        "Timed out waiting for delivery reports. "
                        "Pending=%d",
                        pending
                    )

                    return False

            time.sleep(1)

        return False

    # =====================================================================
    # Join Receiver Thread
    # =====================================================================

    def join(self, timeout=None):

        if self.thread:

            self.thread.join(timeout)

    # =====================================================================
    # Is Running
    # =====================================================================

    def is_running(self):

        return (
            self.thread is not None and
            self.thread.is_alive()
        )

    # =====================================================================
    # Monitor
    # =====================================================================

    def monitor(self):

        stats = self.statistics()

        self.logger.info(
            "Receiver Status | "
            "Running=%s Pending=%d",
            stats["thread_alive"],
            stats["pending_messages"]
        )

    # =====================================================================
    # Shutdown
    # =====================================================================

    def shutdown(self):
        """
        Gracefully stop the receiver thread.
        """

        self.logger.info(
            "Stopping receiver..."
        )

        self.shutdown_event.set()

        self.join(timeout=5)

        self.logger.info(
            "Receiver shutdown complete."
        )

    # =====================================================================
    # Reset
    # =====================================================================

    def reset(self):

        self.shutdown_event.clear()

        self.logger.info(
            "Receiver reset completed."
        )
    # =============================================================================
# Standalone Execution
# =============================================================================

if __name__ == "__main__":

    import argparse

    from config_loader import ConfigLoader
    from logger import Logger
    from smpp_client import SMPPClient
    from sender import Sender
    from cdr_writer import CDRWriter

    parser = argparse.ArgumentParser(
        description="SMPP Delivery Report Receiver"
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Configuration JSON"
    )

    args = parser.parse_args()

    #
    # Load configuration
    #

    config = ConfigLoader(
        args.config
    ).load()

    logger = Logger.get_logger(config)

    client = SMPPClient(
        config=config,
        logger=logger
    )

    if not client.start():

        logger.error(
            "Unable to establish SMPP session."
        )

        raise SystemExit(1)

    #
    # Start enquire link thread
    #

    client.start_enquire_link_thread()

    sender = Sender(
        config=config,
        logger=logger,
        smpp_client=client
    )

    cdr_writer = CDRWriter(
        config=config,
        logger=logger
    )

    receiver = Receiver(
        config=config,
        logger=logger,
        smpp_client=client,
        sender=sender,
        cdr_writer=cdr_writer
    )

    try:

        receiver.start()

        logger.info("=" * 80)
        logger.info("Receiver started successfully.")
        logger.info("Waiting for Delivery Reports...")
        logger.info("=" * 80)

        while True:

            time.sleep(5)

            receiver.monitor()

    except KeyboardInterrupt:

        logger.info(
            "Shutdown requested by user."
        )

    except Exception as ex:

        logger.exception(
            "Receiver failed: %s",
            ex
        )

        raise SystemExit(2)

    finally:

        receiver.shutdown()

        client.shutdown()

        Logger.shutdown()