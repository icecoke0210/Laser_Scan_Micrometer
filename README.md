# Mitutoyo 6200 RS232 Measurement Classifier

A macOS-friendly, PC-based Python app that reads measurement data from a Mitutoyo Laser Scan Micrometer (model 6200) via RS232, logs readings, and classifies them (e.g., Pass/Fail) based on configurable rules.

## Features
- Auto-detect serial ports on macOS (e.g., `/dev/tty.usbserial*`, `/dev/tty.usbmodem*`)
- Configurable serial parameters (baud rate, data bits, parity, stop bits)
- Line-based parsing of incoming readings with a Mitutoyo 6200 protocol parser stub
- CSV logging with timestamps
- Simple threshold-based classification (configurable) and console display

## Requirements
- Python 3.9+
- USB-to-RS232 adapter for mac (driver may be required depending on adapter)

## Quick Start
1) Create a virtual environment and install dependencies

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Adjust `config.yaml` as needed (port, baud rate, classification thresholds)

3) List available serial ports

```
python run.py --list-ports
```

4) Start reading and classifying

```
python run.py --port /dev/tty.usbserial-XXXX --baud 9600 --csv logs/readings.csv
```

You can also set these in `config.yaml` and run without flags:

```
python run.py
```

## Notes on Mitutoyo 6200 Protocol
- The exact output format can vary by mode/configuration. This starter reads line-oriented ASCII and tries to parse a numeric value. If your unit sends a different frame (e.g., prefixed codes, checksum), update `protocols/mitutoyo6200.py` accordingly.
- Common defaults to try: 9600 baud, 8 data bits, no parity, 1 stop bit (9600-8-N-1). Check your 6200 manual to confirm.

## Packaging
Later we can package this into a standalone mac app (e.g., using PyInstaller). For now, validate end-to-end reading and classification from the CLI.
