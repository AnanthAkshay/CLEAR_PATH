"""ClearPath Reinforcement Learning module for junction control.

Provides:
- ClearPathGridEnv: Gym-style environment for 3x3 grid junction control.
- QNetwork: Lightweight, vectorized neural network Q-learning with Adam in NumPy.
- train_policy: Independent Q-learning with parameter sharing across junctions.
- SharedJunctionPolicy: Wrapper for policy inference during simulation.
"""

from clearpath.rl.env import ClearPathGridEnv

__all__ = ["ClearPathGridEnv"]

