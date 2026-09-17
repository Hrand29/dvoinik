#!/usr/bin/env python3
# Мост _raw/gyro_imu -> sensors/imu_data: обрезает физически честный
# симулированный IMU (все 3 оси) до семантики реального kobuki_node
# (kobuki_ros.cpp::publishInertia()) — только yaw в orientation и
# angular_velocity.z, остальные оси с covariance=DBL_MAX ("не доверяй"),
# linear_acceleration не публикуется вообще (у гироскопа его физически нет).
#
# ⚠️⚠️ Курс ИНТЕГРИРУЕТСЯ из angular_velocity.z, а не берётся из
# orientation входящего сообщения. Две причины, обе принципиальные:
#
# 1. Так устроен реальный робот: kobuki_.getHeading() отдаёт
#    inertia.data.angle — курс, который прошивка базы получает
#    ИНТЕГРИРОВАНИЕМ гироскопа (kobuki_core/src/driver/kobuki.cpp:464),
#    а не откуда-то ещё.
# 2. Gazebo НЕ применяет шум к orientation — проверено вживую: при
#    заведомо большом смещении гироскопа angular_velocity.z шумела как
#    задано, а yaw в orientation оставался идеальным (-0.00004 всё время).
#    То есть без интегрирования весь шум гироскопа на курс не влиял бы, и
#    одометрия (odometry_bridge.py берёт курс отсюда) снова оказалась бы
#    безошибочной — ровно та проблема, ради которой всё это делалось.
#
# Побочный эффект, он же желаемый: интеграл шума даёт медленный уход
# курса, как у настоящего гироскопа.

import math
import sys

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu

DBL_MAX = sys.float_info.max


class GyroImuBridge(Node):

    def __init__(self):
        super().__init__('gyro_imu_bridge')
        self._heading = 0.0
        self._last_stamp = None
        self._pub = self.create_publisher(Imu, 'sensors/imu_data', 10)
        self.create_subscription(Imu, '_raw/gyro_imu', self._on_raw_imu, 10)

    def _on_raw_imu(self, raw):
        stamp = raw.header.stamp.sec + raw.header.stamp.nanosec * 1e-9
        if self._last_stamp is not None:
            dt = stamp - self._last_stamp
            # dt<=0 бывает на рестарте симуляции (время прыгнуло назад)
            if 0.0 < dt < 1.0:
                self._heading += raw.angular_velocity.z * dt
                self._heading = math.atan2(math.sin(self._heading),
                                           math.cos(self._heading))
        self._last_stamp = stamp
        yaw = self._heading

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
