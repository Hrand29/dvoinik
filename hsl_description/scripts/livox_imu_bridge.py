#!/usr/bin/env python3
# Мост _raw/livox_imu -> livox/imu: переформатирует физически честный
# симулированный IMU под точную (в т.ч. дефектную) семантику реального
# livox_ros_driver2 (src/lddc.cpp::InitImuMsg), а не "как правильно":
#   - orientation вообще не публикуется реальным драйвером (у ICM-40609 нет
#     магнетометра, полной ориентации взяться неоткуда) — остаётся нулевым
#   - linear_acceleration в единицах "g", драйвер НЕ домножает на 9.81
#     (это реальный баг driver'а: https://github.com/Livox-SDK/livox_ros_driver2/issues/157,
#     см. CLAUDE.md) — здесь то же самое, намеренно, а не "исправлено"
#   - frame_id захардкожен как "livox_frame" (lddc.cpp:481), хотя в TF
#     дереве фрейм называется иначе — тоже воспроизведено намеренно

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu

G_TO_MPS2 = 9.81


class LivoxImuBridge(Node):

    def __init__(self):
        super().__init__('livox_imu_bridge')
        self._pub = self.create_publisher(Imu, 'livox/imu', 10)
        self.create_subscription(Imu, '_raw/livox_imu', self._on_raw_imu, 10)

    def _on_raw_imu(self, raw):
        msg = Imu()
        msg.header.stamp = raw.header.stamp
        msg.header.frame_id = 'livox_frame'

        # orientation остаётся нулевым — реальный драйвер его не заполняет

        msg.angular_velocity = raw.angular_velocity

        msg.linear_acceleration.x = raw.linear_acceleration.x / G_TO_MPS2
        msg.linear_acceleration.y = raw.linear_acceleration.y / G_TO_MPS2
        msg.linear_acceleration.z = raw.linear_acceleration.z / G_TO_MPS2

        self._pub.publish(msg)


def main():
    rclpy.init()
    node = LivoxImuBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
