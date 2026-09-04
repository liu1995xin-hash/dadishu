"""Headless behavioural tests for the six-switch mole game."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt

from mole_game import (
    CHANNEL_COUNT,
    HIT_SIGNAL,
    MATERIAL_FILES,
    MATERIAL_SCORES,
    MoleGameWindow,
    SERIAL_TO_TILE_INDEX,
    SerialReader,
)
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

    def put_target(self, index: int, material: str) -> None:
        self.window.target_expiry_timers[index].stop()
        self.window.targets[index] = material
        self.window.grid.show_asset(index, MATERIAL_FILES[material])

    @staticmethod
    def frame_with_hit_at_tile(index: int) -> list[int]:
        values = [0] * CHANNEL_COUNT
        values[SERIAL_TO_TILE_INDEX.index(index)] = HIT_SIGNAL
        return values

    def test_frame_parser_rejects_incomplete_and_invalid_input(self) -> None:
        self.assertEqual(SerialReader.parse_frame("0 1 0 0 0 1"), [0, 1, 0, 0, 0, 1])
        for text in ("", "0 1 0", "0 1 0 0 0 2", "0 1 0 0 0 x"):
            self.assertIsNone(SerialReader.parse_frame(text))

    def test_serial_input_order_maps_from_bottom_right_to_top_left(self) -> None:
        self.assertEqual(SERIAL_TO_TILE_INDEX, (5, 4, 3, 2, 1, 0))
        self.assertEqual(self.frame_with_hit_at_tile(5), [1, 0, 0, 0, 0, 0])
        self.assertEqual(self.frame_with_hit_at_tile(0), [0, 0, 0, 0, 0, 1])
        self.start_with_zero_baseline()
        self.window.clear_all_targets()
        self.put_target(5, "黄芩")
        self.window.register_game_frame([1, 0, 0, 0, 0, 0])
        self.assertIsNone(self.window.targets[5])

    def test_simulator_frames_are_six_bits_and_do_not_repeat_the_last_hit(self) -> None:
        last_hit: int | None = None
        for _ in range(30):
            values, hit = next_random_frame(last_hit)
            self.assertEqual(len(values), CHANNEL_COUNT)
            self.assertEqual(sum(values), HIT_SIGNAL)
            self.assertNotEqual(hit, last_hit)
            last_hit = hit

    def test_all_configured_material_images_exist(self) -> None:
        self.assertTrue(all(path.exists() for path in MATERIAL_FILES.values()))
        for material in ("黄芩", "丹参", "青蒿", "紫苏"):
            self.assertEqual(MATERIAL_SCORES[material], 10)
        self.assertEqual(MATERIAL_SCORES["大麻叶"], -5)

    def test_asset_is_stretched_to_fill_its_tile(self) -> None:
        self.window.show()
        QTest.qWait(20)
        self.window.grid.show_asset(0, MATERIAL_FILES["黄芩"])
        label = self.window.grid.asset_labels[0]
        self.assertTrue(label.hasScaledContents())
        self.assertEqual(label.geometry(), self.window.grid.asset_rect(0))

    def test_first_frame_is_only_a_baseline(self) -> None:
        self.window.start_game()
        self.window.register_game_frame([1, 0, 0, 0, 0, 0])
        self.assertEqual(self.window.score, 10)
        self.assertTrue(any(target is not None for target in self.window.targets))

    def test_only_rising_edges_score_a_target_once(self) -> None:
        self.start_with_zero_baseline()
        self.window.clear_all_targets()
        self.put_target(0, "黄芩")
        top_left_hit = self.frame_with_hit_at_tile(0)
        self.window.register_game_frame(top_left_hit)
        self.assertIsNone(self.window.targets[0])
        self.window.register_game_frame(top_left_hit)
        self.window.register_game_frame([0, 0, 0, 0, 0, 0])
        self.window.register_game_frame(top_left_hit)
        QTest.qWait(1100)
        self.assertEqual(self.window.score, 20)

    def test_mouse_click_uses_the_same_target_hit_path(self) -> None:
        self.start_with_zero_baseline()
        self.window.clear_all_targets()
        self.put_target(0, "黄芩")
        self.window.show()
        QTest.qWait(20)
        QTest.mouseClick(self.window.grid.tiles[0], Qt.MouseButton.LeftButton)
        self.assertIsNone(self.window.targets[0])
        QTest.qWait(1100)
        self.assertEqual(self.window.score, 20)

    def test_poppy_hit_causes_immediate_failure(self) -> None:
        self.start_with_zero_baseline()
        self.window.clear_all_targets()
        self.put_target(0, "罂粟花")
        self.window.register_game_frame(self.frame_with_hit_at_tile(0))
        self.assertFalse(self.window.game_active)
        self.assertEqual(self.window.grid.message_label.text(), "游戏失败")
        self.assertTrue(all(target is None for target in self.window.targets))

    def test_hemp_target_subtracts_five_after_animation(self) -> None:
        self.start_with_zero_baseline()
        self.window.clear_all_targets()
        self.put_target(0, "大麻叶")
        self.window.register_game_frame(self.frame_with_hit_at_tile(0))
        QTest.qWait(1100)
        self.assertEqual(self.window.score, 5)

    def test_empty_cell_hit_does_not_change_score_or_show_an_asset(self) -> None:
        self.start_with_zero_baseline()
        self.window.clear_all_targets()
        self.window.register_game_frame([1, 0, 0, 0, 0, 0])
        self.assertEqual(self.window.score, 10)
        self.assertFalse(self.window.grid.asset_labels[0].isVisible())

    def test_target_expiry_and_full_grid_skip(self) -> None:
        self.start_with_zero_baseline()
        self.window.clear_all_targets()
        for index in range(CHANNEL_COUNT):
            self.put_target(index, "黄芩")
        before = list(self.window.targets)
        self.window.spawn_target()
        self.assertEqual(self.window.targets, before)
        self.window.expire_target(0)
        self.assertIsNone(self.window.targets[0])
        self.assertFalse(self.window.grid.asset_labels[0].isVisible())

    def test_end_state_clears_all_targets_immediately(self) -> None:
        self.start_with_zero_baseline()
        self.window.end_game()
        self.assertEqual(self.window.targets, [None] * CHANNEL_COUNT)
        self.assertTrue(all(not label.isVisible() for label in self.window.grid.asset_labels))

    def test_manual_end_ignores_future_frames_and_space_starts_again(self) -> None:
        self.start_with_zero_baseline()
        self.window.end_game()
        self.window.register_game_frame([1, 0, 0, 0, 0, 0])
        self.assertEqual(self.window.score, 10)
        self.assertEqual(self.window.grid.message_label.text(), "游戏结束")
        self.window.handle_spacebar()
        self.assertTrue(self.window.game_active)

    def test_mouse_click_is_ignored_outside_an_active_game(self) -> None:
        self.put_target(0, "黄芩")
        self.window.handle_tile_click(0)
        self.assertEqual(self.window.targets[0], "黄芩")

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
