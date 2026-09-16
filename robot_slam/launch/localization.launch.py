from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # 1. Связь livox -> livox_frame
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