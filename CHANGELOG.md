# 版本记录

本项目从 `v0.4.0` 起使用 Git 管理。每次功能变更应同时更新本文件、README 中的用户行为说明，并提交一个独立 Git 提交。

## v0.7.1 — 设置下拉框定位当前项

- 设置面板的下拉列表展开时，会自动滚动并高亮当前已选配置。

对应代码：`mole_game.py` 的 `CurrentSelectionComboBox.showPopup()`。

## v0.7.0 — 可配置目标生成间隔

- 设置面板新增“生成间隔”下拉框，可选 0.5～5.0 秒、每 0.5 秒一档，默认 2.0 秒。
- 每局开始时读取并锁定生成间隔；该设置随本地配置文件保存和恢复。

对应代码：`mole_game.py` 的 `TARGET_SPAWN_INTERVAL_OPTIONS_MS`、`target_spawn_interval_box` 与 `active_target_spawn_interval_ms`。

## v0.6.9 — 命中特效期间锁定格子

- 普通药材命中后，格子在 0.6 秒缩放动画期间标记为结算中。
- 结算中的格子不能随机生成新目标；动画结束清图后才重新可用，避免旧动画清除新目标图片。

对应代码：`mole_game.py` 的 `resolving_target_indices`、`spawn_target()`、`hit_target()` 与 `clear_all_targets()`。

## v0.6.8 — 缩短命中特效

- 命中后放大与缩小阶段均调整为 0.3 秒，总特效时长为 0.6 秒。
- 缩小动画结束时立即清除素材并恢复为空白格；自动化测试覆盖这一时点。

对应代码：`mole_game.py` 的 `HIT_SCALE_DURATION_MS`、`SquareGrid.animate_hit()` 与 `MoleGameWindow.hit_target()`。

## v0.6.7 — 固定位置的本地配置记忆

- 配置文件固定为当前 Windows 用户的 `%LOCALAPPDATA%\MedicinalMoleGame\settings.json`，不依赖 `.exe` 或项目文件夹位置。
- 首次启动自动创建默认配置；后续启动恢复串口选择、初始/胜利分数和各药材分数。
- 每次调整设置后即时原子写入配置文件，单局内仍使用开始时冻结的药材分数。

对应代码：`mole_game.py` 的 `default_config_path()`、`load_config()`、`apply_saved_config()` 与 `save_config()`。

## v0.6.6 — 折叠式配置与自定义药材分数

- 串口连接、初始分数、胜利分数收纳进标题旁“设置”折叠面板；主界面保留游戏操作和方格。
- 新增“药材分数设置”：每个现有药材可选 `-999`（直接失败）、`-20`～`-1` 或 `+1`～`+20` 分，不含 `0`。
- 每局开始时读取并锁定药材分数设置；游戏结束或结果复位后才能修改。

对应代码：`mole_game.py` 的设置面板、`MATERIAL_SCORE_OPTIONS`、`active_material_scores` 与 `set_score_settings_enabled()`。

## v0.6.5 — 鼠标点击命中模拟

- 游戏进行中，鼠标左键点击任一格子会调用与串口有效命中相同的处理流程。
- 素材图层不再拦截鼠标点击；非游戏状态下点击不产生效果。

对应代码：`mole_game.py` 的 `ClickableTile`、`SquareGrid.tile_clicked` 与 `MoleGameWindow.handle_tile_click()`。

## v0.6.4 — 六路输入顺序重映射

- 串口第 1～6 位改为依次触发：右下、左下、右中、左中、右上、左上。
- 增加映射自动化测试，并移除未重新确认的旧 Arduino 引脚编号说明。

对应代码：`mole_game.py` 的 `SERIAL_TO_TILE_INDEX` 与 `register_game_frame()`。

## v0.6.3 — 素材铺满格子

- 药材素材改为直接拉伸至填满所属格子的全部宽高，不保持原始长宽比。
- 命中时的放大、缩小动画沿用同一显示方式。
- 根据当前素材目录移除已不存在的 `黄芩(1).png` 配置，避免随机生成时加载失败。

对应代码：`mole_game.py` 的 `SquareGrid.asset_rect()` 与素材标签的 `setScaledContents(True)`。

## v0.6.2 — 药材分数调整

- 黄芩、丹参、青蒿、紫苏及其他正常药材命中统一加 10 分。
- 大麻叶命中改为减 5 分；罂粟花命中直接失败并立即清场。

对应代码：`mole_game.py` 的 `MATERIAL_SCORES`、`INSTANT_FAILURE_MATERIALS` 与 `hit_target()`。

## v0.6.1 — 直接药材素材映射

- 黄芩改为直接使用 `素材/黄芩.png`，不再把其他药材图片替代为黄芩。
- 素材目录新增丹参、青蒿、紫苏及额外黄芩图片；未定义分数规则的药材暂不参与随机生成。

对应代码：`mole_game.py` 的 `MATERIAL_FILES`。

## v0.6.0 — 药材目标与有效命中

- 新增药材目标机制：开局立即生成一个目标，之后每 2 秒随机向空白格生成；目标显示 4 秒后清除，满格时跳过生成。
- 使用 `素材` 目录中同名的黄芩、罂粟花和大麻叶图片，分数分别为 +5、-5、-20。
- 仅命中有目标的格子才处理；目标被命中后禁止重复得分，执行 1.2 倍放大 0.5 秒、缩回 0.5 秒的动画，再清除和结算。
- 手动结束、胜利与失败均立即停止目标生成并清除所有图片。
- 自动化测试扩展至 11 项，包含空白格、目标到期、满格跳过、有效命中与结束清场。

对应代码：`mole_game.py` 的 `SquareGrid` 素材显示与动画方法，以及 `MoleGameWindow` 的目标生成、到期、命中和清场方法；`test_game_logic.py`。

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
