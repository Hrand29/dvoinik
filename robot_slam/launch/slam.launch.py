from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # 1. Связь livox -> livox_frame (мост между URDF и bridge)
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

        # 3. SLAM Toolbox (без EKF!)
        Node(
            package='slam_toolbox',
            executable='sync_slam_toolbox_node',
            name='slam_toolbox',
            output='screen',
            parameters=[{
                'use_sim_time': True,
                'odom_frame': 'odom',
                'map_frame': 'map',
                'base_frame': 'base_link',
                'scan_topic': '/scan',
                'mode': 'mapping',

                'map_update_interval': 0.5,  # Обновлять карту каждые 0.5 секунды (было ~2 сек)
                'minimum_travel_distance': 0.1,  # Обновлять карту каждые 10 см движения (было ~0.3 м)
                'minimum_travel_heading': 0.1,  # Обновлять карту при повороте на 0.1 радиана (~6 градусов)
                'resolution': 0.05, 
            }]
        ),
    ])