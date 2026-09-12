# Цифровой двойник HSL25 — сборка и запуск

Репозиторий содержит цифровой двойник робота HSL25 (kobuki + Livox
MID-360) для симуляции в Gazebo — **5 ROS2-пакетов** в одной папке.
Инструкция для тех, кто получил доступ к этому репозиторию.

Обоснования решений, найденные баги в сторонних плагинах и что ещё не
готово — `hsl_description/CLAUDE.md`, здесь только то, что нужно, чтобы
собрать и запустить.

## 1. Склонировать

```bash
git clone <URL этого репозитория> ~/ros2_ws/src/hsl25-digital-twin
```

(если у вас ещё нет `~/ros2_ws` — сначала `mkdir -p ~/ros2_ws/src`)

Внутри — 5 пакетов: `hsl_description/`, `ros2_livox_simulation/`,
`livox_ros_driver2/`, `kobuki_ros_interfaces/`, `robot_b_detector/`
(детекция второго робота в облаке точек, задача HSL26 — см. п.9). Не
имеет значения, что они лежат на один уровень глубже, чем обычно у
пакетов в `src/` — `colcon` находит их рекурсивно.

⚠️ Если у вас в этом же workspace ТАКЖЕ будет лежать `hackaton/hsl25-master`
(архив организаторов, скачанный отдельно) — положите рядом пустой файл
`hackaton/COLCON_IGNORE`. Иначе colcon найдёт внутри архива ещё один
пакет `livox_ros_driver2` и упадёт на конфликте имён — собрать его всё
равно нельзя, ему нужен физический SDK лидара.

## 2. Установить один раз

Предполагается уже установленный ROS2 Humble на Ubuntu 22.04.

```bash
sudo apt install ros-humble-gazebo-ros-pkgs ros-humble-gazebo-ros \
    ros-humble-gazebo-plugins python3-numpy
```

## 3. Собрать

```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select kobuki_ros_interfaces livox_ros_driver2 \
    ros2_livox_simulation hsl_description robot_b_detector --symlink-install
```

`--symlink-install` обязателен — без него правки в `urdf/*.xacro`,
launch-файлах и Python-скриптах не подхватятся без пересборки.

## 4. Что сорсить в КАЖДОМ новом терминале

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
source ~/ros2_ws/src/hsl25-digital-twin/hsl_description/setup_env.sh
```

Третья строка обязательна перед запуском Gazebo. Она:
- отключает попытку `gzserver` достучаться до онлайн-базы моделей (иначе
  20-30 секунд зависания при каждом старте);
- донастраивает `GAZEBO_MODEL_PATH`/`GAZEBO_RESOURCE_PATH`, без которых
  `gzserver` не находит даже встроенные `ground_plane`/`sun` (пола и
  света не будет, но ошибки в логе тоже не будет — молча).

Для чисто RViz-превью (без Gazebo) третья строка не обязательна, но
лишней не будет.

## 5. Launch-файлы

### RViz-превью без физики — `robot_description.launch.py`

Быстро посмотреть модель/геометрию, без Gazebo.

```bash
ros2 launch hsl_description robot_description.launch.py
```

| Аргумент | По умолчанию | Что делает |
|---|---|---|
| `urdf_file` | `kobuki_standalone.urdf.xacro` | какую модель грузить. Полная модель двойника: `urdf_file:=hsl_robot.urdf.xacro` |
| `rviz` | `true` | `rviz:=false` — не поднимать RViz |

### Полная симуляция — `gazebo.launch.py`

Gazebo с физикой, все сенсоры/плагины, все мосты соответствия реальному
драйверу (энкодеры, оба IMU, лидар) + RViz.

```bash
ros2 launch hsl_description gazebo.launch.py
```

| Аргумент | По умолчанию | Что делает |
|---|---|---|
| `urdf_file` | `hsl_robot.urdf.xacro` | уже полная модель, обычно не трогать |
| `gui` | `true` | `gui:=false` — без окна Gazebo (headless, для слабой машины/автотестов) |
| `rviz` | `true` | `rviz:=false` — не поднимать RViz |
| `entity_name` | `hsl_robot` | имя модели в Gazebo, менять не нужно |

Пример headless-запуска для автотестов/CI:
```bash
ros2 launch hsl_description gazebo.launch.py gui:=false rviz:=false
```

## 6. Быстрая проверка, что всё работает

В соседнем терминале (тот же source-набор из шага 4):

```bash
ros2 topic list
```

Ожидаются: `/commands/velocity`, `/odom`, `/joint_states`, `/sensors/core`,
`/sensors/imu_data`, `/livox/imu`, `/livox/lidar`, `/tf`, `/tf_static`.

Проехать вперёд:
```bash
ros2 topic pub /commands/velocity geometry_msgs/msg/Twist '{linear: {x: 0.2}}'
```
(без `-1` — шлёт непрерывно, `Ctrl+C` останавливает; для разового толчка
добавить `-1`)

## 7. Известные грабли

- **`gzserver` падает сразу с `exit code 255` без сообщения в лог launch** —
  почти наверняка порт `11345` занят зависшим процессом с прошлого
  неудачного запуска (`Ctrl+C` не всегда убивает подпроцессы). Проверить:
  `ss -tlnp | grep 11345`, убить всё, что найдётся: `kill -9 <pid>`.
- **Точки лидара в RViz визуально "накапливаются" за ~3 секунды** — это
  настройка отображения (`Decay Time`), каждое сообщение `/livox/lidar`
  само по себе содержит только текущий скан, как и у реального робота.
- **Все точки лидара одного цвета (обычно "красные")** — правильное
  поведение, пока в мире нет объектов с `<laser_retro>` в SDF. Не баг.
- **Меши корпуса/колёс не видны в Gazebo, видны только примитивы
  (стойки/платформа)** — если вдруг увидите это после переноса на новую
  машину, проверьте, что `setup_env.sh` из шага 4 реально выполнен.

## 8. Bag-записи с этапа квалификации

`hsl_description/data/` **не входит в этот репозиторий** (796МБ, два
файла превышают лимит GitHub в 100МБ) — реальные записи `/livox/lidar`,
`/livox/imu` с этапа квалификации, полезны для сверки формата/интенсивности
с симуляцией. Взять отдельно: *(ссылка/место — уточнить у капитана
команды)*.

## 9. Детекция второго робота (`robot_b_detector`, задача HSL26)

Пакет `robot_b_detector` ищет в облаке `/livox/lidar` цилиндрическое
основание второго робота (см. `docs/regulations.md` внутри пакета —
критерии поимки/обнаружения из регламента HSL26). Чистые numpy-функции
конвейера — `robot_b_detector/pipeline.py`, ROS2-нода — `detector_node.py`.

Запуск на цифровом двойнике (двойник уже спавнит второго робота по
умолчанию — см. `gazebo.launch.py` в `hsl_description`):

```bash
ros2 run robot_b_detector detector_node --ros-args -p use_sim_time:=true
```

Debug-топики: `/debug/floor_removed` (облако без пола), `/debug/candidate_cluster`
(кластер-кандидат), `/debug/position` (маркеры позиции в RViz).

`data/` внутри пакета — так же, как и в п.8, bag-записи в `.gitignore`,
не входят в репозиторий.

---

Подробности каждого пункта, обоснования решений и что ещё не готово —
`hsl_description/CLAUDE.md`.
