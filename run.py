from __future__ import annotations

import argparse
import sys
from typing import Optional

from rich.console import Console
from rich.table import Table

from lsm6200.config import AppConfig, load_config, SerialConfig, LoggingConfig
from lsm6200.serial_utils import available_ports, managed_serial
from lsm6200.protocols import Mitutoyo6200Parser
from lsm6200.classifier import classify_value
from lsm6200.logging_utils import CsvLogger

console = Console()


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Mitutoyo 6200 RS232 Reader & Classifier")
    p.add_argument("--config", type=str, default=None, help="Path to config.yaml")

    # Serial overrides
    p.add_argument("--list-ports", action="store_true", help="List available serial ports and exit")
    p.add_argument("--port", type=str, default=None, help="Serial port device path (e.g., /dev/tty.usbserial-XXXX)")
    p.add_argument("--baud", type=int, default=None, help="Baud rate (e.g., 9600)")
    p.add_argument("--bytesize", type=int, default=None, help="Data bits (5,6,7,8)")
    p.add_argument("--parity", type=str, default=None, help="Parity (N,E,O,M,S)")
    p.add_argument("--stopbits", type=float, default=None, help="Stop bits (1, 1.5, 2)")
    p.add_argument("--timeout", type=float, default=None, help="Read timeout seconds")

    # Logging
    p.add_argument("--csv", type=str, default=None, help="CSV log path")
    p.add_argument("--no-append", action="store_true", help="Overwrite CSV instead of appending")
    p.add_argument("--utc", action="store_true", help="Use UTC timestamps in CSV")

    return p


def merge_overrides(cfg: AppConfig, args: argparse.Namespace) -> AppConfig:
    # Serial overrides
    sc = cfg.serial
    if args.port is not None:
        sc.port = args.port
    if args.baud is not None:
        sc.baudrate = args.baud
    if args.bytesize is not None:
        sc.bytesize = args.bytesize
    if args.parity is not None:
        sc.parity = args.parity.upper()
    if args.stopbits is not None:
        sc.stopbits = args.stopbits
    if args.timeout is not None:
        sc.timeout = args.timeout

    # Logging overrides
    lc = cfg.logging
    if args.csv is not None:
        lc.csv_path = args.csv
    if args.no_append:
        lc.append = False
    if args.utc:
        lc.timestamp_tz = "utc"

    return cfg


def print_ports_and_exit() -> None:
    ports = available_ports()
    if not ports:
        console.print("[yellow]No serial ports found. Plug in your USB-RS232 adapter and try again.[/yellow]")
        sys.exit(0)
    table = Table(title="Available Serial Ports")
    table.add_column("Device")
    for d in ports:
        table.add_row(d)
    console.print(table)
    sys.exit(0)


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.list_ports:
        print_ports_and_exit()

    cfg_path = None if args.config is None else args.config
    cfg = load_config() if cfg_path is None else load_config(path=cfg_path)  # type: ignore[arg-type]
    cfg = merge_overrides(cfg, args)

    if not cfg.serial.port:
        console.print("[red]No serial port specified. Use --port or set serial.port in config.yaml.\nTry: python run.py --list-ports[/red]")
        return 2

    console.rule("Mitutoyo 6200 RS232 Reader")
    console.print(f"Port: [bold]{cfg.serial.port}[/bold]  Baud: {cfg.serial.baudrate}  Format: {cfg.serial.bytesize}{cfg.serial.parity}{cfg.serial.stopbits}")
    console.print(f"CSV: [bold]{cfg.logging.csv_path}[/bold]  Append: {cfg.logging.append}  TZ: {cfg.logging.timestamp_tz}")

    parser = Mitutoyo6200Parser(expected_unit=cfg.classification.units)

    try:
        with managed_serial(
            port=cfg.serial.port,
            baudrate=cfg.serial.baudrate,
            bytesize=cfg.serial.bytesize,
            parity=cfg.serial.parity,
            stopbits=cfg.serial.stopbits,
            timeout=cfg.serial.timeout,
        ) as ser, CsvLogger(cfg.logging) as csvlog:
            console.print("[green]Reading... Press Ctrl+C to stop.[/green]")
            while True:
                line = ser.readline()
                if not line:
                    continue
                meas = parser.parse_line(line)
                if not meas:
                    continue
                result = classify_value(meas.value, cfg.classification)

                color = "green" if result.verdict == "PASS" else ("red" if result.verdict == "FAIL" else "yellow")
                console.print(f"[{color}]value={meas.value} {meas.unit or ''}\tverdict={result.verdict}\treason={result.reason or ''}\traw=\"{meas.raw}\"[/{color}]")

                csvlog.log(meas.value, meas.unit, result.verdict, result.reason or "", meas.raw)

    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped by user.[/yellow]")
        return 0
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
