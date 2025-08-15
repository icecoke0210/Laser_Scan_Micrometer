from __future__ import annotations

import sys
from pathlib import Path
import datetime as dt

from PySide6.QtCore import Qt, QUrl, QThread, Signal, QObject
from PySide6.QtGui import QFont, QColor, QPalette, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QGroupBox,
    QFormLayout,
    QCheckBox,
    QDialog,
    QLineEdit,
    QDialogButtonBox,
    QMessageBox,
    QComboBox,
    QTabWidget,
)

from lsm6200.config import load_config
from lsm6200.simulator import MicrometerSimulator
from lsm6200.processing import process_value, classify_six_bins
from lsm6200.logging_utils import CsvLogger
from lsm6200.serial_utils import available_ports, managed_serial
from lsm6200.protocols import Mitutoyo6200Parser
from lsm6200.classifier import classify_value


class SerialWorker(QObject):
    measurement = Signal(float, str, str, str, str)  # value, unit, verdict, reason, raw
    status = Signal(str)
    error = Signal(str)
    finished = Signal()

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self._running = False

    def start(self):
        self._running = True
        parser = Mitutoyo6200Parser(expected_unit=self.cfg.classification.units)
        try:
            with managed_serial(
                port=self.cfg.serial.port,
                baudrate=self.cfg.serial.baudrate,
                bytesize=self.cfg.serial.bytesize,
                parity=self.cfg.serial.parity,
                stopbits=self.cfg.serial.stopbits,
                timeout=self.cfg.serial.timeout,
            ) as ser, CsvLogger(self.cfg.logging) as csvlog:
                self.status.emit("connected")
                while self._running:
                    line = ser.readline()
                    if not line:
                        continue
                    meas = parser.parse_line(line)
                    if not meas:
                        continue
                    res = classify_value(meas.value, self.cfg.classification)
                    csvlog.log(meas.value, meas.unit, res.verdict, res.reason or "", meas.raw)
                    self.measurement.emit(meas.value, meas.unit or "", res.verdict, res.reason or "", meas.raw)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.status.emit("disconnected")
            self.finished.emit()

    def stop(self):
        self._running = False


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Laser Scan Micrometer")
        self.cfg = load_config()
        self.sim = MicrometerSimulator()
        self.csv_logger = None  # type: ignore
        self.standard = 0.110  # default standard before user setup
        self.session_started = False
        self.thread: QThread | None = None
        self.worker: SerialWorker | None = None
        self.live_connected = False

        self._build_ui()
        self._update_category_style("#444444")
        # Default to Live tab but without connecting; user can switch to Sim
        self._refresh_ports()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Header
        title = QLabel("雷射量測（Live / 模擬）")
        title.setAlignment(Qt.AlignLeft)
        title.setFont(QFont("Arial", 18, QFont.Bold))
        root.addWidget(title)

        # Tabs for Live/Sim
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        # Build Live tab
        live_tab = QWidget()
        live_layout = QVBoxLayout(live_tab)

        port_layout = QHBoxLayout()
        self.cmb_ports = QComboBox()
        self.btn_refresh_ports = QPushButton("重新掃描")
        self.btn_connect = QPushButton("連線")
        self.btn_disconnect = QPushButton("中止")
        self.btn_disconnect.setEnabled(False)
        port_layout.addWidget(QLabel("COM 埠："))
        port_layout.addWidget(self.cmb_ports)
        port_layout.addWidget(self.btn_refresh_ports)
        port_layout.addStretch(1)
        port_layout.addWidget(self.btn_connect)
        port_layout.addWidget(self.btn_disconnect)
        live_layout.addLayout(port_layout)

        self.live_status = QLabel("狀態：未連線")
        self.live_status.setStyleSheet("color:#666;")
        live_layout.addWidget(self.live_status)

        self.tabs.addTab(live_tab, "連線模式")

        # Build Sim tab (existing UI)
        sim_tab = QWidget()
        sim_layout = QVBoxLayout(sim_tab)

        # Category display
        self.category_label = QLabel("分類：—")
        self.category_label.setAlignment(Qt.AlignCenter)
        self.category_label.setFont(QFont("Arial", 28, QFont.Bold))
        self.category_label.setAutoFillBackground(True)
        sim_layout.addWidget(self.category_label)

        # Values box
        values_box = QGroupBox("數值顯示")
        form = QFormLayout()
        self.raw5 = QLabel("—")
        self.cut4 = QLabel("—")
        self.round3 = QLabel("—")
        form.addRow("原始值（5位小數）:", self.raw5)
        form.addRow("截斷至萬分位（4位）:", self.cut4)
        form.addRow("四捨五入至千分位（3位）:", self.round3)
        values_box.setLayout(form)
        sim_layout.addWidget(values_box)

        # Controls
        ctrl_layout = QHBoxLayout()
        self.btn_run = QPushButton("RUN 模擬")
        self.btn_run.clicked.connect(self.on_run)
        self.chk_log = QCheckBox("紀錄至 CSV")
        self.chk_log.setChecked(True)
        self.btn_run.setEnabled(False)  # enable after setup confirmed
        # View report button
        self.btn_view_report = QPushButton("查看量測報表")
        self.btn_view_report.clicked.connect(self.on_view_report)
        ctrl_layout.addWidget(self.btn_run)
        ctrl_layout.addWidget(self.chk_log)
        ctrl_layout.addWidget(self.btn_view_report)
        ctrl_layout.addStretch(1)
        sim_layout.addLayout(ctrl_layout)

        # Footer hint
        hint = QLabel("說明：Live 連線可即時接收並紀錄；模擬模式按 RUN 產生測量並依規則分類；CSV 路徑於 config.yaml")
        hint.setStyleSheet("color: #666;")
        sim_layout.addWidget(hint)

        self.tabs.addTab(sim_tab, "模擬模式")

        # Wire Live tab actions
        self.btn_refresh_ports.clicked.connect(self._refresh_ports)
        self.btn_connect.clicked.connect(self.on_connect)
        self.btn_disconnect.clicked.connect(self.on_disconnect)
        # Prompt sim measurement setup initially
        self._prompt_measurement_setup()

    def _update_category_style(self, color_hex: str):
        pal = self.category_label.palette()
        pal.setColor(QPalette.Window, QColor(color_hex))
        pal.setColor(QPalette.WindowText, QColor("white"))
        self.category_label.setPalette(pal)
        self.category_label.setAutoFillBackground(True)

    def _prompt_measurement_setup(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("量測尺寸設定")
        layout = QVBoxLayout(dlg)

        form_box = QGroupBox("請輸入要量測的尺寸（mm）")
        form = QFormLayout()
        input_size = QLineEdit(f"{self.standard:.3f}")
        input_size.setPlaceholderText("例如 0.110")
        form.addRow("標準尺寸:", input_size)
        form_box.setLayout(form)
        layout.addWidget(form_box)

        rules_label = QLabel("")
        rules_label.setWordWrap(True)
        layout.addWidget(rules_label)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(btns)

        def refresh_rules():
            try:
                val = float(input_size.text())
            except ValueError:
                rules_label.setText("請輸入有效數值，如 0.110")
                return
            s = val
            hi_limit = s + 0.008
            bin2_lo, bin2_hi = s + 0.003, s + 0.007
            bin3_lo, bin3_hi = s - 0.002, s + 0.002
            bin4_lo, bin4_hi = s - 0.007, s - 0.003
            bin5_lo, bin5_hi = s - 0.012, s - 0.008
            lo_limit = s - 0.013
            text = (
                "分類規則（基於標準尺寸）\n"
                f"1 超過上限公差: v ≥ {hi_limit:.3f}\n"
                f"2 標準+0.005: {bin2_lo:.3f} ≤ v ≤ {bin2_hi:.3f}\n"
                f"3 標準±0.002: {bin3_lo:.3f} ≤ v ≤ {bin3_hi:.3f}\n"
                f"4 標準-0.005: {bin4_lo:.3f} ≤ v ≤ {bin4_hi:.3f}\n"
                f"5 標準-0.010: {bin5_lo:.3f} ≤ v ≤ {bin5_hi:.3f}\n"
                f"6 超過下限公差: v ≤ {lo_limit:.3f}"
            )
            rules_label.setText(text)

        input_size.textChanged.connect(lambda _: refresh_rules())
        refresh_rules()

        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)

        if dlg.exec() == QDialog.Accepted:
            try:
                s = float(input_size.text())
            except ValueError:
                QMessageBox.warning(self, "輸入錯誤", "請輸入有效數值，如 0.110")
                return self._prompt_measurement_setup()
            self.standard = float(f"{s:.3f}")
            # apply standard to simulator and session CSV
            self.sim.cfg.standard = self.standard
            self._setup_session_csv()
            self.btn_run.setEnabled(True)
            self.session_started = True
        else:
            # user canceled: keep RUN disabled
            pass

    def _setup_session_csv(self):
        # New CSV file per session: size + date + start time
        start = dt.datetime.now()
        date_str = start.strftime("%Y%m%d")
        time_str = start.strftime("%H%M%S")
        size_str = f"{self.standard:.3f}mm"
        filename = f"{size_str}_{date_str}_{time_str}.csv"
        logs_dir = Path(self.cfg.logging.csv_path).parent if self.cfg.logging.csv_path else Path("logs")
        logs_dir.mkdir(parents=True, exist_ok=True)
        self.cfg.logging.csv_path = str(logs_dir / filename)
        # Start a fresh file, then append subsequent runs in this session
        # CsvLogger will write header when file is empty even in append mode
        self.cfg.logging.append = True

    def on_run(self):
        if not self.session_started:
            self._prompt_measurement_setup()
            if not self.session_started:
                return
        # Simulate a high-precision reading (5 dp)
        raw = self.sim.next_value()
        pv = process_value(raw)
        cat_res = classify_six_bins(pv.rounded_3dp, standard=self.standard)

        # Update UI
        self.raw5.setText(f"{pv.raw_5dp:.5f} mm")
        self.cut4.setText(f"{pv.cut_4dp:.4f} mm")
        self.round3.setText(f"{pv.rounded_3dp:.3f} mm")
        self.category_label.setText(f"分類：{cat_res.category.code} - {cat_res.category.name}  ({cat_res.reason})")
        self._update_category_style(cat_res.category.color)

        # Optional CSV log
        if self.chk_log.isChecked():
            from lsm6200.logging_utils import CsvLogger
            try:
                with CsvLogger(self.cfg.logging) as log:
                    log.log_categorized(
                        value_3dp=pv.rounded_3dp,
                        category_code=cat_res.category.code,
                        unit="mm",
                        reason=cat_res.reason,
                        raw=f"raw={pv.raw_5dp:.5f}",
                    )
            except Exception:
                pass

    # Live mode helpers
    def _refresh_ports(self):
        try:
            ports = available_ports()
        except Exception:
            ports = []
        current = self.cfg.serial.port or ""
        self.cmb_ports.clear()
        for p in ports:
            self.cmb_ports.addItem(p)
        if current:
            idx = self.cmb_ports.findText(current)
            if idx >= 0:
                self.cmb_ports.setCurrentIndex(idx)
        self.live_status.setText("狀態：待連線" if ports else "狀態：未找到可用 COM")

    def on_connect(self):
        if self.live_connected:
            return
        port = self.cmb_ports.currentText().strip()
        if not port:
            QMessageBox.warning(self, "未選擇 COM", "請先選擇可用的 COM 埠")
            return
        self.cfg.serial.port = port
        # Start worker thread
        self.thread = QThread()
        self.worker = SerialWorker(self.cfg)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.start)
        self.worker.measurement.connect(self._on_live_measurement)
        self.worker.status.connect(self._on_live_status)
        self.worker.error.connect(self._on_live_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._on_thread_finished)
        self.thread.start()
        self.btn_connect.setEnabled(False)
        self.btn_disconnect.setEnabled(True)
        self.live_status.setText(f"狀態：連線中 ({port})")

    def on_disconnect(self):
        if self.worker:
            self.worker.stop()
        self.btn_disconnect.setEnabled(False)

    def _on_live_measurement(self, value: float, unit: str, verdict: str, reason: str, raw: str):
        # Map verdict to color similar to CLI
        color = "#2e7d32" if verdict == "PASS" else ("#c62828" if verdict == "FAIL" else "#f9a825")
        self.category_label.setText(f"分類：{verdict}  ({reason})")
        self._update_category_style(color)
        # Update numeric labels (unit assumes mm unless otherwise provided)
        self.raw5.setText(f"{value:.5f} {unit or 'mm'}")
        self.cut4.setText(f"{value:.4f} {unit or 'mm'}")
        self.round3.setText(f"{value:.3f} {unit or 'mm'}")

    def _on_live_status(self, s: str):
        if s == "connected":
            self.live_connected = True
            self.live_status.setText(f"狀態：已連線 ({self.cfg.serial.port})")
        elif s == "disconnected":
            self.live_connected = False
            self.live_status.setText("狀態：未連線")
            self.btn_connect.setEnabled(True)
            self.btn_disconnect.setEnabled(False)

    def _on_live_error(self, msg: str):
        QMessageBox.critical(self, "連線錯誤", msg)

    def _on_thread_finished(self):
        if self.thread:
            self.thread.deleteLater()
            self.thread = None
        self.worker = None

    def on_view_report(self):
        """Open the current session CSV if available; otherwise open the logs directory.
        """
        try:
            csv_path = getattr(self.cfg.logging, "csv_path", "")
        except Exception:
            csv_path = ""

        target = None
        if csv_path:
            p = Path(csv_path)
            if p.exists():
                target = p
            else:
                target = p.parent
        else:
            target = Path("logs")

        try:
            target.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        # Open with system default app (Finder on macOS)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.resolve())))


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(800, 520)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
