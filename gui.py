from __future__ import annotations

import sys
from pathlib import Path
import datetime as dt

from PySide6.QtCore import Qt, QUrl
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
)

from lsm6200.config import load_config
from lsm6200.simulator import MicrometerSimulator
from lsm6200.processing import process_value, classify_six_bins
from lsm6200.logging_utils import CsvLogger


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Laser Scan Micrometer DEMO")
        self.cfg = load_config()
        self.sim = MicrometerSimulator()
        self.csv_logger = None  # type: ignore
        self.standard = 0.110  # default standard before user setup
        self.session_started = False

        self._build_ui()
        self._update_category_style("#444444")
        self._prompt_measurement_setup()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Header
        title = QLabel("雷射量測 DEMO（無硬體）")
        title.setAlignment(Qt.AlignLeft)
        title.setFont(QFont("Arial", 18, QFont.Bold))
        root.addWidget(title)

        # Category display
        self.category_label = QLabel("分類：—")
        self.category_label.setAlignment(Qt.AlignCenter)
        self.category_label.setFont(QFont("Arial", 28, QFont.Bold))
        self.category_label.setAutoFillBackground(True)
        root.addWidget(self.category_label)

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
        root.addWidget(values_box)

        # Controls
        ctrl_layout = QHBoxLayout()
        self.btn_run = QPushButton("RUN 測量")
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
        root.addLayout(ctrl_layout)

        # Footer hint
        hint = QLabel("說明：每次按下 RUN 會模擬一次測量並依規則分類；CSV 輸出路徑於 config.yaml")
        hint.setStyleSheet("color: #666;")
        root.addWidget(hint)

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
    w.resize(700, 420)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
