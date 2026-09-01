"""Headless behavioural tests for the six-switch mole game."""

from __future__ import annotations

import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from mole_game import CHANNEL_COUNT, HIT_SIGNAL, MoleGameWindow, SerialReader
from serial_signal_simulator import next_random_frame


class MoleGameLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.window = MoleGameWindow()

    def tearDown(self) -> None:
        self.window.close()

    def start_with_zero_baseline(self) -> None:
        self.window.start_game()
        self.window.register_game_frame([0] * CHANNEL_COUNT)

    def test_frame_parser_rejects_incomplete_and_invalid_input(self) -> None:
        self.assertEqual(SerialReader.parse_frame("0 1 0 0 0 1"), [0, 1, 0, 0, 0, 1])
        for text in ("", "0 1 0", "0 1 0 0 0 2", "0 1 0 0 0 x"):
            self.assertIsNone(SerialReader.parse_frame(text))

    def test_simulator_frames_are_six_bits_and_do_not_repeat_the_last_hit(self) -> None:
        last_hit: int | None = None
        for _ in range(30):
            values, hit = next_random_frame(last_hit)
            self.assertEqual(len(values), CHANNEL_COUNT)
            self.assertEqual(sum(values), HIT_SIGNAL)
            self.assertNotEqual(hit, last_hit)
            last_hit = hit

    def test_first_frame_is_only_a_baseline(self) -> None:
        self.window.start_game()
        self.window.register_game_frame([1, 0, 0, 0, 0, 0])
        self.assertEqual(self.window.score, 10)
        self.assertEqual(self.window.grid.hit_until[0], 0.0)

    def test_only_rising_edges_score_and_refresh_the_visual_hit(self) -> None:
        self.start_with_zero_baseline()
        self.window.register_game_frame([1, 0, 0, 0, 0, 0])
        self.assertEqual(self.window.score, 11)
        self.assertGreater(self.window.grid.hit_until[0], time.monotonic())
        self.window.register_game_frame([1, 0, 0, 0, 0, 0])
        self.assertEqual(self.window.score, 11)
        self.window.register_game_frame([0, 0, 0, 0, 0, 0])
        self.window.register_game_frame([1, 0, 0, 0, 0, 0])
        self.assertEqual(self.window.score, 12)

    def test_visual_hit_returns_to_white_after_its_window(self) -> None:
        self.start_with_zero_baseline()
        self.window.register_game_frame([1, 0, 0, 0, 0, 0])
        self.window.grid.hit_until[0] = time.monotonic() - 0.01
        self.window.grid.refresh_colours()
        self.assertIn("background: white", self.window.grid.tiles[0].styleSheet())

    def test_manual_end_ignores_future_frames_and_space_starts_again(self) -> None:
        self.start_with_zero_baseline()
        self.window.end_game()
        self.window.register_game_frame([1, 0, 0, 0, 0, 0])
        self.assertEqual(self.window.score, 10)
        self.assertEqual(self.window.grid.message_label.text(), "游戏结束")
        self.window.handle_spacebar()
        self.assertTrue(self.window.game_active)

    def test_winning_score_shows_result_and_space_skips_to_ready(self) -> None:
        self.start_with_zero_baseline()
        self.window.adjust_score(20)
        self.assertFalse(self.window.game_active)
        self.assertTrue(self.window.victory_timer.isActive())
        self.assertEqual(self.window.grid.message_label.text(), "游戏胜利")
        self.window.handle_spacebar()
        self.assertFalse(self.window.game_active)
        self.assertFalse(self.window.victory_timer.isActive())
        self.assertFalse(self.window.grid.message_label.isVisible())

    def test_zero_score_shows_failure_and_space_skips_to_ready(self) -> None:
        self.start_with_zero_baseline()
        self.window.adjust_score(-10)
        self.assertFalse(self.window.game_active)
        self.assertTrue(self.window.victory_timer.isActive())
        self.assertEqual(self.window.grid.message_label.text(), "游戏失败")
        self.window.handle_spacebar()
        self.assertFalse(self.window.game_active)
        self.assertFalse(self.window.victory_timer.isActive())
        self.assertFalse(self.window.grid.message_label.isVisible())

    def test_invalid_score_configuration_does_not_start_a_game(self) -> None:
        self.window.initial_score_box.setCurrentText("100分")
        self.window.winning_score_box.setCurrentText("30分")
        self.window.start_game()
        self.assertFalse(self.window.game_active)
        self.assertEqual(self.window.status_label.text(), "初始分数必须小于胜利分数。")


if __name__ == "__main__":
    unittest.main(verbosity=2)
