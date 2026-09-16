# Copyright 2022 Waipot Ngamsaad
# All rights reserved.
#
# Software License Agreement (BSD License 2.0)
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# * Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
# * Neither the name of {copyright_holder} nor the names of its
#   contributors may be used to endorse or promote products derived
#   from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def _spawn_static_robot_b(context, *args, **kwargs):
    """Спавнит второго робота (та же модель) БЕЗ единого <gazebo>-плагина.

    Диффдрайв, оба IMU и лидар у digital twin'а все глобальные, без
    namespace (см. CLAUDE.md, раздел HSL26) - если оставить их активными и
    у второго робота, он будет драться с роботом А за одни и те же топики
    (commands/velocity, odom, joint_states, _raw/gyro_imu, _raw/livox_imu,
    _raw/livox_lidar), причём не громко упадёт, а тихо испортит данные
    робота А подмешанными сообщениями от робота Б. Простое и надёжное
    решение (без правки общего xacro и без threading'а namespace через все
    плагины/мосты) - сгенерировать URDF тем же xacro, что и для робота А, и
    вырезать из него ВСЕ <gazebo>-блоки перед спавном: остаются только
    link/joint/visual/collision/inertial (геометрия та же, что у реального
    двойника), полностью отключается любая ROS-публикация И актуация
    колёс. Итог ровно то, что просили как временный вариант - видимая
    модель без возможности управления, без конфликтов.
    """
    if context.launch_configurations.get('spawn_robot_b', 'true') not in ('true', 'True', '1'):
        return []

    urdf_file = LaunchConfiguration('urdf_file').perform(context)
    lidar_samples = LaunchConfiguration('lidar_samples').perform(context)
    urdf_path = os.path.join(
        get_package_share_directory('hsl_description'), 'urdf', urdf_file)

    result = subprocess.run(
        ['xacro', urdf_path, f'lidar_samples:={lidar_samples}'],
        capture_output=True, text=True, check=True)

    root = ET.fromstring(result.stdout)
    for gazebo_tag in root.findall('gazebo'):
        root.remove(gazebo_tag)

    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='_robot_b.urdf', delete=False)
    tmp.write(ET.tostring(root, encoding='unicode'))
    tmp.close()

    return [Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        output='screen',
        arguments=[
            '-file', tmp.name,
            '-entity', LaunchConfiguration('robot_b_entity_name').perform(context),
            '-x', LaunchConfiguration('robot_b_x').perform(context),
            '-y', LaunchConfiguration('robot_b_y').perform(context),
            '-Y', LaunchConfiguration('robot_b_yaw').perform(context),
        ]
    )]


def generate_launch_description():

    urdf_path = PathJoinSubstitution(
        [FindPackageShare('hsl_description'), 'urdf', LaunchConfiguration('urdf_file')]
    )

    gazebo_launch_path = PathJoinSubstitution(
        [FindPackageShare('gazebo_ros'), 'launch', 'gazebo.launch.py']
    )

    world_path = PathJoinSubstitution(
        [FindPackageShare('hsl_description'), 'worlds',
         [LaunchConfiguration('world'), '.world']]
    )

    rviz_config_path = PathJoinSubstitution(
        [FindPackageShare('hsl_description'), 'rviz', 'gazebo.rviz']
    )

    return LaunchDescription([

        # См. CLAUDE.md: без этого gzserver на старте пытается достучаться
        # до models.gazebosim.org и подвисает на 20-30+ секунд.
        SetEnvironmentVariable('GAZEBO_MODEL_DATABASE_URI', ''),

        DeclareLaunchArgument(
            name='urdf_file',
            default_value='hsl_robot.urdf.xacro',
            description='Имя .urdf.xacro файла в hsl_description/urdf для загрузки'
        ),

        DeclareLaunchArgument(
            name='entity_name',
            default_value='hsl_robot',
            description='Имя модели в Gazebo'
        ),

        DeclareLaunchArgument(
            name='gui',
            default_value='true',
            description=(
                'Запускать gzclient (3D-окно самого Gazebo). По умолчанию '
                'выключен — дублирует RViz (тот уже показывает модель и '
                'облако точек), а лишняя нагрузка заметно увеличивает '
                'задержку потока лидара на загруженной машине (см. CLAUDE.md)'
            )
        ),

        DeclareLaunchArgument(
            name='rviz',
            default_value='true',
            description='Запускать RViz (модель робота + TF + облако точек лидара)'
        ),

        DeclareLaunchArgument(
            name='world',
            default_value='lab1',
            description=(
                'Какой мир грузить (worlds/<value>.world в hsl_description): '
                'lab1 — лабиринт по умолчанию (с двумя выходами — Wall_144/'
                'Wall_117 убраны), template/lab2 — другие варианты из '
                'Labirint_bez_prepyatstviy.zip, empty — пустой пол. '
                'Геометрия мира — это Gazebo, не URDF, поэтому в RViz стены '
                'лабиринта своей 3D-моделью не отрисуются; но лидар их '
                'честно сканирует, так что стены всё равно будут видны в '
                'RViz как облако точек, когда робот к ним подъедет. Чтобы '
                'разглядеть лабиринт целиком как 3D-сцену — нужен gui:=true '
                '(дефолт gui остаётся false)'
            )
        ),

        DeclareLaunchArgument(
            name='lidar_samples',
            default_value='2000',
            description=(
                'Лучей на скан лидара (xacro:arg lidar_samples в '
                'mast.urdf.xacro). Больше — плотнее облако, но выше нагрузка '
                'и больше задержка потока лидара под конкуренцией за CPU. '
                '10000 — ближе к реальному роботу (~20000/скан), но '
                'ощутимо лагает на загрученной машине; 2000 — для '
                'повседневной разработки'
            )
        ),

        DeclareLaunchArgument(
            name='spawn_x',
            default_value='-2.55',
            description=(
                'Начальная позиция робота А, X (м) — только spawn_entity, '
                'world/SDF не трогает. Дефолт — угловая ячейка lab1 между '
                'Wall_156 и Wall_45 (клиренс до стен ~0.42м)'
            )
        ),
        DeclareLaunchArgument(
            name='spawn_y',
            default_value='-2.55',
            description='Начальная позиция робота А, Y (м) — см. spawn_x'
        ),
        DeclareLaunchArgument(
            name='spawn_yaw',
            default_value='0.0',
            description='Начальная ориентация робота А, yaw (рад)'
        ),

        DeclareLaunchArgument(
            name='spawn_robot_b',
            default_value='true',
            description=(
                'Спавнить второго робота (та же модель, БЕЗ активных '
                'Gazebo-плагинов — ни диффдрайва, ни IMU, ни лидара, см. '
                '_spawn_static_robot_b выше: без этого он бы делил '
                'глобальные топики с роботом А). Статичная модель, колёса '
                'не актуируются'
            )
        ),
        DeclareLaunchArgument(
            name='robot_b_entity_name',
            default_value='robot_b',
            description='Имя модели робота Б в Gazebo'
        ),
        DeclareLaunchArgument(
            name='robot_b_x',
            default_value='1.70',
            description=(
                'Начальная позиция робота Б, X (м). Дефолт — ячейка lab1 '
                'между Wall_138 и Wall_140 (клиренс ~0.42м). ⚠️ Значение по '
                'умолчанию привязано к геометрии именно lab1 — при смене '
                'world на lab2/template координаты уже не гарантированно '
                'безопасны'
            )
        ),
        DeclareLaunchArgument(
            name='robot_b_y',
            default_value='2.54',
            description='Начальная позиция робота Б, Y (м) — см. robot_b_x'
        ),
        DeclareLaunchArgument(
            name='robot_b_yaw',
            default_value='0.0',
            description='Начальная ориентация робота Б, yaw (рад)'
        ),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(gazebo_launch_path),
            launch_arguments={
                'gui': LaunchConfiguration('gui'),
                'world': world_path,
            }.items()
        ),

        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{
                'use_sim_time': True,
                'robot_description': ParameterValue(
                    Command([
                        'xacro ', urdf_path,
                        ' lidar_samples:=', LaunchConfiguration('lidar_samples')
                    ]), value_type=str)
            }]
        ),

        Node(
            package='gazebo_ros',
            executable='spawn_entity.py',
            output='screen',
            arguments=[
                '-topic', 'robot_description', '-entity', LaunchConfiguration('entity_name'),
                '-x', LaunchConfiguration('spawn_x'),
                '-y', LaunchConfiguration('spawn_y'),
                '-Y', LaunchConfiguration('spawn_yaw'),
            ]
        ),

        OpaqueFunction(function=_spawn_static_robot_b),

        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            arguments=['-d', rviz_config_path],
            condition=IfCondition(LaunchConfiguration('rviz')),
            parameters=[{'use_sim_time': True}]
        ),

        # joint_states -> sensors/core (kobuki_ros_interfaces/SensorState),
        # чтобы код команды читал энкодеры так же, как на реальном роботе
        Node(
            package='hsl_description',
            executable='wheel_encoders_bridge.py',
            name='wheel_encoders_bridge',
            output='screen',
            parameters=[{'use_sim_time': True}]
        ),

        # _raw/gyro_imu -> sensors/imu_data, обрезка до семантики реального
        # kobuki_node (только yaw + angular_velocity.z)
        Node(
            package='hsl_description',
            executable='gyro_imu_bridge.py',
            name='gyro_imu_bridge',
            output='screen',
            parameters=[{'use_sim_time': True}]
        ),

        # _raw/livox_imu -> livox/imu, переформатирование под точную (в т.ч.
        # дефектную) семантику реального livox_ros_driver2
        Node(
            package='hsl_description',
            executable='livox_imu_bridge.py',
            name='livox_imu_bridge',
            output='screen',
            parameters=[{'use_sim_time': True}]
        ),

        # _raw/livox_lidar (CustomMsg) -> livox/lidar (PointCloud2 с
        # сохранённой intensity, как у реального робота)
        Node(
            package='hsl_description',
            executable='livox_lidar_bridge.py',
            name='livox_lidar_bridge',
            output='screen',
            parameters=[{'use_sim_time': True}]
        ),

        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='livox_to_livox_frame',
            arguments=[
                '--x', '0', '--y', '0', '--z', '0',
                '--roll', '0', '--pitch', '0', '--yaw', '0',
                '--frame-id', 'livox',
                '--child-frame-id', 'livox_frame'
            ]
        ),

        # 2. PointCloud2 -> LaserScan
        Node(
            package='pointcloud_to_laserscan',
            executable='pointcloud_to_laserscan_node',
            name='pointcloud_to_laserscan',
            remappings=[
                ('cloud_in', '/livox/lidar'),
                ('scan', '/scan')
            ],
            parameters=[{
                'use_sim_time': True,
                'target_frame': 'livox_frame',
                'transform_tolerance': 0.05,
                'min_height': -0.1,
                'max_height': 0.1,
                'angle_min': -3.14159,
                'angle_max': 3.14159,
                'angle_increment': 0.0087,
                'scan_time': 0.1,
                'range_min': 0.5,
                'range_max': 15.0,
                'use_inf': True,
                'concurrency_level': 1,
            }]
        ),

        # 3. SLAM Toolbox в режиме локализации
        Node(
            package='slam_toolbox',
            executable='localization_slam_toolbox_node',
            name='slam_toolbox',
            output='screen',
            parameters=[{
                'use_sim_time': True,
                'odom_frame': 'odom',
                'map_frame': 'map',
                'base_frame': 'base_link',
                'scan_topic': '/scan',
                'mode': 'localization',
                
                # Путь к сохраненной карте (без расширения .yaml)
                'map_file_name': '/root/hakaton_starline/ros2_ws/src/dvoinik/robot_slam/my_map',
                
                # НАЧАЛЬНАЯ ПОЗИЦИЯ РОБОТА (x, y, theta)
                # Это примерная позиция, где робот находится в Gazebo в момент запуска
                # Если робот в начале координат, поставь [0.0, 0.0, 0.0]
                'map_start_pose': [-2.551348, -2.549979, 0.0],
                
                'map_update_interval': 0.5,
                'resolution': 0.05,
            }]
        ),
    ])
