#!/usr/bin/env python3
"""
===============================================================================
Module      : smpp_client.py
Description : SMPP Client Session Manager
Version     : 1.0
===============================================================================
"""

import threading
import time

import smpplib.client
import smpplib.consts
import smpplib.gsm

from models import (
    SubmitResult,
    ConnectionStatus
)


class SMPPClient:
    """
    SMPP session manager.

    Responsibilities:
      - Connect
      - Bind
      - submit_sm()
      - read_pdu()
      - enquire_link()
      - reconnect()
      - disconnect()

    DLR parsing is intentionally handled by receiver.py.
    """

    def __init__(self, config, logger):

        self.config = config
        self.logger = logger

        smpp = config["smpp"]

        self.host = smpp["host"]
        self.port = smpp["port"]

        self.system_id = smpp["system_id"]
        self.password = smpp["password"]
        self.system_type = smpp.get("system_type", "")

        self.source_addr = smpp["source_addr"]

        self.addr_ton = smpp["addr_ton"]
        self.addr_npi = smpp["addr_npi"]

        self.dest_ton = smpp["dest_ton"]
        self.dest_npi = smpp["dest_npi"]

        self.data_coding = smpp["data_coding"]

        self.registered_delivery = smpp["registered_delivery"]

        self.connection_timeout = smpp["connection_timeout"]
        self.socket_timeout = smpp["socket_timeout"]

        self.enquire_link_interval = smpp["enquire_link_interval"]
        self.reconnect_interval = smpp["reconnect_interval"]

        self.max_reconnect_attempts = smpp.get(
            "max_reconnect_attempts",
            0
        )

        self.client = None

        self.lock = threading.RLock()

        self.status = ConnectionStatus()

        self.shutdown_event = threading.Event()

    # =====================================================================
    # Connect
    # =====================================================================

    def connect(self):

        with self.lock:

            if self.status.connected:
                return True

            try:

                self.logger.info(
                    "Connecting to %s:%s",
                    self.host,
                    self.port
                )

                self.client = smpplib.client.Client(
                    self.host,
                    self.port
                )

                self.client.connect()

                self.status.connected = True

                self.logger.info(
                    "TCP connection established."
                )

                return True

            except Exception as ex:

                self.status.connected = False

                self.logger.exception(
                    "Connection failed: %s",
                    ex
                )

                return False

    # =====================================================================
    # Bind
    # =====================================================================

    def bind(self):

        if not self.status.connected:

            if not self.connect():
                return False

        try:

            self.client.bind_transceiver(

                system_id=self.system_id,

                password=self.password,

                system_type=self.system_type

            )

            self.status.bound = True

            self.logger.info(
                "Successfully bound as transceiver."
            )

            return True

        except Exception as ex:

            self.status.bound = False

            self.logger.exception(
                "Bind failed: %s",
                ex
            )

            return False

    # =====================================================================
    # Start
    # =====================================================================

    def start(self):

        if not self.connect():
            return False

        if not self.bind():
            return False

        return True

        # =====================================================================
    # Submit SMS
    # =====================================================================

    def submit_sm(
        self,
        record
    ) -> SubmitResult:

        with self.lock:

            if not self.verify_session():

                return SubmitResult(
                    success=False,
                    error_message="SMPP session is not available."
                )

            try:

                short_message = record.message

                data_coding = (
                    self.data_coding
                    if record.encoding == "GSM7"
                    else smpplib.consts.SMPP_ENCODING_ISO10646
                )

                response = self.client.send_message(

                    source_addr_ton=self.addr_ton,
                    source_addr_npi=self.addr_npi,
                    source_addr=self.source_addr,

                    dest_addr_ton=self.dest_ton,
                    dest_addr_npi=self.dest_npi,
                    destination_addr=record.msisdn,

                    short_message=short_message,

                    data_coding=data_coding,

                    registered_delivery=self.registered_delivery

                )

                message_id = ""

                if hasattr(response, "message_id"):

                    message_id = str(response.message_id)

                elif hasattr(response, "seq"):

                    message_id = str(response.seq)

                record.mark_submitted(message_id)

                self.logger.info(
                    "SMS submitted successfully. "
                    "MSISDN=%s MessageID=%s",
                    record.msisdn,
                    message_id
                )

                return SubmitResult(
                    success=True,
                    message_id=message_id
                )

            except Exception as ex:

                self.logger.exception(
                    "SMS submission failed for %s : %s",
                    record.msisdn,
                    ex
                )

                return SubmitResult(
                    success=False,
                    error_message=str(ex)
                )

    # =====================================================================
    # Read PDU
    # =====================================================================

    def read_pdu(self):
        """
        Read one incoming SMPP PDU.

        receiver.py is responsible for calling this method
        continuously and handling deliver_sm PDUs.
        """

        if not self.verify_session():

            return None

        try:

            return self.client.read_once()

        except Exception as ex:

            self.logger.exception(
                "Failed to read PDU: %s",
                ex
            )

            self.status.connected = False
            self.status.bound = False

            return None

    # =====================================================================
    # Enquire Link
    # =====================================================================

    def enquire_link(self):

        if not self.verify_session():

            return False

        try:

            self.client.enquire_link()

            self.logger.debug(
                "enquire_link successful."
            )

            return True

        except Exception as ex:

            self.logger.warning(
                "enquire_link failed: %s",
                ex
            )

            self.status.connected = False
            self.status.bound = False

            return False
        # =====================================================================
    # Verify Session
    # =====================================================================

    def verify_session(self) -> bool:
        """
        Verify SMPP session state.

        If the connection is lost, attempt automatic reconnect.
        """

        if self.status.connected and self.status.bound:
            return True

        self.logger.warning(
            "SMPP session unavailable. Attempting reconnect..."
        )

        return self.reconnect()

    # =====================================================================
    # Reconnect
    # =====================================================================

    def reconnect(self) -> bool:

        attempts = 0

        while not self.shutdown_event.is_set():

            if (
                self.max_reconnect_attempts > 0 and
                attempts >= self.max_reconnect_attempts
            ):

                self.logger.error(
                    "Maximum reconnect attempts reached."
                )

                return False

            attempts += 1

            self.status.reconnect_count += 1

            self.logger.info(
                "Reconnect attempt %d",
                attempts
            )

            try:

                self.disconnect()

            except Exception:
                pass

            if self.connect() and self.bind():

                self.logger.info(
                    "SMPP reconnection successful."
                )

                return True

            self.logger.warning(
                "Reconnect failed. Waiting %d seconds...",
                self.reconnect_interval
            )

            time.sleep(self.reconnect_interval)

        return False

    # =====================================================================
    # Disconnect
    # =====================================================================

    def disconnect(self):

        with self.lock:

            if self.client is None:

                self.status.connected = False
                self.status.bound = False

                return

            try:

                if self.status.bound:

                    try:
                        self.client.unbind()
                    except Exception:
                        pass

                try:
                    self.client.disconnect()
                except Exception:
                    pass

            finally:

                self.client = None

                self.status.connected = False
                self.status.bound = False

                self.logger.info(
                    "Disconnected from SMSC."
                )

    # =====================================================================
    # Health
    # =====================================================================

    def health(self):

        return {
            "connected": self.status.connected,
            "bound": self.status.bound,
            "reconnect_count": self.status.reconnect_count
        }

    # =====================================================================
    # Ping
    # =====================================================================

    def ping(self) -> bool:
        """
        Used by send_sms.py to verify connectivity.
        """

        return self.enquire_link()

    # =====================================================================
    # Context Manager
    # =====================================================================

    def __enter__(self):

        if not self.start():

            raise RuntimeError(
                "Unable to establish SMPP session."
            )

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback
    ):

        self.shutdown()

        return False
    
        # =====================================================================
    # Enquire Link Thread
    # =====================================================================

    def start_enquire_link_thread(self):
        """
        Starts the background enquire_link thread.
        """

        if hasattr(self, "_enquire_thread") and \
                self._enquire_thread.is_alive():
            return

        self._enquire_thread = threading.Thread(
            target=self._enquire_link_worker,
            name="EnquireLinkThread",
            daemon=True
        )

        self._enquire_thread.start()

        self.logger.info(
            "Enquire Link thread started."
        )

    def _enquire_link_worker(self):
        """
        Periodically sends enquire_link to keep the SMPP
        session alive.
        """

        while not self.shutdown_event.is_set():

            try:

                self.enquire_link()

            except Exception as ex:

                self.logger.warning(
                    "Enquire Link failed: %s",
                    ex
                )

            self.shutdown_event.wait(
                self.enquire_link_interval
            )

        self.logger.info(
            "Enquire Link thread stopped."
        )

    # =====================================================================
    # Thread Status
    # =====================================================================

    def thread_status(self):

        enquire_alive = False

        if hasattr(self, "_enquire_thread"):

            enquire_alive = self._enquire_thread.is_alive()

        return {

            "connected": self.status.connected,

            "bound": self.status.bound,

            "enquire_thread": enquire_alive,

            "reconnect_count": self.status.reconnect_count

        }

    # =====================================================================
    # Statistics
    # =====================================================================

    def statistics(self):

        return {

            "host": self.host,

            "port": self.port,

            "connected": self.status.connected,

            "bound": self.status.bound,

            "reconnect_count": self.status.reconnect_count

        }

    # =====================================================================
    # Shutdown
    # =====================================================================

    def shutdown(self):
        """
        Gracefully stop background processing and disconnect.
        """

        self.logger.info(
            "Shutting down SMPP client..."
        )

        self.shutdown_event.set()

        if hasattr(self, "_enquire_thread"):

            self._enquire_thread.join(timeout=5)

        self.disconnect()

        self.logger.info(
            "SMPP client shutdown complete."
        )
    
    # =============================================================================
# Standalone Execution
# =============================================================================

if __name__ == "__main__":

    import argparse

    from config_loader import ConfigLoader
    from logger import Logger

    parser = argparse.ArgumentParser(
        description="SMPP Client Test"
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

    try:

        logger.info("=" * 80)
        logger.info("SMPP Client Connectivity Test")
        logger.info("=" * 80)

        #
        # Connect and Bind
        #

        if not client.start():

            logger.error("Unable to establish SMPP session.")

            raise SystemExit(1)

        logger.info("SMPP session established successfully.")

        #
        # Health
        #

        logger.info("Health Status : %s", client.health())

        #
        # Enquire Link Test
        #

        if client.ping():

            logger.info("enquire_link successful.")

        else:

            logger.warning("enquire_link failed.")

        #
        # Start keepalive thread
        #

        client.start_enquire_link_thread()

        logger.info(
            "Client running. Press Ctrl+C to stop..."
        )

        while True:

            time.sleep(1)

    except KeyboardInterrupt:

        logger.info("Interrupted by user.")

    except Exception as ex:

        logger.exception(
            "Unexpected error: %s",
            ex
        )

    finally:

        client.shutdown()

        Logger.shutdown()