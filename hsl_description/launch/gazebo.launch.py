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

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    urdf_path = PathJoinSubstitution(
        [FindPackageShare('hsl_description'), 'urdf', LaunchConfiguration('urdf_file')]
    )

    gazebo_launch_path = PathJoinSubstitution(
        [FindPackageShare('gazebo_ros'), 'launch', 'gazebo.launch.py']
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
            description='Запускать gzclient (GUI)'
        ),

        DeclareLaunchArgument(
            name='rviz',
            default_value='true',
            description='Запускать RViz (модель робота + TF + облако точек лидара)'
        ),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(gazebo_launch_path),
            launch_arguments={'gui': LaunchConfiguration('gui')}.items()
        ),

        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{
                'use_sim_time': True,
                'robot_description': ParameterValue(
                    Command(['xacro ', urdf_path]), value_type=str)
            }]
        ),

        Node(
            package='gazebo_ros',
            executable='spawn_entity.py',
            output='screen',
            arguments=['-topic', 'robot_description', '-entity', LaunchConfiguration('entity_name')]
        ),

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
    ])
