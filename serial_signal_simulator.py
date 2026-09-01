"""Six-channel serial signal simulator for the mole-game display.

Every second, the simulator sends one complete frame containing exactly one
``1`` and five ``0`` values.  For example::

    0 0 1 0 0 0

Use the sender end of a virtual serial-port pair here, and select the paired
receiver end in ``mole_game.py``.
"""

from __future__ import annotations

import argparse
import random
import sys
import time

try:
    import serial
    from serial.tools import list_ports
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:
    raise SystemExit(
        "缺少依赖。请先在终端运行：\n"
        f"{sys.executable} -m pip install -r requirements.txt"
    ) from exc


BAUD_RATE = 115200
CHANNEL_COUNT = 6
FRAME_INTERVAL_MS = 1000


def next_random_frame(last_hit_index: int | None) -> tuple[list[int], int]:
    """Return one six-value frame whose hit position differs from the prior one."""
    choices = [index for index in range(CHANNEL_COUNT) if index != last_hit_index]
    hit_index = random.choice(choices)
    values = [0] * CHANNEL_COUNT
    values[hit_index] = 1
    return values, hit_index


def run_headless(port: str, interval_ms: int, count: int) -> None:
    """Write random frames without creating a Qt window; count=0 runs until Ctrl+C."""
    if interval_ms <= 0:
        raise ValueError("发送间隔必须大于 0 ms。")
    if count < 0:
        raise ValueError("发送帧数不能小于 0。")

    print(f"无界面模拟已启动：{port}，{BAUD_RATE} 波特，每 {interval_ms} ms 发送一帧。")
    last_hit_index: int | None = None
    sent = 0
    try:
        with serial.Serial(port, BAUD_RATE, write_timeout=1) as connection:
            while count == 0 or sent < count:
                values, last_hit_index = next_random_frame(last_hit_index)
                frame = " ".join(map(str, values))
                connection.write(f"{frame}\n".encode("ascii"))
                connection.flush()
                sent += 1
                print(f"已发送 {sent}: {frame}（第 {last_hit_index + 1} 位为 1）")
                if count == 0 or sent < count:
                    time.sleep(interval_ms / 1000)
    except KeyboardInterrupt:
        print("模拟已由用户停止。")
    except (serial.SerialException, OSError) as exc:
        raise SystemExit(f"串口错误：{exc}") from exc


class SerialSignalSimulatorWindow(QMainWindow):
    """Writes one randomly selected hit frame per second to a serial port."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("打地鼠 — 串口信号模拟器")
        self.setMinimumWidth(500)

        self.connection: serial.Serial | None = None
        self.last_hit_index: int | None = None
        self.send_timer = QTimer(self)
        self.send_timer.timeout.connect(self.send_random_frame)

        self._build_ui()
        self.refresh_ports()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("发送端串口："))
        self.port_box = QComboBox()
        self.port_box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        controls.addWidget(self.port_box, 1)
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.refresh_ports)
        controls.addWidget(self.refresh_button)
        self.connection_button = QPushButton("开始模拟")
        self.connection_button.clicked.connect(self.toggle_simulation)
        controls.addWidget(self.connection_button)
        layout.addLayout(controls)

        layout.addWidget(QLabel("发送规则：每 1 秒随机一位为 1，其余五位为 0。"))
        layout.addWidget(QLabel("数据格式：0 0 0 0 0 0（空格分隔，换行结束）"))
        self.status_label = QLabel("未开始")
        layout.addWidget(self.status_label)
        self.frame_label = QLabel("最近发送：无")
        layout.addWidget(self.frame_label)

    def refresh_ports(self) -> None:
        current = self.port_box.currentText()
        ports = [item.device for item in list_ports.comports()]
        self.port_box.clear()
        self.port_box.addItems(ports)
        if current in ports:
            self.port_box.setCurrentText(current)
        if not ports:
            self.status_label.setText("未发现串口。请创建或连接可用的串口后点击“刷新”。")

    def toggle_simulation(self) -> None:
        if self.connection is not None:
            self.stop_simulation("已停止")
            return

        port = self.port_box.currentText()
        if not port:
            self.status_label.setText("请先选择一个发送端串口。")
            return

        try:
            self.connection = serial.Serial(port, BAUD_RATE, write_timeout=1)
        except (serial.SerialException, OSError) as exc:
            self.status_label.setText(f"无法打开 {port}：{exc}")
            return

        self.port_box.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.connection_button.setText("停止模拟")
        self.status_label.setText(f"正在向 {port} 发送：{BAUD_RATE} 波特，每秒 1 帧")
        self.send_random_frame()
        self.send_timer.start(FRAME_INTERVAL_MS)

    def send_random_frame(self) -> None:
        if self.connection is None:
            return

        values, hit_index = next_random_frame(self.last_hit_index)
        self.last_hit_index = hit_index
        frame = " ".join(map(str, values))

        try:
            self.connection.write(f"{frame}\n".encode("ascii"))
            self.connection.flush()
        except (serial.SerialException, OSError) as exc:
            self.stop_simulation(f"串口写入错误：{exc}")
            return

        self.frame_label.setText(f"最近发送：{frame}（第 {hit_index + 1} 位为 1）")

    def stop_simulation(self, status: str) -> None:
        self.send_timer.stop()
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        self.port_box.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.connection_button.setText("开始模拟")
        self.status_label.setText(status)

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.stop_simulation("已停止")
        event.accept()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="六路打地鼠串口信号模拟器")
    parser.add_argument("--headless", action="store_true", help="不打开窗口，直接向指定串口发送模拟帧")
    parser.add_argument("--port", help="无界面模式的发送端串口，例如 COM10")
    parser.add_argument("--interval-ms", type=int, default=FRAME_INTERVAL_MS, help="发送间隔毫秒数，默认 1000")
    parser.add_argument("--count", type=int, default=0, help="发送帧数；0 表示持续发送，默认 0")
    arguments = parser.parse_args()

    if arguments.headless:
        if not arguments.port:
            parser.error("--headless 必须同时指定 --port。")
        run_headless(arguments.port, arguments.interval_ms, arguments.count)
        raise SystemExit(0)

    application = QApplication(sys.argv)
    window = SerialSignalSimulatorWindow()
    window.show()
    raise SystemExit(application.exec())
