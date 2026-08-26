#!/usr/bin/env python3
# Мост _raw/livox_lidar (CustomMsg) -> livox/lidar (PointCloud2): собирает
# PointCloud2 вручную по тому же байтовому макету, что и реальный
# livox_ros_driver2 (src/lddc.cpp::InitPointcloud2Msg,
# struct LivoxPointXyzrtlt в src/comm/comm.h, #pragma pack(1), 26 байт/точку:
# x,y,z,intensity float32 + tag,line uint8 + timestamp float64), а НЕ
# стандартным sensor_msgs_py-хелпером, чтобы поля точно совпадали 1-в-1.
#
# Зачем вообще этот мост: плагин ros2_livox_simulation публикует и
# CustomMsg (честная reflectivity на точку), и свой собственный PointCloud2
# — но тот теряет intensity/reflectivity при конвертации. Реальный робот
# публикует именно PointCloud2 С intensity (xfer_format=0). Поэтому мост
# собирает PointCloud2 заново из CustomMsg, а не берёт готовый от плагина
# (см. CLAUDE.md, секция "Симуляция лидара").
#
# intensity в этом сообщении = reflectivity (uint8 0..255) как есть, без
# пересчёта — это то же значение, что и в CustomMsg. Точной формулы
# масштабирования "intensity" у реального pub_handler.cpp внутри
# driver'а не нашли (закопано глубже lddc.cpp), решили не гадать.
#
# Упаковка через numpy structured array, а НЕ поточечный struct.pack_into
# в цикле: живым тестом (сравнение stamp сообщения с текущим /clock)
# обнаружено, что при ~1500 точках/сообщение и фактической частоте потока
# заметно выше ожидаемых 10Гц (похоже, <publish_rate> у плагина тоже не
# делает то, что заявлено — из той же серии, что и другие SDF-теги в этом
# форке) поточечный Python-цикл не успевал и накапливал растущую задержку
# (визуально — облако "отстаёт" от модели при движении и "нагоняет" при
# остановке; в логе RViz — "timestamp is earlier than all data in
# transform cache"). Векторизация через numpy field-assignment вместо
# 1500 отдельных вызовов struct.pack_into убирает это узкое место.

import numpy as np

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2, PointField
from livox_ros_driver2.msg import CustomMsg

POINT_STEP = 26  # 4*4 (x,y,z,intensity float32) + 1+1 (tag,line uint8) + 8 (timestamp float64)

# aligned=False (дефолт) => без паддинга между полями, как #pragma pack(1)
POINT_DTYPE = np.dtype([
    ('x', '<f4'), ('y', '<f4'), ('z', '<f4'), ('intensity', '<f4'),
    ('tag', 'u1'), ('line', 'u1'), ('timestamp', '<f8'),
])
assert POINT_DTYPE.itemsize == POINT_STEP


def make_fields():
    return [
        PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
        PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
        PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
        PointField(name='intensity', offset=12, datatype=PointField.FLOAT32, count=1),
        PointField(name='tag', offset=16, datatype=PointField.UINT8, count=1),
        PointField(name='line', offset=17, datatype=PointField.UINT8, count=1),
        PointField(name='timestamp', offset=18, datatype=PointField.FLOAT64, count=1),
    ]


class LivoxLidarBridge(Node):

    def __init__(self):
        super().__init__('livox_lidar_bridge')
        self._fields = make_fields()
        self._pub = self.create_publisher(PointCloud2, 'livox/lidar', 10)
        self.create_subscription(CustomMsg, '_raw/livox_lidar', self._on_raw_lidar, 10)

    def _on_raw_lidar(self, raw):
        n = len(raw.points)

        arr = np.empty(n, dtype=POINT_DTYPE)
        arr['x'] = [p.x for p in raw.points]
        arr['y'] = [p.y for p in raw.points]
        arr['z'] = [p.z for p in raw.points]
        arr['intensity'] = [p.reflectivity for p in raw.points]
        arr['tag'] = [p.tag for p in raw.points]
        arr['line'] = [p.line for p in raw.points]
        arr['timestamp'] = [p.offset_time for p in raw.points]

        msg = PointCloud2()
        msg.header = raw.header
        msg.header.frame_id = 'livox'
        msg.height = 1
        msg.width = n
        msg.fields = self._fields
        msg.is_bigendian = False
        msg.point_step = POINT_STEP
        msg.row_step = POINT_STEP * n
        msg.is_dense = True
        msg.data = arr.tobytes()

        self._pub.publish(msg)


def main():
    rclpy.init()
    node = LivoxLidarBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
