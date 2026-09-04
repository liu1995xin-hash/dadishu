"""Headless behavioural tests for the six-switch mole game."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt

from mole_game import (
    CHANNEL_COUNT,
    DEFAULT_GAME_DURATION_SECONDS,
    GAME_DURATION_OPTIONS_SECONDS,
    HIT_SIGNAL,
    MATERIAL_FILES,
    MATERIAL_SCORE_OPTIONS,
    MATERIAL_SCORES,
    MoleGameWindow,
    SERIAL_TO_TILE_INDEX,
    SerialReader,
    TARGET_SPAWN_INTERVAL_OPTIONS_MS,
    default_config_path,
)
from serial_signal_simulator import next_random_frame


class MoleGameLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_directory.name) / "settings.json"
        self.window = MoleGameWindow(config_path=self.config_path)

    def tearDown(self) -> None:
        self.window.close()
        self.temp_directory.cleanup()

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
        self.assertEqual(MATERIAL_SCORES["罂粟花"], -999)

    def test_default_config_path_is_absolute_and_not_tied_to_the_program_folder(self) -> None:
        self.assertTrue(default_config_path().is_absolute())
        self.assertNotEqual(default_config_path().parent, Path.cwd())

    def test_config_file_is_created_updated_and_restored(self) -> None:
        self.assertTrue(self.config_path.exists())
        self.window.initial_score_box.setCurrentIndex(self.window.initial_score_box.findData(20))
        self.window.winning_score_box.setCurrentIndex(self.window.winning_score_box.findData(50))
        self.window.target_spawn_interval_box.setCurrentIndex(
            self.window.target_spawn_interval_box.findData(3500)
        )
        self.window.game_duration_box.setCurrentIndex(self.window.game_duration_box.findData(50))
        hemp_box = self.window.material_score_boxes["大麻叶"]
        hemp_box.setCurrentIndex(hemp_box.findData(7))
        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["initial_score"], 20)
        self.assertEqual(saved["winning_score"], 50)
        self.assertEqual(saved["target_spawn_interval_ms"], 3500)
        self.assertEqual(saved["game_duration_seconds"], 50)
        self.assertEqual(saved["material_scores"]["大麻叶"], 7)

        self.window.close()
        self.window = MoleGameWindow(config_path=self.config_path)
        self.assertEqual(self.window.initial_score_box.currentData(), 20)
        self.assertEqual(self.window.winning_score_box.currentData(), 50)
        self.assertEqual(self.window.target_spawn_interval_box.currentData(), 3500)
        self.assertEqual(self.window.game_duration_box.currentData(), 50)
        self.assertEqual(self.window.material_score_boxes["大麻叶"].currentData(), 7)

    def test_target_spawn_interval_options_are_saved_and_locked_for_a_game(self) -> None:
        expected_options = list(range(500, 5001, 500))
        self.assertEqual(list(TARGET_SPAWN_INTERVAL_OPTIONS_MS), expected_options)
        interval_box = self.window.target_spawn_interval_box
        self.assertEqual(
            [interval_box.itemData(index) for index in range(interval_box.count())],
            expected_options,
        )
        interval_box.setCurrentIndex(interval_box.findData(500))
        self.window.start_game()
        self.assertEqual(self.window.active_target_spawn_interval_ms, 500)
        self.assertEqual(self.window.spawn_timer.interval(), 500)
        self.assertFalse(interval_box.isEnabled())
        self.window.end_game()
        self.assertTrue(interval_box.isEnabled())

    def test_game_duration_options_are_saved_locked_and_displayed_above_the_title(self) -> None:
        expected_options = [20, 30, 40, 50, 60]
        self.assertEqual(list(GAME_DURATION_OPTIONS_SECONDS), expected_options)
        duration_box = self.window.game_duration_box
        self.assertEqual(
            [duration_box.itemData(index) for index in range(duration_box.count())],
            expected_options,
        )
        self.assertEqual(duration_box.currentData(), DEFAULT_GAME_DURATION_SECONDS)
        self.assertEqual(self.window.countdown_label.text(), "剩余 30秒")

        duration_box.setCurrentIndex(duration_box.findData(20))
        self.assertEqual(self.window.countdown_label.text(), "剩余 20秒")
        self.window.start_game()
        self.assertEqual(self.window.active_game_duration_seconds, 20)
        self.assertTrue(self.window.countdown_timer.isActive())
        self.assertFalse(duration_box.isEnabled())
        QTest.qWait(1200)
        self.assertEqual(self.window.countdown_label.text(), "剩余 19秒")
        self.window.end_game()
        self.assertFalse(self.window.countdown_timer.isActive())
        self.assertTrue(duration_box.isEnabled())
        self.assertEqual(self.window.countdown_label.text(), "剩余 20秒")

    def test_countdown_expiry_ends_and_clears_the_game(self) -> None:
        self.start_with_zero_baseline()
        self.assertTrue(self.window.countdown_timer.isActive())
        self.window.game_deadline = 0.0
        self.window.update_countdown()
        self.assertFalse(self.window.game_active)
        self.assertFalse(self.window.countdown_timer.isActive())
        self.assertEqual(self.window.countdown_label.text(), "剩余 0秒")
        self.assertEqual(self.window.grid.message_label.text(), "游戏结束")
        self.assertTrue(all(target is None for target in self.window.targets))

    def test_opened_setting_dropdown_highlights_and_reveals_its_current_value(self) -> None:
        self.window.show()
        QTest.qWait(20)
        score_box = self.window.material_score_boxes["黄芩"]
        score_box.setCurrentIndex(score_box.findData(20))
        score_box.showPopup()
        QTest.qWait(20)
        self.assertEqual(score_box.view().currentIndex().row(), score_box.currentIndex())
        score_box.hidePopup()

    def test_score_settings_are_collapsed_and_expose_the_exact_requested_options(self) -> None:
        self.assertTrue(self.window.settings_panel.isHidden())
        self.window.settings_button.click()
        self.assertFalse(self.window.settings_panel.isHidden())
        self.assertTrue(self.window.material_settings_panel.isHidden())
        self.window.material_settings_button.click()
        self.assertFalse(self.window.material_settings_panel.isHidden())
        expected_options = [-999, *range(-20, 0), *range(1, 21)]
        self.assertEqual(list(MATERIAL_SCORE_OPTIONS), expected_options)
        for score_box in self.window.material_score_boxes.values():
            self.assertEqual(
                [score_box.itemData(index) for index in range(score_box.count())],
                expected_options,
            )

    def test_material_scores_are_locked_for_a_game_and_read_at_start(self) -> None:
        score_box = self.window.material_score_boxes["黄芩"]
        score_box.setCurrentIndex(score_box.findData(-20))
        self.window.start_game()
        self.assertEqual(self.window.active_material_scores["黄芩"], -20)
        self.assertFalse(score_box.isEnabled())
        self.window.end_game()
        self.assertTrue(score_box.isEnabled())

    def test_configuring_any_material_as_minus_999_causes_direct_failure(self) -> None:
        score_box = self.window.material_score_boxes["黄芩"]
        score_box.setCurrentIndex(score_box.findData(-999))
        self.start_with_zero_baseline()
        self.window.clear_all_targets()
        self.put_target(0, "黄芩")
        self.window.handle_tile_click(0)
        self.assertFalse(self.window.game_active)
        self.assertEqual(self.window.grid.message_label.text(), "游戏失败")

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
        QTest.qWait(700)
        self.assertEqual(self.window.score, 20)
        self.assertFalse(self.window.grid.asset_labels[0].isVisible())

    def test_mouse_click_uses_the_same_target_hit_path(self) -> None:
        self.start_with_zero_baseline()
        self.window.clear_all_targets()
        self.put_target(0, "黄芩")
        self.window.show()
        QTest.qWait(20)
        QTest.mouseClick(self.window.grid.tiles[0], Qt.MouseButton.LeftButton)
        self.assertIsNone(self.window.targets[0])
        QTest.qWait(700)
        self.assertEqual(self.window.score, 20)
        self.assertFalse(self.window.grid.asset_labels[0].isVisible())

    def test_asset_is_cleared_when_the_0_6_second_hit_animation_finishes(self) -> None:
        self.start_with_zero_baseline()
        self.window.clear_all_targets()
        self.put_target(0, "黄芩")
        self.window.show()
        QTest.qWait(20)
        self.window.handle_tile_click(0)
        QTest.qWait(450)
        self.assertTrue(self.window.grid.asset_labels[0].isVisible())
        QTest.qWait(250)
        self.assertFalse(self.window.grid.asset_labels[0].isVisible())

    def test_resolving_tile_cannot_receive_a_new_target_until_its_animation_ends(self) -> None:
        self.start_with_zero_baseline()
        self.window.clear_all_targets()
        self.put_target(0, "黄芩")
        self.window.handle_tile_click(0)
        self.assertIn(0, self.window.resolving_target_indices)
        with patch("mole_game.random.choice", side_effect=[1, "黄芩"]):
            self.window.spawn_target()
        self.assertIsNone(self.window.targets[0])
        self.assertEqual(self.window.targets[1], "黄芩")

        QTest.qWait(700)
        self.assertNotIn(0, self.window.resolving_target_indices)
        with patch("mole_game.random.choice", side_effect=[0, "黄芩"]):
            self.window.spawn_target()
        self.assertEqual(self.window.targets[0], "黄芩")

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
        QTest.qWait(700)
        self.assertEqual(self.window.score, 5)
        self.assertFalse(self.window.grid.asset_labels[0].isVisible())

    def test_non_terminal_hit_shows_the_score_change_until_its_animation_completes(self) -> None:
        self.start_with_zero_baseline()
        self.window.clear_all_targets()
        self.put_target(0, "大麻叶")
        self.window.show()
        QTest.qWait(20)
        self.window.handle_tile_click(0)
        feedback_label = self.window.grid.score_change_labels[0]
        self.assertTrue(feedback_label.isVisible())
        self.assertEqual(feedback_label.text(), "-5分")
        QTest.qWait(700)
        self.assertFalse(feedback_label.isVisible())
        self.assertEqual(self.window.score, 5)

    def test_direct_failure_does_not_show_a_score_change(self) -> None:
        self.start_with_zero_baseline()
        self.window.clear_all_targets()
        self.put_target(0, "罂粟花")
        self.window.handle_tile_click(0)
        self.assertFalse(self.window.grid.score_change_labels[0].isVisible())

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
