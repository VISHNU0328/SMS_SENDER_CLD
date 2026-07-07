#!/usr/bin/env python3
"""
===============================================================================
Module      : models.py
Description : Common Data Models
Author      : Pelatro
Version     : 1.1
===============================================================================
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


# ============================================================================
# SMS Record
# ============================================================================

@dataclass
class SMSRecord:
    row_number: int = 0
    msisdn: str = ""
    message: str = ""
    encoding: str = "GSM7"
    sms_parts: int = 1

    message_id: str = ""

    submit_time: Optional[str] = None
    delivery_time: Optional[str] = None

    source_addr: str = ""

    status: str = "PENDING"

    error_code: str = ""
    error_description: str = ""

    retry_count: int = 0

    created_at: datetime = field(default_factory=datetime.now)

    def mark_submitted(self, message_id: str):
        self.message_id = message_id
        self.submit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.status = "SUBMITTED"

    def mark_delivered(self, delivery_time: str):
        self.delivery_time = delivery_time
        self.status = "DELIVRD"

    def mark_failed(self, error_code: str, reason: str):
        self.error_code = error_code
        self.error_description = reason
        self.status = "FAILED"

    def increment_retry(self):
        self.retry_count += 1


# ============================================================================
# Delivery Report
# ============================================================================

@dataclass
class DeliveryReport:
    message_id: str
    msisdn: str
    status: str
    submit_time: str
    done_time: str

    error_code: str = "000"
    description: str = ""
    raw_pdu: str = ""


# ============================================================================
# Invalid Record
# ============================================================================

@dataclass
class InvalidRecord:
    row_number: int
    msisdn: str
    message: str
    reason: str


# ============================================================================
# Validation Result
# ============================================================================

@dataclass
class ValidationResult:
    success: bool = False

    valid_records: List[SMSRecord] = field(default_factory=list)
    invalid_records: List[InvalidRecord] = field(default_factory=list)

    total_records: int = 0
    valid_count: int = 0
    invalid_count: int = 0


# ============================================================================
# Application Statistics
# ============================================================================

@dataclass
class ApplicationStatistics:
    total_records: int = 0
    submitted_records: int = 0
    delivered_records: int = 0
    failed_records: int = 0
    invalid_records: int = 0
    total_sms_parts: int = 0

    start_time: Optional[str] = None
    end_time: Optional[str] = None

    execution_time: float = 0.0


# ============================================================================
# Message Correlation
# ============================================================================

@dataclass
class MessageCorrelation:
    message_id: str
    msisdn: str
    source_addr: str
    encoding: str
    sms_parts: int
    submit_time: str


# ============================================================================
# SMPP Submit Result
# ============================================================================

@dataclass
class SubmitResult:
    success: bool
    message_id: str = ""
    error_message: str = ""
    command_status: int = 0


# ============================================================================
# SMPP Connection Status
# ============================================================================

@dataclass
class ConnectionStatus:
    connected: bool = False
    bound: bool = False
    reconnect_count: int = 0
    last_connected_time: str = ""


# ============================================================================
# Health Status
# ============================================================================

@dataclass
class HealthStatus:
    application: str
    environment: str
    connected: bool
    bound: bool
    sender_alive: bool
    receiver_alive: bool
    enquire_alive: bool
    timestamp: str
