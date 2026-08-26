#!/usr/bin/env python3
# Мост joint_states -> sensors/core: считает "сырые" тики энкодеров из
# углов колёсных joint'ов и публикует их в том же топике/типе, что и
# реальный kobuki_node, чтобы код команды не отличал двойника от робота.
#
# Остальные поля SensorState (бампер, cliff, PWM, батарея, зарядка и т.д.)
# оставлены нулями/пустыми — под них пока нет отдельных Gazebo-плагинов,
# отдающих эти данные в ROS. Если код команды их читает — это не готово.

import math

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from kobuki_ros_interfaces.msg import SensorState

# Реальная константа kobuki, НЕ ticks_per_revolution "на глаз":
# kobuki_core/src/driver/diff_drive.cpp: tick_to_rad = 0.002436916871363930187454
TICK_TO_RAD = 0.002436916871363930187454
RAD_TO_TICK = 1.0 / TICK_TO_RAD

# Энкодеры и time_stamp реального робота - uint16, переполняются на 65536
# (см. комментарии в SensorState.msg)
UINT16_WRAP = 65536

PUBLISH_RATE_HZ = 50.0  # совпадает с "transmitted at 50Hz" в SensorState.msg


class WheelEncodersBridge(Node):

    def __init__(self):
        super().__init__('wheel_encoders_bridge')

        self.left_joint_name = self.declare_parameter(
            'wheel_left_joint_name', 'wheel_left_joint').value
        self.right_joint_name = self.declare_parameter(
            'wheel_right_joint_name', 'wheel_right_joint').value

        self._left_ticks = 0
        self._right_ticks = 0
        self._prev_left_angle = None
        self._prev_right_angle = None

        self._start_time = self.get_clock().now()

        self._pub = self.create_publisher(SensorState, 'sensors/core', 10)
        self.create_subscription(JointState, 'joint_states', self._on_joint_states, 10)
        self.create_timer(1.0 / PUBLISH_RATE_HZ, self._publish)

        self.get_logger().info(
            f'wheel_encoders_bridge: joint_states -> sensors/core '
            f'({self.left_joint_name}/{self.right_joint_name}, tick_to_rad={TICK_TO_RAD})')

    def _angle_delta_to_ticks(self, angle, prev_angle):
        delta = angle - prev_angle
        # нормализация на случай перехода через ±π между двумя сообщениями
        while delta > math.pi:
            delta -= 2 * math.pi
        while delta < -math.pi:
            delta += 2 * math.pi
        return round(delta * RAD_TO_TICK)

    def _on_joint_states(self, msg):
        if self.left_joint_name in msg.name:
            idx = msg.name.index(self.left_joint_name)
            angle = msg.position[idx]
            if self._prev_left_angle is not None:
                self._left_ticks += self._angle_delta_to_ticks(angle, self._prev_left_angle)
            self._prev_left_angle = angle

        if self.right_joint_name in msg.name:
            idx = msg.name.index(self.right_joint_name)
            angle = msg.position[idx]
            if self._prev_right_angle is not None:
                self._right_ticks += self._angle_delta_to_ticks(angle, self._prev_right_angle)
            self._prev_right_angle = angle

    def _publish(self):
        msg = SensorState()
        msg.header.stamp = self.get_clock().now().to_msg()

        elapsed_ms = (self.get_clock().now() - self._start_time).nanoseconds // 1_000_000
        msg.time_stamp = elapsed_ms % UINT16_WRAP

        msg.left_encoder = self._left_ticks % UINT16_WRAP
        msg.right_encoder = self._right_ticks % UINT16_WRAP

        self._pub.publish(msg)


def main():
    rclpy.init()
    node = WheelEncodersBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
