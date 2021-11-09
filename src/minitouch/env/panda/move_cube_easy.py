from gym import spaces

import os, inspect
import pybullet as p
import numpy as np
import random
import math
from minitouch.env.panda.panda_haptics import PandaHaptics
from minitouch.env.panda.common.log_specification import LogSpecification
from minitouch.env.panda.common.bound_3d import Bound3d

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(os.path.dirname(currentdir))
os.sys.path.insert(0, parentdir)
urdfRootPath = currentdir + "/assets/"


class MoveCubeEasy(PandaHaptics):

    def __init__(self, threshold_found=0.077, cube_spawn_distance=0.1, sparse_reward_scale=1, random_side=False, sparse_rewards=True,
                 **kwargs):
        super(MoveCubeEasy, self).__init__(**kwargs)
        # Robots bounds for this tasks
        self.objectUid = None
        self.object_file_path = os.path.join(urdfRootPath, "objects/cube/cube.urdf")
        #self.object_file_path = os.path.join(urdfRootPath, "objects/cube/cube_new.urdf")
        self.target_file_path = os.path.join(urdfRootPath, "objects/cube/cube.urdf")

        self.space_limits = Bound3d(0.1, 0.55, -0.20, 0.25, 0, 0.035)

        self.cube_size = 100
        self.sparse_rewards = sparse_rewards
        self.sparse_reward_scale = sparse_reward_scale
        self.random_side = random_side

        self.cube_spawn_distance = cube_spawn_distance

        self.object_start_position = None
        self.target_cube_pos = None

        self.collisionFilterGroup = 0
        self.collisionFilterMask = 0

        self.enable_target_collision = 0
        self.old_distance = 0
        self.random_cube_angle_pos = 0

        self.found = False
        self.treshold_found = threshold_found

        if not random_side:
            self.cube_pos_distribution = spaces.Box(
                low=np.array([self.space_limits.x_low + 0.05, self.space_limits.y_low + 0.05, 0.02]),
                high=np.array(
                    [self.space_limits.x_high - 0.05, self.space_limits.y_high - self.cube_spawn_distance, 0.02]))
        else:
            self.cube_pos_distribution = spaces.Box(
                low=np.array([self.space_limits.x_low + self.cube_spawn_distance,
                              self.space_limits.y_low + self.cube_spawn_distance, 0.02]),
                high=np.array([self.space_limits.x_high - self.cube_spawn_distance,
                               self.space_limits.y_high - self.cube_spawn_distance, 0.02]))

        self.log_specifications = [
            LogSpecification("object_distance", "compute_average", 1, "object_distance"),
            LogSpecification("haptics", "compute_variance", 1, "variance_haptics"),
            LogSpecification("cube_pos", "compute_heat_map_x_y", 10, "cube_pos_heatmap", [0.5, 0.95, -0.20, 0.25]),
            LogSpecification("end_effector_pos", "compute_heat_map_x_y", 10, "end_effector_heatmap",
                             [0.5, 0.95, -0.20, 0.25]),
            LogSpecification("cube_pos", "compute_variance", 1, "cube_pos_variance"),
            LogSpecification("found", "compute_or", 1, "found_cube"),
            LogSpecification("target_cube_angle", "compute_average", 1, "target_cube_angle")

        ]

    def reset(self):
        state = super().reset()
        self.set_cube_positions()
        self.randomize_hand_pos()
        self.place_objects()
        self.old_distance = self.get_distance(self.object_start_position, self.target_cube_pos)
        self.step([0, 0, 0, 0])
        
        self.obj_init_pos = self.get_object_pos()
        
        return state

    def randomize_hand_pos(self):

        # Random position hand around white cube
        random_hand_distance = random.uniform(0.12, 0.14)
        random_angle_hand = self.random_cube_angle_pos + math.pi

        random_radius_hand = random_hand_distance
        random_x_hand = random_radius_hand * math.cos(random_angle_hand)
        random_y_hand = random_radius_hand * math.sin(random_angle_hand)
        init_hand_pos = [self.object_start_position[0] + random_x_hand,
                                self.object_start_position[1] + random_y_hand,
                                self.object_start_position[2]]

        self.move_hand_to(init_hand_pos)

    def set_cube_positions(self):
        self.object_start_position = list(self.cube_pos_distribution.sample())

        random_cube_spawn_distance = random.uniform(0.1, self.cube_spawn_distance)

        if not self.random_side:
            self.target_cube_pos = [self.object_start_position[0], self.object_start_position[1] + random_cube_spawn_distance,
                                    self.object_start_position[2]]
        else:
            self.random_cube_angle_pos = random.uniform(0, 2 * math.pi)
            random_radius = random_cube_spawn_distance
            random_x = random_radius * math.cos(self.random_cube_angle_pos)
            random_y = random_radius * math.sin(self.random_cube_angle_pos)
            self.target_cube_pos = [self.object_start_position[0] + random_x,
                                        self.object_start_position[1] + random_y,
                                        self.object_start_position[2]]


        """
        random_side = random.randint(0, 3)

        self.target_cube_pos = [self.object_start_position[0],
                                    self.object_start_position[1] + random_cube_spawn_distance,
                                    self.object_start_position[2]]
        elif random_side == 1:
            self.target_cube_pos = [self.object_start_position[0],
                                    self.object_start_position[1] - random_cube_spawn_distance,
                                    self.object_start_position[2]]
        elif random_side == 2:
            self.target_cube_pos = [self.object_start_position[0] + random_cube_spawn_distance,
                                    self.object_start_position[1],
                                    self.object_start_position[2]]
        elif random_side == 3:
            self.target_cube_pos = [self.object_start_position[0],
                                    self.object_start_position[1] - random_cube_spawn_distance,
                                    self.object_start_position[2]]
        """


    def place_objects(self):
        self.objectUid = p.loadURDF(self.object_file_path, basePosition=self.object_start_position,
                                    globalScaling=1)

        # p.changeDynamics(self.objectUid, -1, 2)
        self.targetUid = p.loadURDF(self.target_file_path, basePosition=self.target_cube_pos,
                                    globalScaling=1, useFixedBase=True)

        p.setCollisionFilterGroupMask(self.targetUid, -1, self.collisionFilterGroup, self.collisionFilterMask)
        p.setCollisionFilterPair(self.pandaUid, self.targetUid, -1, -1, self.enable_target_collision)

        p.changeVisualShape(self.targetUid, -1,
                            rgbaColor=[0.7, 0.7, 0.7, 1])

    def step(self, action):
        step, reward, done, info = super().step(action)
        self.old_distance = self.get_distance(self.get_object_pos(), self.target_cube_pos)
        return step, reward, done, info

    def _get_done(self):
        if self.get_distance(self.get_object_pos(), self.target_cube_pos) < self.treshold_found:
            return 1
        elif not self.space_limits.is_inside(self.get_object_pos()):
            return 1
        # else:
        return 0

    def get_object_pos(self):
        return p.getBasePositionAndOrientation(self.objectUid)[0]

    def get_object_distance(self):
        """
        Get distance between end effector and  object.
        :return: eucledian distance
        """
        return self.get_distance(self.get_object_pos(), self.get_end_effector_pos())

    def _get_info(self):
        found = self.get_distance(self.get_object_pos(), self.target_cube_pos) < self.treshold_found

        return {"haptics": self._get_haptics(), "object_distance": self.get_object_distance(),
                "cube_pos": self.get_object_pos(), "fingers_pos": self.get_fingers_pos(),
                "end_effector_pos": self.get_end_effector_pos(), "found": found, "target_cube_angle": self.random_cube_angle_pos}

    def _get_reward(self):
        if self.get_distance(self.get_object_pos(), self.target_cube_pos) < self.treshold_found:
            return self.sparse_reward_scale
        else:
            return 0

    # def _get_sparse_reward(self):
    #     return 0
    
    # # Folowing functions taken from meta-world dense reward for push task
    # # https://github.com/rlworkgroup/metaworld/blob/a0009ed9a208ff9864a5c1368c04c273bb20dd06/metaworld/envs/mujoco/sawyer_xyz/v2/sawyer_push_v2.py#L104
    
    # def _get_dense_reward(self):
    #     # obj = obs[4:7]
    #     # tcp_opened = obs[3]
    #     # tcp_to_obj = np.linalg.norm(obj - self.tcp_center)
    #     # target_to_obj = np.linalg.norm(obj - self._target_pos)
    #     # target_to_obj_init = np.linalg.norm(self.obj_init_pos - self._target_pos)
        
    #     obj = self.get_object_pos()
    #     tcp_opened = self.get_fingers_pos()
    #     tcp_to_obj = np.linalg.norm(obj - self.get_end_effector_pos())
    #     target_to_obj = np.linalg.norm(obj - self.target_cube_pos)
    #     target_to_obj_init = np.linalg.norm(self.obj_init_pos - self.target_cube_pos)

    #     in_place = self.tolerance(
    #         target_to_obj,
    #         bounds=(0, self.treshold_found),
    #         margin=target_to_obj_init,
    #         sigmoid='long_tail',
    #     )

    #     object_grasped = self._gripper_caging_reward(
    #         action,
    #         obj,
    #         object_reach_radius=0.01,
    #         obj_radius=0.015,
    #         pad_success_thresh=0.05,
    #         xz_thresh=0.005,
    #         high_density=True
    #     )
    #     reward = 2 * object_grasped

    #     if tcp_to_obj < 0.02 and tcp_opened > 0:
    #         reward += 1. + reward + 5. * in_place
    #     if target_to_obj < self.TARGET_RADIUS:
    #         reward = 10.

    #     return (
    #         reward,
    #         tcp_to_obj,
    #         tcp_opened,
    #         target_to_obj,
    #         object_grasped,
    #         in_place
    #     )
    
