"""Двойник + SLAM (mapping, построение карты с нуля) одной командой.

Переиспользует gazebo.launch.py (hsl_description) и slam.launch.py
(robot_slam) через IncludeLaunchDescription, а не копирует их ноды -
единственное определение каждой ноды остаётся в своём файле, поэтому
здесь физически не может возникнуть дублирования имён (livox_to_
livox_frame/pointcloud_to_laserscan/slam_toolbox), с которым уже
столкнулись при ручной вставке тех же нод прямо в gazebo.launch.py.

Аргументы gazebo.launch.py (world, gui и т.п.) не форвардятся - запускает
двойник с его собственными дефолтами (gui:=true уже дефолт на этой ветке).
Если нужен другой мир/позиция спавна - редактировать сами дефолты в
gazebo.launch.py, а не аргументы этого файла.
"""

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution


def generate_launch_description():
    gazebo_launch_path = PathJoinSubstitution(
        [FindPackageShare('hsl_description'), 'launch', 'gazebo.launch.py']
    )
    slam_mapping_launch_path = PathJoinSubstitution(
        [FindPackageShare('robot_slam'), 'launch', 'slam.launch.py']
    )

    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(gazebo_launch_path)
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(slam_mapping_launch_path)
        ),
    ])
