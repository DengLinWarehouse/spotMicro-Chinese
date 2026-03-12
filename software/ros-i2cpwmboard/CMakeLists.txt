cmake_minimum_required(VERSION 2.8.3)
project(i2cpwm_board)

find_package(catkin REQUIRED COMPONENTS roscpp std_msgs message_generation)


add_message_files(DIRECTORY msg FILES Servo.msg ServoArray.msg ServoConfig.msg ServoConfigArray.msg Position.msg PositionArray.msg)

add_service_files(DIRECTORY srv FILES IntValue.srv ServosConfig.srv DriveMode.srv StopServos.srv)

generate_messages(DEPENDENCIES std_msgs)


catkin_package(CATKIN_DEPENDS roscpp std_msgs message_runtime)


include_directories(include  ${catkin_INCLUDE_DIRS})
link_directories(${catkin_LIBRARY_DIRS})


find_library(I2C_LIB i2c)

add_executable(i2cpwm_board src/i2cpwm_controller.cpp)
target_link_libraries(i2cpwm_board ${catkin_LIBRARIES} ${I2C_LIB})
add_dependencies(i2cpwm_board i2cpwm_board_generate_messages_cpp)

install(TARGETS i2cpwm_board
    RUNTIME DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION} 
	LIBRARY DESTINATION ${CATKIN_PACKAGE_LIB_DESTINATION} 
	ARCHIVE DESTINATION ${CATKIN_PACKAGE_LIB_DESTINATION} 
)
install(DIRECTORY include/${PROJECT_NAME}/ DESTINATION ${CATKIN_PACKAGE_INCLUDE_DESTINATION} FILES_MATCHING PATTERN "*.h" )
install(DIRECTORY launch/ DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/launch )

option(I2CPWM_BUILD_DOCS "Generate Doxygen documentation as part of the build" OFF)
if(I2CPWM_BUILD_DOCS)
  find_package(Doxygen QUIET)
  if(DOXYGEN_FOUND)
    message(STATUS "Enabling Doxygen documentation for ros-i2cpwmboard")
    add_custom_target(i2cpwmboard_doxygen ALL
      COMMAND ${DOXYGEN_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/doc/Doxyfile
      WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
      COMMENT "Generating Doxygen docs for ros-i2cpwmboard")
  else()
    message(WARNING "Doxygen not found, unable to build ros-i2cpwmboard docs")
  endif()
endif()
