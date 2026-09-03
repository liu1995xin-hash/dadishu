"""Six-switch mole-game display.

The Arduino sends one line at a time, for example:
    0 1 0 0 0 1

With COM + NC wiring, 0 means released and 1 means struck/pressed. Each hit
signal keeps its corresponding square black for HIT_DISPLAY_MS milliseconds.
"""

from __future__ import annotations

import queue
import random
import sys
import threading
import time
from pathlib import Path

try:
    import serial
    from serial.tools import list_ports
    from PySide6.QtCore import QEasingCurve, QRect, QPropertyAnimation, QSequentialAnimationGroup, Qt, QTimer
    from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QFrame,
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
HIT_SIGNAL = 1  # COM -> GND and NC -> Dx: released=0, struck/pressed=1
DEFAULT_INITIAL_SCORE = 10
DEFAULT_WINNING_SCORE = 30
INITIAL_SCORE_OPTIONS = range(10, 101, 10)
WINNING_SCORE_OPTIONS = range(30, 201, 10)
GAME_OVER_SCORE = 0
VICTORY_DISPLAY_MS = 1000
TARGET_SPAWN_MS = 2000
TARGET_DISPLAY_MS = 4000
HIT_SCALE_DURATION_MS = 500
ASSET_DIRECTORY = Path(__file__).with_name("素材")
MATERIAL_SCORES = {
    "黄芩": 10,
    "黄芩(1)": 10,
    "丹参": 10,
    "青蒿": 10,
    "紫苏": 10,
    "大麻叶": -5,
}
INSTANT_FAILURE_MATERIALS = {"罂粟花"}

MATERIAL_FILES = {
    "黄芩": ASSET_DIRECTORY / "黄芩.png",
    "黄芩(1)": ASSET_DIRECTORY / "黄芩(1).png",
    "丹参": ASSET_DIRECTORY / "丹参.png",
    "青蒿": ASSET_DIRECTORY / "青蒿.png",
    "紫苏": ASSET_DIRECTORY / "紫苏.png",
    "罂粟花": ASSET_DIRECTORY / "罂粟花.png",
    "大麻叶": ASSET_DIRECTORY / "大麻叶.png",
}


class SerialReader(threading.Thread):
    """Reads serial data on a worker thread and posts valid frames to a queue."""

    def __init__(self, port: str, output: queue.Queue[tuple[str, object]]) -> None:
        super().__init__(daemon=True)
        self.port = port
        self.output = output
        self.stop_requested = threading.Event()

    def stop(self) -> None:
        self.stop_requested.set()

    def run(self) -> None:
        connection: serial.Serial | None = None
        try:
            connection = serial.Serial(self.port, BAUD_RATE, timeout=0.15)
            if self.stop_requested.is_set():
                return
            self.output.put(("connected", self.port))

            while not self.stop_requested.is_set():
                text = connection.readline().decode("utf-8", errors="replace").strip()
                values = self.parse_frame(text)
                if values is not None:
                    self.output.put(("frame", values))
        except (serial.SerialException, OSError) as exc:
            if not self.stop_requested.is_set():
                self.output.put(("error", f"串口错误：{exc}"))
        finally:
            if connection is not None:
                connection.close()
            self.output.put(("stopped", None))

    @staticmethod
    def parse_frame(text: str) -> list[int] | None:
        """Accept only one complete six-value 0/1 frame."""
        parts = text.split()
        if len(parts) != CHANNEL_COUNT or any(part not in {"0", "1"} for part in parts):
            return None
        return [int(part) for part in parts]


class SquareGrid(QWidget):
    """A 2 x 3 area whose tiles remain square at every window size."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(280, 420)
        self.setStyleSheet("background: white;")
        self.tiles: list[QFrame] = []
        self.asset_labels: list[QLabel] = []
        self.asset_animations: list[QSequentialAnimationGroup | None] = [None] * CHANNEL_COUNT

        for _index in range(CHANNEL_COUNT):
            tile = QFrame(self)
            tile.setStyleSheet("background: white;")
            self.tiles.append(tile)
            asset_label = QLabel(tile)
            asset_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            asset_label.setStyleSheet("background: transparent;")
            asset_label.hide()
            self.asset_labels.append(asset_label)

        # One border surrounds the complete 2 x 3 area; individual tiles have none.
        self.outer_border = QFrame(self)
        self.outer_border.setStyleSheet("background: transparent; border: 1px solid black;")
        self.message_label = QLabel(self)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setStyleSheet(
            "background: transparent; color: black; font-size: 36px; font-weight: bold;"
        )
        self.message_label.hide()

    def asset_rect(self, index: int, scale: float = 1.0) -> QRect:
        tile = self.tiles[index]
        side = max(int(min(tile.width(), tile.height()) * 0.72 * scale), 1)
        return QRect((tile.width() - side) // 2, (tile.height() - side) // 2, side, side)

    def show_asset(self, index: int, image_path: Path) -> None:
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            raise ValueError(f"无法加载素材图片：{image_path}")
        label = self.asset_labels[index]
        label.setPixmap(pixmap)
        label.setGeometry(self.asset_rect(index))
        label.show()
        label.raise_()

    def clear_asset(self, index: int) -> None:
        animation = self.asset_animations[index]
        if animation is not None:
            animation.stop()
            self.asset_animations[index] = None
        self.asset_labels[index].hide()
        self.asset_labels[index].clear()

    def clear_all_assets(self) -> None:
        for index in range(CHANNEL_COUNT):
            self.clear_asset(index)

    def animate_hit(self, index: int, on_finished) -> None:  # type: ignore[no-untyped-def]
        label = self.asset_labels[index]
        animation = QSequentialAnimationGroup(self)
        enlarge = QPropertyAnimation(label, b"geometry", animation)
        enlarge.setDuration(HIT_SCALE_DURATION_MS)
        enlarge.setStartValue(self.asset_rect(index))
        enlarge.setEndValue(self.asset_rect(index, 1.2))
        enlarge.setEasingCurve(QEasingCurve.Type.OutQuad)
        shrink = QPropertyAnimation(label, b"geometry", animation)
        shrink.setDuration(HIT_SCALE_DURATION_MS)
        shrink.setStartValue(self.asset_rect(index, 1.2))
        shrink.setEndValue(self.asset_rect(index))
        shrink.setEasingCurve(QEasingCurve.Type.InQuad)
        animation.addAnimation(enlarge)
        animation.addAnimation(shrink)
        animation.finished.connect(on_finished)
        self.asset_animations[index] = animation
        animation.start()

    def show_message(self, message: str) -> None:
        self.message_label.setText(message)
        self.message_label.show()
        self.message_label.raise_()

    def hide_message(self) -> None:
        self.message_label.hide()

    def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().resizeEvent(event)
        width, height = self.width(), self.height()
        margin = 18
        side = min(
            (width - 2 * margin) / 2,
            (height - 2 * margin) / 3,
        )
        side = max(int(side), 1)
        grid_width = 2 * side
        grid_height = 3 * side
        left = (width - grid_width) // 2
        top = (height - grid_height) // 2

        for index, tile in enumerate(self.tiles):
            row, column = divmod(index, 2)
            tile.setGeometry(
                left + column * side,
                top + row * side,
                side,
                side,
            )
            if self.asset_animations[index] is None:
                self.asset_labels[index].setGeometry(self.asset_rect(index))
        self.outer_border.setGeometry(left, top, grid_width, grid_height)
        self.outer_border.raise_()
        self.message_label.setGeometry(self.rect())
        self.message_label.raise_()


class MoleGameWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("打地鼠 — 六开关显示")
        self.resize(640, 900)
        self.setMinimumSize(420, 620)

        self.messages: queue.Queue[tuple[str, object]] = queue.Queue()
        self.reader: SerialReader | None = None
        self.score = DEFAULT_INITIAL_SCORE
        self.winning_score = DEFAULT_WINNING_SCORE
        self.result_state: str | None = None
        self.game_active = False
        self.previous_values = [0] * CHANNEL_COUNT
        self.awaiting_first_frame = True
        self.targets: list[str | None] = [None] * CHANNEL_COUNT
        self.target_expiry_timers: list[QTimer] = []
        self._build_ui()
        self.refresh_ports()

        self.message_timer = QTimer(self)
        self.message_timer.timeout.connect(self.process_messages)
        self.message_timer.start(20)
        self.victory_timer = QTimer(self)
        self.victory_timer.setSingleShot(True)
        self.victory_timer.timeout.connect(self.reset_to_ready)
        self.space_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self.space_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.space_shortcut.activated.connect(self.handle_spacebar)
        self.spawn_timer = QTimer(self)
        self.spawn_timer.timeout.connect(self.spawn_target)
        for index in range(CHANNEL_COUNT):
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda index=index: self.expire_target(index))
            self.target_expiry_timers.append(timer)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setStyleSheet("background: white;")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("串口："))
        self.port_box = QComboBox()
        self.port_box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        controls.addWidget(self.port_box, 1)
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.refresh_ports)
        controls.addWidget(refresh_button)
        self.connection_button = QPushButton("连接")
        self.connection_button.clicked.connect(self.toggle_connection)
        controls.addWidget(self.connection_button)
        layout.addLayout(controls)

        game_controls = QHBoxLayout()
        self.start_button = QPushButton("开始游戏")
        self.start_button.clicked.connect(self.start_game)
        game_controls.addWidget(self.start_button)
        self.end_button = QPushButton("结束游戏")
        self.end_button.clicked.connect(self.end_game)
        self.end_button.setEnabled(False)
        game_controls.addWidget(self.end_button)
        game_controls.addWidget(QLabel("初始分数："))
        self.initial_score_box = QComboBox()
        for score in INITIAL_SCORE_OPTIONS:
            self.initial_score_box.addItem(f"{score}分", score)
        self.initial_score_box.setCurrentText(f"{DEFAULT_INITIAL_SCORE}分")
        game_controls.addWidget(self.initial_score_box)
        game_controls.addWidget(QLabel("胜利分数："))
        self.winning_score_box = QComboBox()
        for score in WINNING_SCORE_OPTIONS:
            self.winning_score_box.addItem(f"{score}分", score)
        self.winning_score_box.setCurrentText(f"{DEFAULT_WINNING_SCORE}分")
        game_controls.addWidget(self.winning_score_box)
        self.score_label = QLabel()
        self.score_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.score_label.hide()
        game_controls.addWidget(self.score_label)
        game_controls.addStretch(1)
        layout.addLayout(game_controls)

        self.status_label = QLabel("未连接")
        layout.addWidget(self.status_label)
        self.grid = SquareGrid()
        layout.addWidget(self.grid, 1)

    def refresh_ports(self) -> None:
        current = self.port_box.currentText()
        ports = [item.device for item in list_ports.comports()]
        self.port_box.clear()
        self.port_box.addItems(ports)

        if current in ports:
            self.port_box.setCurrentText(current)

        if not ports:
            self.status_label.setText("未发现串口。连接开发板后点击“刷新”。")

    def toggle_connection(self) -> None:
        if self.reader is not None:
            self.disconnect()
            return

        port = self.port_box.currentText()
        if not port:
            self.status_label.setText("请先选择一个串口。")
            return

        self.status_label.setText(f"正在连接 {port}（{BAUD_RATE} 波特）…")
        self.reader = SerialReader(port, self.messages)
        self.reader.start()
        self.connection_button.setText("断开")
        self.port_box.setEnabled(False)

    def disconnect(self) -> None:
        if self.reader is not None:
            self.reader.stop()
            self.reader.join(timeout=0.5)
            self.reader = None
        self.connection_button.setText("连接")
        self.port_box.setEnabled(True)
        self.status_label.setText("已断开")

    def start_game(self) -> None:
        self.victory_timer.stop()
        initial_score = int(self.initial_score_box.currentData())
        winning_score = int(self.winning_score_box.currentData())
        if initial_score >= winning_score:
            self.status_label.setText("初始分数必须小于胜利分数。")
            return

        self.score = initial_score
        self.winning_score = winning_score
        self.previous_values = [0] * CHANNEL_COUNT
        self.awaiting_first_frame = True
        self.game_active = True
        self.clear_all_targets()
        self.grid.hide_message()
        self.score_label.setText(f"{self.score}分")
        self.score_label.show()
        self.start_button.setEnabled(False)
        self.end_button.setEnabled(True)
        self.initial_score_box.setEnabled(False)
        self.winning_score_box.setEnabled(False)
        self.spawn_target()
        self.spawn_timer.start(TARGET_SPAWN_MS)

    def end_game(self) -> None:
        self.game_active = False
        self.previous_values = [0] * CHANNEL_COUNT
        self.awaiting_first_frame = True
        self.clear_all_targets()
        self.score_label.hide()
        self.start_button.setEnabled(True)
        self.end_button.setEnabled(False)
        self.initial_score_box.setEnabled(True)
        self.winning_score_box.setEnabled(True)
        self.grid.show_message("游戏结束")

    def finish_victory(self) -> None:
        self.result_state = "victory"
        self.game_active = False
        self.previous_values = [0] * CHANNEL_COUNT
        self.awaiting_first_frame = True
        self.clear_all_targets()
        self.score_label.hide()
        self.start_button.setEnabled(False)
        self.end_button.setEnabled(False)
        self.initial_score_box.setEnabled(False)
        self.winning_score_box.setEnabled(False)
        self.grid.show_message("游戏胜利")
        self.victory_timer.start(VICTORY_DISPLAY_MS)

    def finish_failure(self) -> None:
        self.result_state = "failure"
        self.game_active = False
        self.previous_values = [0] * CHANNEL_COUNT
        self.awaiting_first_frame = True
        self.clear_all_targets()
        self.score_label.hide()
        self.start_button.setEnabled(False)
        self.end_button.setEnabled(False)
        self.initial_score_box.setEnabled(False)
        self.winning_score_box.setEnabled(False)
        self.grid.show_message("游戏失败")
        self.victory_timer.start(VICTORY_DISPLAY_MS)

    def reset_to_ready(self) -> None:
        self.result_state = None
        self.score = int(self.initial_score_box.currentData())
        self.winning_score = int(self.winning_score_box.currentData())
        self.previous_values = [0] * CHANNEL_COUNT
        self.awaiting_first_frame = True
        self.clear_all_targets()
        self.grid.hide_message()
        self.score_label.hide()
        self.start_button.setEnabled(True)
        self.end_button.setEnabled(False)
        self.initial_score_box.setEnabled(True)
        self.winning_score_box.setEnabled(True)

    def register_game_frame(self, values: list[int]) -> None:
        # The first complete frame after starting establishes the released/pressed
        # baseline. It deliberately triggers neither a score nor a hit effect.
        if self.awaiting_first_frame:
            self.previous_values = values
            self.awaiting_first_frame = False
            return

        for index, (previous, current) in enumerate(zip(self.previous_values, values)):
            if previous != HIT_SIGNAL and current == HIT_SIGNAL:
                self.hit_target(index)
                if not self.game_active:
                    break
        self.previous_values = values

    def spawn_target(self) -> None:
        if not self.game_active:
            return
        empty_indices = [index for index, target in enumerate(self.targets) if target is None]
        if not empty_indices:
            return
        index = random.choice(empty_indices)
        material = random.choice(list(MATERIAL_FILES))
        self.targets[index] = material
        self.grid.show_asset(index, MATERIAL_FILES[material])
        self.target_expiry_timers[index].start(TARGET_DISPLAY_MS)

    def expire_target(self, index: int) -> None:
        if self.targets[index] is None:
            return
        self.targets[index] = None
        self.grid.clear_asset(index)

    def hit_target(self, index: int) -> None:
        material = self.targets[index]
        if material is None:
            return
        self.targets[index] = None
        self.target_expiry_timers[index].stop()
        if material in INSTANT_FAILURE_MATERIALS:
            self.finish_failure()
            return
        score_change = MATERIAL_SCORES[material]

        def complete_hit() -> None:
            self.grid.clear_asset(index)
            if self.game_active:
                self.adjust_score(score_change)

        self.grid.animate_hit(index, complete_hit)

    def clear_all_targets(self) -> None:
        self.spawn_timer.stop()
        for timer in self.target_expiry_timers:
            timer.stop()
        self.targets = [None] * CHANNEL_COUNT
        self.grid.clear_all_assets()

    def handle_spacebar(self) -> None:
        if self.game_active:
            self.end_game()
        elif self.victory_timer.isActive():
            self.victory_timer.stop()
            self.reset_to_ready()
        else:
            self.start_game()

    def adjust_score(self, change: int) -> None:
        self.score += change
        self.score_label.setText(f"{self.score}分")
        if self.score >= self.winning_score:
            self.score = self.winning_score
            self.score_label.setText(f"{self.score}分")
            self.finish_victory()
        elif self.score <= GAME_OVER_SCORE:
            self.finish_failure()

    def process_messages(self) -> None:
        while True:
            try:
                kind, payload = self.messages.get_nowait()
            except queue.Empty:
                break

            if kind == "connected":
                self.status_label.setText(f"已连接：{payload}，{BAUD_RATE} 波特")
            elif kind == "frame":
                if self.game_active:
                    self.register_game_frame(payload)  # type: ignore[arg-type]
            elif kind == "error":
                self.status_label.setText(str(payload))
                self.reader = None
                self.connection_button.setText("连接")
                self.port_box.setEnabled(True)

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.victory_timer.stop()
        self.disconnect()
        event.accept()


if __name__ == "__main__":
    application = QApplication(sys.argv)
    window = MoleGameWindow()
    window.show()
    raise SystemExit(application.exec())
