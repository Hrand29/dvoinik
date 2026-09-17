#!/usr/bin/env python3
# Мост _raw/odom + sensors/imu_data -> odom (+ TF odom->base_link):
# воспроизводит семантику реального kobuki_node, а не "как удобнее".
#
# Реальный драйвер (kobuki_node/src/odometry.cpp, Odometry::update()):
#
#     ecl::extend_pose(pose_, pose_update);        // x, y, yaw от ЭНКОДЕРОВ
#     if (use_imu_heading_) {                      // = true в конфиге
#         pose_[2] = ecl::wrap_angle(imu_heading);         // yaw ПЕРЕЗАПИСАН
#         pose_update_rates[2] = imu_angular_velocity;     // гироскопом базы
#     }
#
# use_imu_heading: true стоит в kobuki_node_params.yaml организаторов, а
# imu_heading — это kobuki_.getHeading() -> inertia.data.angle, встроенный
# гироскоп базы, уже проинтегрированный прошивкой в АБСОЛЮТНЫЙ курс
# (kobuki_core/src/driver/kobuki.cpp:464).
#
# Практическое следствие, ради которого всё это и нужно: у реального робота
# x/y дрейфуют от проскальзывания колёс, а курс — нет. Если робот в
# лабиринте чиркнул стену и колёса проскользнули, позиция уедет, а yaw
# останется верным. Ни ground-truth-одометрия (дефолт плагина), ни чистые
# энкодеры такой асимметрии не дают, а SLAM/Nav2 настраиваются именно под
# неё.
#
# Шума нет намеренно: симулированный гироскоп (kobuki_gazebo.urdf.xacro)
# идёт с bias_stddev=0, т.е. курс здесь ТОЧНЕЕ реального (настоящий гироскоп
# медленно уходит нулём). Структура ошибок верная, абсолютная величина по
# курсу — оптимистичная.

import math

import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import Imu
from tf2_ros import TransformBroadcaster


class OdometryBridge(Node):

    def __init__(self):
        super().__init__('odometry_bridge')
        self._imu_yaw = None
        self._imu_yaw_rate = 0.0

        self._pub = self.create_publisher(Odometry, 'odom', 50)
        self._tf = TransformBroadcaster(self)
        self.create_subscription(Imu, 'sensors/imu_data', self._on_imu, 50)
        self.create_subscription(Odometry, '_raw/odom', self._on_raw_odom, 50)

        self.get_logger().info(
            'odometry_bridge: _raw/odom (энкодеры) + sensors/imu_data (курс '
            'гироскопа) -> odom + TF odom->base_link, как kobuki_node с '
            'use_imu_heading=true')

    def _on_imu(self, msg):
        self._imu_yaw = self._yaw_from_quaternion(msg.orientation)
        self._imu_yaw_rate = msg.angular_velocity.z

    def _on_raw_odom(self, raw):
        # До прихода первого сообщения гироскопа отдаём энкодерный курс как
        # есть - ровно так же ведёт себя реальный драйвер, пока inertia не
        # пришла (pose_[2] просто не перезаписывается)
        if self._imu_yaw is None:
            yaw = self._yaw_from_quaternion(raw.pose.pose.orientation)
            yaw_rate = raw.twist.twist.angular.z
        else:
            yaw = self._wrap_angle(self._imu_yaw)
            yaw_rate = self._imu_yaw_rate

        qz = math.sin(yaw / 2.0)
        qw = math.cos(yaw / 2.0)

        msg = Odometry()
        msg.header.stamp = raw.header.stamp
        msg.header.frame_id = 'odom'
        msg.child_frame_id = 'base_link'

        # x, y - как есть от счисления по колёсам, их драйвер не трогает
        msg.pose.pose.position.x = raw.pose.pose.position.x
        msg.pose.pose.position.y = raw.pose.pose.position.y
        msg.pose.pose.position.z = 0.0
        msg.pose.pose.orientation.z = qz
        msg.pose.pose.orientation.w = qw

        msg.twist.twist.linear.x = raw.twist.twist.linear.x
        msg.twist.twist.linear.y = raw.twist.twist.linear.y
        msg.twist.twist.angular.z = yaw_rate

        # Значения один в один из Odometry::getOdometry() реального драйвера:
        # yaw-covariance 0.05 именно потому, что курс от гироскопа (без него
        # драйвер ставит 0.2), 1e10 на неиспользуемых осях - требование
        # robot_pose_ekf
        msg.pose.covariance[0] = 0.1
        msg.pose.covariance[7] = 0.1
        msg.pose.covariance[35] = 0.05
        msg.pose.covariance[14] = 1e10
        msg.pose.covariance[21] = 1e10
        msg.pose.covariance[28] = 1e10

        self._pub.publish(msg)

        tf = TransformStamped()
        tf.header.stamp = raw.header.stamp
        tf.header.frame_id = 'odom'
        tf.child_frame_id = 'base_link'
        tf.transform.translation.x = raw.pose.pose.position.x
        tf.transform.translation.y = raw.pose.pose.position.y
        tf.transform.translation.z = 0.0
        tf.transform.rotation.z = qz
        tf.transform.rotation.w = qw
        self._tf.sendTransform(tf)

    @staticmethod
    def _wrap_angle(angle):
        return math.atan2(math.sin(angle), math.cos(angle))

    @staticmethod
    def _yaw_from_quaternion(q):
        return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def main():
    rclpy.init()
    node = OdometryBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
