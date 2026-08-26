#!/usr/bin/env python3
"""
Эмуляция реальных энкодеров AS5048 для колес робота.
Публикует тики энкодера для каждого колеса в отдельный топик.
"""

import rospy
import math
import random
from sensor_msgs.msg import JointState
from std_msgs.msg import Int32, Float32

class WheelEncoders:
    def __init__(self):
        rospy.init_node('wheel_encoders', anonymous=True)
        
        # ==================== ПАРАМЕТРЫ ЭНКОДЕРОВ ====================
        self.ticks_per_revolution = rospy.get_param('~ticks_per_revolution', 4096)
        self.gear_ratio = rospy.get_param('~gear_ratio', 1.0)
        self.add_noise = rospy.get_param('~add_noise', True)
        self.noise_stddev = rospy.get_param('~noise_stddev', 2.0)
        self.publish_rate = rospy.get_param('~publish_rate', 100)
        
        # Имена колесных сочленений (ДОЛЖНЫ СОВПАДАТЬ С URDF!)
        self.wheel_joints = [
            'wheel1_joint',
            'wheel2_joint', 
            'wheel3_joint',
            'wheel4_joint'
        ]
        
        # Имена моторов для топиков
        self.motor_names = [
            'front_left',
            'back_left',
            'back_right',
            'front_right'
        ]
        
        # Хранение данных
        self.prev_positions = {}
        self.prev_time = None
        self.ticks = {}
        self.prev_ticks = {}
        self.prev_angles = {}  # Для отслеживания полных оборотов
        
        # Инициализация
        for name in self.motor_names:
            self.ticks[name] = 0
            self.prev_ticks[name] = 0
            self.prev_angles[name] = 0
        
        # ==================== ПУБЛИКАТОРЫ ====================
        self.encoders_pub = {}
        for i, name in enumerate(self.motor_names):
            self.encoders_pub[name] = rospy.Publisher(
                f'/wheel_encoders/{name}/ticks', 
                Int32, 
                queue_size=10
            )
        
        self.speed_pub = {}
        for i, name in enumerate(self.motor_names):
            self.speed_pub[name] = rospy.Publisher(
                f'/wheel_encoders/{name}/rpm',
                Float32,
                queue_size=10
            )
        
        self.all_ticks_pub = rospy.Publisher(
            '/wheel_encoders/all_ticks',
            Int32,
            queue_size=10
        )
        
        # ==================== ПОДПИСЧИК ====================
        self.sub = rospy.Subscriber('/joint_states', JointState, self.joint_states_callback, queue_size=10)
        
        # ==================== ТАЙМЕР ====================
        self.timer = rospy.Timer(rospy.Duration(1.0/self.publish_rate), self.publish_ticks)
        
        rospy.loginfo("=" * 50)
        rospy.loginfo("Wheel Encoders Node Started")
        rospy.loginfo(f"  Wheel joints: {self.wheel_joints}")
        rospy.loginfo(f"  Motor names: {self.motor_names}")
        rospy.loginfo(f"  Ticks per revolution: {self.ticks_per_revolution}")
        rospy.loginfo(f"  Gear ratio: {self.gear_ratio}")
        rospy.loginfo(f"  Add noise: {self.add_noise}")
        rospy.loginfo(f"  Publish rate: {self.publish_rate} Hz")
        rospy.loginfo("=" * 50)
        
        # Счетчик сообщений (инициализируем!)
        self.msg_count = 0
        
    def add_encoder_noise(self, ticks):
        """Добавляет шум к значению энкодера"""
        if not self.add_noise:
            return ticks
        noise = random.gauss(0, self.noise_stddev)
        return int(ticks + noise)
    
    def angle_to_continuous_ticks(self, current_angle, prev_angle, motor_name):
        """
        Преобразует угол в непрерывные тики с учетом полных оборотов.
        Это важно для continuous вращения!
        """
        # Вычисляем разницу углов
        delta_angle = current_angle - prev_angle
        
        # Нормализуем разницу в диапазон [-π, π]
        # Это позволяет отслеживать полные обороты
        while delta_angle > math.pi:
            delta_angle -= 2 * math.pi
        while delta_angle < -math.pi:
            delta_angle += 2 * math.pi
        
        # Вычисляем изменение в тиках
        delta_ticks = (delta_angle / (2 * math.pi)) * self.ticks_per_revolution * self.gear_ratio
        
        # Обновляем общее количество тиков
        new_ticks = self.prev_ticks.get(motor_name, 0) + delta_ticks
        
        return int(new_ticks)
    
    def radians_to_ticks_simple(self, angle_rad):
        """Простое преобразование радиан в тики (без учета полных оборотов)"""
        motor_angle = angle_rad * self.gear_ratio
        ticks = (motor_angle / (2 * math.pi)) * self.ticks_per_revolution
        return int(ticks)
    
    def ticks_to_rpm(self, delta_ticks, delta_time):
        """Переводит изменение тиков в RPM"""
        if delta_time <= 0:
            return 0.0
        revolutions = delta_ticks / self.ticks_per_revolution
        rpm = (revolutions / delta_time) * 60.0
        return rpm
    
    def joint_states_callback(self, msg):
        """Обрабатывает сообщения joint_states"""
        self.msg_count += 1
        
        # Логируем каждые 100 сообщений
        if self.msg_count % 100 == 0:
            rospy.loginfo(f"Received {self.msg_count} joint_states messages")
        
        current_time = msg.header.stamp.to_sec()
        if current_time == 0:
            current_time = rospy.Time.now().to_sec()
        
        for i, joint_name in enumerate(self.wheel_joints):
            if joint_name in msg.name:
                idx = msg.name.index(joint_name)
                motor_name = self.motor_names[i]
                
                current_angle = msg.position[idx]
                
                # Используем метод с отслеживанием полных оборотов
                current_ticks = self.angle_to_continuous_ticks(
                    current_angle, 
                    self.prev_angles.get(motor_name, 0),
                    motor_name
                )
                current_ticks = self.add_encoder_noise(current_ticks)
                
                # Сохраняем тики
                self.ticks[motor_name] = current_ticks
                
                # Расчет RPM
                if motor_name in self.prev_ticks and self.prev_time is not None:
                    delta_ticks = current_ticks - self.prev_ticks[motor_name]
                    delta_time = current_time - self.prev_time
                    rpm = self.ticks_to_rpm(delta_ticks, delta_time)
                else:
                    rpm = 0.0
                
                # Публикуем RPM
                self.speed_pub[motor_name].publish(Float32(rpm))
                
                # Сохраняем для следующего расчета
                self.prev_ticks[motor_name] = current_ticks
                self.prev_angles[motor_name] = current_angle
        
        self.prev_time = current_time
    
    def publish_ticks(self, event):
        """Публикует текущие значения энкодеров"""
        for motor_name, ticks in self.ticks.items():
            self.encoders_pub[motor_name].publish(Int32(ticks))
        
        all_ticks = sum(self.ticks.values())
        self.all_ticks_pub.publish(Int32(all_ticks))

if __name__ == '__main__':
    try:
        encoder_node = WheelEncoders()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass