import numpy as np
import random
import json
from pathlib import Path

from .primitives.planning.planners import PathPlanning
from .primitives.formation.control import FormationControl
from .primitives.engaging.shooting import Shooting


class PrimitiveManager(object):
    def __init__(self, state_manager, physics_client):
        """A base class to perform different primitives.

        Parameters
        ----------
        state_manager : instance
            An instance of state manager
        physics_client : instance
            An instance of pybullet physics_client
        """
        print("Primitive Manager Initialized")
        self.p = physics_client
        self.state_manager = state_manager
        self.dt = self.state_manager.config['simulation']['time_step']

        # Instance of primitives
        self.planning = PathPlanning(self.state_manager.config)
        self.formation = FormationControl()
        self.shooting = Shooting()

        primitive_config = Path(__file__).parents[2] / 'Primitives/PrimitiveConfig.json'
        primitive_config_file = open(primitive_config, 'r')
        config_data = json.load(primitive_config_file)

        return None

    #Can Remain here
    def allocate_action(self, action):
        print("Primitive Manager: allocate_action")
        self.action = action
        self.key = action['vehicles_type'] + '_p_' + str(action['platoon_id'])
        return None

    #Needs to remain here
    def execute_primitive(self):
        """Perform primitive execution
        """
        print("Primitive Manager: execute_primitive")
        done = False
        primitives = {
            'planning': self.planning_primitive,
            'formation': self.formation_primitive,
            'shooting': self.shooting_primitive
        }
        print("self.action['primitive'] is ", self.action['primitive'])
        if self.action['execute'] and self.action[
                'primitive'] in primitives.keys():
            done = primitives[self.action['primitive']]()

        return done
    #Can Remain here
    def make_vehicles_idle(self):
        """Make the vehicles idle
        """
        print("Primitive Manager: make_vehicles_idle")
        for vehicle in self.action['vehicles']:
            vehicle.idle = True
        return None
    #Can Remain here
    def make_vehicles_nonidle(self):
        """Make the vehicles non-idle
        """
        print("Primitive Manager: make_vehicles_nonidle")
        for vehicle in self.action['vehicles']:
            vehicle.idle = False
        return None

    #Can Remain here
    def get_centroid(self):
        """Get the centroid of the vehicles
        """
        print("Primitive Manager: get_centroid")
        centroid = []
        for vehicle in self.action['vehicles']:
            centroid.append(vehicle.current_pos)
        centroid = np.mean(np.asarray(centroid), axis=0)
        return centroid

    #Move out
    def planning_primitive(self):
        """Performs path planning primitive
        """
        print("Primitive Manager: planning_primitive")
        # Make vehicles non idle
        done_rolling = False
        # self.make_vehicles_nonidle()

        # Initial formation
        if self.action['initial_formation']:
            self.dt = 1
            # First point of formation
            self.action['centroid_pos'] = self.get_centroid()
            self.action['next_pos'] = self.action['centroid_pos']
            done = self.formation_primitive()
            if done:
                self.action['initial_formation'] = False
                self.path_points = self.planning.find_path(
                    start=self.action['centroid_pos'],
                    end=self.action['target_pos'])
                self.action['next_pos'] = self.path_points[0]
        else:
            self.dt = 0.025
            self.action['centroid_pos'] = self.get_centroid()
            distance = np.linalg.norm(self.action['centroid_pos'][0:2] -
                                      self.action['next_pos'][0:2])

            if len(self.path_points) > 1 and distance < 0.1:
                self.path_points = np.delete(self.path_points, 0, 0)
                self.action['next_pos'] = self.path_points[0]

            if len(self.path_points) <= 1:
                done_rolling = True

            # Run formation control
            self.formation_primitive()

        if done_rolling:
            self.make_vehicles_idle()
        return done_rolling

    # Move out
    def formation_primitive(self):
        """Performs formation primitive
        """
        print("Primitive Manager: formation_primitive")
        if self.action['primitive'] == 'formation':
            self.action['centroid_pos'] = self.get_centroid()
            self.action['next_pos'] = self.get_centroid()

        self.action['vehicles'], done_rolling = self.formation.execute(
            self.action['vehicles'], self.action['next_pos'],
            self.action['centroid_pos'], self.dt, 'solid')

        for vehicle in self.action['vehicles']:
            vehicle.set_position(vehicle.desired_pos)
        return done_rolling

    #Can remain here
    def plot_path(self):
        print("Primitive Manager: plot_path")
        for point in self.path_points:
            a = self.p.createVisualShape(self.p.GEOM_SPHERE,
                                         radius=1,
                                         rgbaColor=[1, 0, 0, 1],
                                         visualFramePosition=point)

            self.p.createMultiBody(0, baseVisualShapeIndex=a)

    #Move out
    def shooting_primitive(self):
        """Perform shooting primitive
        """
        print("Primitive Manager: shooting_primitive")
        # First point of formation
        self.action['centroid_pos'] = self.get_centroid()
        self.action['next_pos'] = self.action['centroid_pos']

        n_blue_team = self.action['n_blue_team']
        n_red_team = self.action['n_red_team']
        distance = self.action['distance']

        p = self.shooting.shoot(n_blue_team, n_red_team, distance, type='blue')

        if p > 0.95 and random.random() > 0.95:
            # Remove 10% of the drones
            n_vehicles = len(self.action['vehicles'])
            n_remove = int(np.ceil(0.1 * n_vehicles))
            if n_vehicles > 2:
                # Sort is needed to remove the highest index first
                ids_to_remove = random.choices(range(n_vehicles), k=n_remove)
                ids_to_remove.sort(reverse=True)
                for idx in ids_to_remove:
                    self.action['vehicles'][idx].remove_self()
                    self.action['vehicles'][idx].functional = False
                    self.action['vehicles'].pop(idx)

                # Perform formation control
                self.formation_primitive()
            else:
                self.action['execute'] = False
