<<<<<<< HEAD
# SMS Sender (SMPP Batch Application)

## Overview

This is a production-oriented Python SMPP batch SMS sender application.

The application reads an input CSV file, validates each record, sends SMS messages through an SMPP server, receives Delivery Reports (DLRs), writes CDR files, archives processed files, and logs all activities.

---

# Architecture

```
send_sms.py
      │
      ▼
sender.py
      │
      ▼
smpp_client.py
      │
      ▼
receiver.py
      │
      ▼
cdr_writer.py
```

Supporting modules

```
validator.py
archive.py
config_loader.py
logger.py
utils.py
models.py
dlr_parser.py
```

---

# Features

- SMPP Transceiver (TRX)
- CSV Batch Processing
- Configurable UAT / PROD environments
- CSV Validation
- GSM7 / UCS2 Detection
- SMS Segmentation Calculation
- Automatic Retry
- Auto Reconnect
- Enquire Link
- Delivery Report Processing
- CDR Generation
- Invalid Record Generation
- File Archiving
- Configurable Logging
- Graceful Shutdown

---

# Project Structure

```
sms_sender/
│
├── README.md
├── requirements.txt
├── install.sh
├── run.sh
│
├── conf/
│   ├── config-uat.json
│   └── config-prod.json
│
├── send_sms.py
├── sender.py
├── receiver.py
├── smpp_client.py
├── validator.py
├── archive.py
├── cdr_writer.py
├── dlr_parser.py
├── config_loader.py
├── logger.py
├── utils.py
├── models.py
│
├── input/
├── archive/
├── failed/
├── delivery_report/
└── logs/
```

---

# Input File Format

Filename

```
sms_input.csv
```

Format

```
MSISDN,Message
255712345678,Welcome to Pelatro
255712345679,Your OTP is 123456
```

Header is mandatory.

---

# Configuration

Configuration files

```
conf/config-uat.json
conf/config-prod.json
```

Everything is configurable.

- SMPP
- Logging
- Retry
- Archive
- DLR
- CDR
- Paths
- Timeouts
- Rate Limits

---

# Processing Flow

```
Read Configuration
        │
        ▼
Initialize Logger
        │
        ▼
Validate Input CSV
        │
        ▼
Connect to SMSC
        │
        ▼
Bind TRX
        │
        ▼
Start Receiver
        │
        ▼
Send SMS
        │
        ▼
Receive DLR
        │
        ▼
Generate CDR
        │
        ▼
Archive Input File
        │
        ▼
Shutdown
```

---

# Logging

Logs are written to the configured log directory.

Typical log entries

```
INFO
WARNING
ERROR
CRITICAL
DEBUG
```

Log rotation is supported through the logging configuration.

---

# Delivery Reports

Delivery reports are written as CSV files.

Example

```
SUBMIT_TIME,DELIVERY_TIME,MESSAGE_ID,MSISDN,STATUS,ERROR_CODE,DESCRIPTION
2026-07-01 10:00:01,2026-07-01 10:00:05,123456789,255712345678,DELIVRD,000,Delivered
```

---

# Archive

Processed files

```
archive/
```

Invalid input files

```
failed/
```

Invalid records

```
failed/invalid_records.csv
```

---

# Running

UAT

```
python3 send_sms.py --config conf/config-uat.json
```

Production

```
python3 send_sms.py --config conf/config-prod.json
```

---

# Dependencies

Python 3.10+

Required package

```
smpplib
```

Install using

```
pip install -r requirements.txt
```

---

# Exit Codes

```
0  Success

1  Configuration Error

2  Validation Error

3  SMPP Connection Failure

4  SMS Submission Failure

5  Unexpected Error
```

---

# Production Notes

- Use a dedicated Linux service account.
- Configure log rotation.
- Monitor disk usage.
- Enable automatic restart using systemd.
- Archive processed files regularly.
- Test against the target SMSC before production rollout.
=======
# SMSC-worker
Python Based Message Sender Application
>>>>>>> 09eeec758c7f93b33516f7b013302cc30781dea5
