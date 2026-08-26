# Source this ПОСЛЕ /opt/ros/humble/setup.bash и install/setup.bash,
# перед любым запуском gazebo.launch.py:
#
#   source /opt/ros/humble/setup.bash
#   source ~/ros2_ws/install/setup.bash
#   source ~/ros2_ws/src/hsl_description/setup_env.sh
#   ros2 launch hsl_description gazebo.launch.py
#
# Без этого gzserver либо зависает на 20-30с (ждёт models.gazebosim.org),
# либо не находит даже встроенные model://ground_plane и model://sun
# (сыпет "Unable to find uri" в лог, но не падает — просто нет пола и
# света). Подробности — CLAUDE.md, раздел "Gazebo 11 Classic".

# ВАЖЕН ПОРЯДОК: /usr/share/gazebo/setup.sh сам делает
# export GAZEBO_MODEL_DATABASE_URI=http://models.gazebosim.org — если
# отключить онлайн-базу ДО этой строки, она молча перезатрётся обратно.
if [ -f /usr/share/gazebo/setup.sh ]; then
    source /usr/share/gazebo/setup.sh
else
    echo "WARNING: /usr/share/gazebo/setup.sh не найден — Gazebo 11 установлен?" >&2
fi

export GAZEBO_MODEL_DATABASE_URI=""
