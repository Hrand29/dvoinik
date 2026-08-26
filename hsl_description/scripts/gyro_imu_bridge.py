#!/usr/bin/env python3
# Мост _raw/gyro_imu -> sensors/imu_data: обрезает физически честный
# симулированный IMU (все 3 оси) до семантики реального kobuki_node
# (kobuki_ros.cpp::publishInertia()) — только yaw в orientation и
# angular_velocity.z, остальные оси с covariance=DBL_MAX ("не доверяй"),
# linear_acceleration не публикуется вообще (у гироскопа его физически нет).

import math
import sys

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu

DBL_MAX = sys.float_info.max


class GyroImuBridge(Node):

    def __init__(self):
        super().__init__('gyro_imu_bridge')
        self._pub = self.create_publisher(Imu, 'sensors/imu_data', 10)
        self.create_subscription(Imu, '_raw/gyro_imu', self._on_raw_imu, 10)

    def _on_raw_imu(self, raw):
        yaw = self._yaw_from_quaternion(raw.orientation)

        msg = Imu()
        msg.header.stamp = raw.header.stamp
        msg.header.frame_id = 'gyro_link'

        msg.orientation.x = 0.0
        msg.orientation.y = 0.0
        msg.orientation.z = math.sin(yaw / 2.0)
        msg.orientation.w = math.cos(yaw / 2.0)
        msg.orientation_covariance[0] = DBL_MAX
        msg.orientation_covariance[4] = DBL_MAX
        msg.orientation_covariance[8] = 0.05

        msg.angular_velocity.z = raw.angular_velocity.z
        msg.angular_velocity_covariance[0] = DBL_MAX
        msg.angular_velocity_covariance[4] = DBL_MAX
        msg.angular_velocity_covariance[8] = 0.05

        # linear_acceleration остаётся нулевым — publishInertia() реального
        # драйвера его тоже не заполняет

        self._pub.publish(msg)

    @staticmethod
    def _yaw_from_quaternion(q):
        return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def main():
    rclpy.init()
    node = GyroImuBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
