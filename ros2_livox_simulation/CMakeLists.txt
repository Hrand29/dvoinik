cmake_minimum_required(VERSION 3.5)
project(ros2_livox_simulation)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
add_compile_options(-std=c++17)
# Default to C99
if(NOT CMAKE_C_STANDARD)
  set(CMAKE_C_STANDARD 99)
endif()

# Default to C++14
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 14)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(gazebo_dev REQUIRED)
find_package(gazebo_ros REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(livox_ros_driver2 REQUIRED)
find_package(Boost REQUIRED COMPONENTS chrono)
find_package(rcutils REQUIRED)
# epic_common убран: не найден нигде в системе/workspace (не ROS2-пакет,
# похоже на внутреннюю библиотеку форка-автора), используется только в
# csv_main (отдельная offline-утилита для просмотра scan_mode/*.csv, не
# нужна для самого Gazebo-плагина) — csv_main тоже убран ниже целиком.
# uncomment the following section in order to fill in
# further dependencies manually.
# find_package(<dependency> REQUIRED)
include_directories(
  include
)
include_directories(${GAZEBO_INCLUDE_DIRS})
include_directories(/usr/include/gazebo-11/gazebo)
link_directories(${GAZEBO_LIBRARY_DIRS})



install(DIRECTORY include/
        DESTINATION include
)



add_library(ros2_livox SHARED src/livox_points_plugin.cpp src/livox_ode_multiray_shape.cpp)
target_link_libraries(ros2_livox ${GAZEBO_LIBRARIES} RayPlugin GpuRayPlugin)
ament_target_dependencies(ros2_livox rclcpp std_msgs sensor_msgs geometry_msgs gazebo_dev gazebo_ros tf2_ros livox_ros_driver2 rcutils)
# Было захардкожено libprotobuf.so.9 / libboost_chrono.so.1.71.0 — точных
# версий на этой системе нет (Ubuntu 22.04: protobuf 23, boost 1.74), линковка
# падала. Ни один .cpp плагина protobuf напрямую не использует (нужен Gazebo
# transport'у транзитивно через ${GAZEBO_LIBRARIES}), boost::chrono — через
# нормальный CMake target вместо пути к конкретной .so.
target_link_libraries(ros2_livox Boost::chrono)
target_include_directories(ros2_livox PRIVATE include)

# csv_main (offline-просмотр scan_mode/*.csv) убран — тянул epic_common/glog,
# каких нет в системе, и не нужен для работы самого Gazebo-плагина

install(TARGETS ros2_livox
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_export_libraries(
  ros2_livox
)

set(CSV_FILES
    scan_mode/mid40.csv
    scan_mode/mid70.csv
    scan_mode/mid360.csv
    scan_mode/tele.csv
    scan_mode/horizon.csv
    scan_mode/HAP.csv
    scan_mode/avia.csv
    scan_mode/mid360_vertical.csv
)
foreach(CSV_FILE ${CSV_FILES})
    configure_file(${CSV_FILE} ${CMAKE_CURRENT_BINARY_DIR}/${CSV_FILE} COPYONLY)
    install(FILES ${CMAKE_CURRENT_BINARY_DIR}/${CSV_FILE}
        DESTINATION share/${PROJECT_NAME}/scan_mode
    )
endforeach()

set(URDF_FILES
    urdf/mid40.xacro
    urdf/mid70.xacro
    urdf/mid360.xacro
    urdf/mid360_vertical.xacro
    urdf/tele.xacro
    urdf/horizon.xacro
    urdf/HAP.xacro
    urdf/avia.xacro
)
foreach(URDF_FILES ${URDF_FILES})
    configure_file(${URDF_FILES} ${CMAKE_CURRENT_BINARY_DIR}/${URDF_FILES} COPYONLY)
    install(FILES ${CMAKE_CURRENT_BINARY_DIR}/${URDF_FILES}
        DESTINATION share/${PROJECT_NAME}/urdf
    )
endforeach()

ament_package()
