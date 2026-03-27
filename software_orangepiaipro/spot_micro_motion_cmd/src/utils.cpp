#include "utils.h"

#include <ros/ros.h>
#include <eigen3/Eigen/Geometry>
#include "tf2/LinearMath/Quaternion.h"
#include "tf2_geometry_msgs/tf2_geometry_msgs.h"

using namespace Eigen;
using namespace geometry_msgs;


Affine3d matrix4fToAffine3d(const Matrix4f& in) {
  // Convert a Eigen Matrix4F to an Affine3d by first casting
  // float to double (to a Matrix4d), then calling the constructor for Affine3d
  // with the Matrix4d
  return Affine3d(in.cast<double>());
}


// Create a ROS tf2 TransformStamped from a Eigen Affine3d, 
// parent frame id and child frame id. Stamped with current time, 
// so should be broadcast ASAP
TransformStamped eigAndFramesToTrans(
    const Affine3d& transform, 
    std::string parent_frame_id, std::string child_frame_id) {

  TransformStamped transform_stamped;

  transform_stamped.header.stamp = ros::Time::now();
  transform_stamped.header.frame_id = parent_frame_id;
  transform_stamped.child_frame_id = child_frame_id;

  transform_stamped.transform.translation.x = transform.translation().x();
  transform_stamped.transform.translation.y = transform.translation().y();
  transform_stamped.transform.translation.z = transform.translation().z();

  Eigen::Quaterniond q(transform.rotation());
  transform_stamped.transform.rotation.x = q.x();
  transform_stamped.transform.rotation.y = q.y();
  transform_stamped.transform.rotation.z = q.z();
  transform_stamped.transform.rotation.w = q.w();

  return transform_stamped;
}


// Create a transform from a translation, rotation, and parent and 
// child frame IDs. Will stamp the transform with ros::Time::now(),
// so the returned transform should be broadcast asap
  TransformStamped createTransform(
      std::string parent_frame_id, std::string child_frame_id,
      double x, double y, double z, 
      double roll, double pitch, double yaw) {

  TransformStamped tr_stamped;

  tr_stamped.header.stamp = ros::Time::now();
  tr_stamped.header.frame_id = parent_frame_id;
  tr_stamped.child_frame_id = child_frame_id;

  tr_stamped.transform.translation.x = x;
  tr_stamped.transform.translation.y = y;
  tr_stamped.transform.translation.z = z;
  tf2::Quaternion q;
  q.setRPY(roll, pitch, yaw);
  tr_stamped.transform.rotation.x = q.x();
  tr_stamped.transform.rotation.y = q.y();
  tr_stamped.transform.rotation.z = q.z();
  tr_stamped.transform.rotation.w = q.w();

  return tr_stamped;
}

