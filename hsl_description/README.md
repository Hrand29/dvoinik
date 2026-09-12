# Цифровой двойник HSL25 — сборка и запуск

## 1. Установить один раз

Предполагается уже установленный ROS2 Humble на Ubuntu 22.04.

```bash
sudo apt install ros-humble-gazebo-ros-pkgs ros-humble-gazebo-ros \
    ros-humble-gazebo-plugins python3-numpy
```

## 2. Какие папки нужны

Цифровой двойник — это **4 пакета**, все должны лежать рядом в
`~/ros2_ws/src/`:

- `hsl_description/` — основной пакет (URDF, launch, RViz-конфиги, мосты)
- `ros2_livox_simulation/` — Gazebo-плагин лидара
- `livox_ros_driver2/` — пакет-заглушка с типами сообщений Livox (НЕ
  настоящий драйвер)
- `kobuki_ros_interfaces/` — сообщения kobuki (`SensorState` и др.)

⚠️ Если в этом же workspace будет лежать `hackaton/hsl25-master` (архив
организаторов) — положить рядом пустой файл `hackaton/COLCON_IGNORE`,
иначе colcon упадёт на конфликте имён пакетов (внутри архива тоже есть
`livox_ros_driver2`, но собрать его нельзя — требует физический SDK).

## 3. Собрать

```bash
cd ~/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select kobuki_ros_interfaces livox_ros_driver2 \
    ros2_livox_simulation hsl_description --symlink-install
```

`--symlink-install` обязателен — без него правки в `urdf/*.xacro`,
launch-файлах и Python-скриптах не подхватятся без пересборки.

## 4. Что сорсить в КАЖДОМ новом терминале

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
source ~/ros2_ws/src/hsl_description/setup_env.sh
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
| `gui` | `false` | `gui:=true` — включить 3D-окно самого Gazebo. По умолчанию выключено: дублирует RViz и заметно увеличивает задержку потока лидара на загруженной машине |
| `rviz` | `true` | `rviz:=false` — не поднимать RViz |
| `entity_name` | `hsl_robot` | имя модели в Gazebo, менять не нужно |
| `lidar_samples` | `2000` | лучей на скан лидара. Больше — плотнее облако, но выше нагрузка и задержка (см. «Известные грабли» ниже); `lidar_samples:=10000` — ближе к реальному роботу, если машина свободна |
| `world` | `empty` | какой мир грузить: `empty` (пустой пол, поведение как раньше), `template`/`lab1`/`lab2` — варианты лабиринта. Стены — геометрия Gazebo, в RViz своей 3D-моделью не отрисуются (но лидар их видит, будут видны как облако точек); чтобы посмотреть лабиринт целиком — нужен `gui:=true` |

Пример headless-запуска для автотестов/CI:
```bash
ros2 launch hsl_description gazebo.launch.py rviz:=false
```

Пример с более плотным облаком (на свободной машине):
```bash
ros2 launch hsl_description gazebo.launch.py lidar_samples:=10000
```

Пример с лабиринтом, чтобы реально его разглядеть:
```bash
ros2 launch hsl_description gazebo.launch.py world:=lab1 gui:=true
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
  машину, проверьте `export GAZEBO_MODEL_DATABASE_URI=""` и
  `source /usr/share/gazebo/setup.sh` выполнены (шаг 4).
- **Облако лидара в RViz выглядит "оторванным" от робота, висит в
  пустоте не двигаясь по несколько секунд** — не баг замороженного
  буфера, а реальная задержка потока лидара под нагрузкой на CPU
  (плагин однопоточный, без защиты от отставания). Помогает: не
  включать `gui:=true` (дублирует RViz, но заметно грузит именно
  лидар), снизить `lidar_samples` (дефолт уже `2000` из-за этого),
  закрыть лишние программы. Подробности и цифры — `CLAUDE.md`.
- **Если склонировали/скачали этот же репозиторий ещё раз внутрь
  `~/ros2_ws/src/`** (например, чтобы проверить сборку) — colcon найдёт
  те же 4 пакета дважды и упадёт на `Duplicate package names`. Положить
  пустой `COLCON_IGNORE` в скачанную копию.

Подробности каждого пункта, обоснования решений и что ещё не готово —
`CLAUDE.md`.
