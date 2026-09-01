# 版本记录

本项目从 `v0.4.0` 起使用 Git 管理。每次功能变更应同时更新本文件、README 中的用户行为说明，并提交一个独立 Git 提交。

## v0.5.1 — 游戏逻辑自动化测试

- 新增 `test_game_logic.py` 无界面行为测试，覆盖串口帧校验、模拟帧、首帧基准、上升沿计分、视觉恢复、结束、胜利、失败、空格跳过和分数配置校验。

对应代码：`test_game_logic.py`。

## v0.5.0 — 无界面串口模拟

- `serial_signal_simulator.py` 新增 `--headless` 模式，可不打开 Qt 窗口直接向指定串口发送随机六位帧。
- 新增 `--port`、`--interval-ms` 与 `--count` 参数；模拟器图形界面与无界面模式使用同一套随机帧生成逻辑。

对应代码：`serial_signal_simulator.py` 的 `next_random_frame()`、`run_headless()` 与命令行参数入口。

## v0.4.0 — 可配置分数与结果状态（当前版本）

- 初始分数下拉框：10～100 分，每 10 分一档，默认 10 分。
- 胜利分数下拉框：30～200 分，每 10 分一档，默认 30 分。
- 开始时校验初始分数必须小于胜利分数；游戏中锁定两个选择框。
- 达到胜利分数时显示“游戏胜利”1 秒；分数小于等于 0 时显示“游戏失败”1 秒。
- 胜利或失败提示期间按空格可跳过等待，回到开始前状态。

对应代码：`mole_game.py` 的分数常量（44～48 行）、`MoleGameWindow._build_ui()`（203～254 行）、`start_game()`（293～313 行）、`finish_victory()`（327～339 行）、`finish_failure()`（341～353 行）、`handle_spacebar()`（385～392 行）与 `adjust_score()`（394～405 行）。

## v0.3.0 — 基础游戏流程

- 新增开始、结束、得分显示与中央结果文字。
- 开始后首个完整帧仅作为状态基准；后续每个格子只在 `0 → 1` 时加 1 分。
- 游戏结束时忽略串口命中；空格可开始或结束游戏。

对应代码：`mole_game.py` 的 `start_game()`、`end_game()`、`register_game_frame()` 与 `handle_spacebar()`。

## v0.2.0 — Arduino Mega 2560 与命中视觉调整

- 串口波特率改为 115200，开发板改为 Arduino Mega 2560。
- 移除旧开发板的硬编码端口偏好，端口由运行时刷新后选择。
- 背景与未命中格改为白色；命中格改为黑色，并按最后一次 `1` 保持 1 秒。
- 增加 `serial_signal_simulator.py` 用于独立串口模拟。

对应代码：`mole_game.py` 的通信与视觉常量、`SquareGrid`；`serial_signal_simulator.py`；README 与 PROGRAM_HANDOFF 的协议说明。

## v0.1.0 — 初始六开关显示（Git 管理前的基线）

- 严格接收一行六位 `0/1` 串口帧，映射到固定的 2 列 × 3 行格子。
- 后台串口线程通过队列向 Qt 主线程传递有效帧。
- 使用 COM + NC 接线语义：`1` 为命中信号。

对应代码：`mole_game.py` 的 `SerialReader`、`SquareGrid` 和 `MoleGameWindow`。
