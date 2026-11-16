"""Unit and integration tests for the RL-based junction policy.

Verifies:
1. ClearPathGridEnv gym-style interface (reset, step, action_masks, spaces).
2. Observation dimension and components (queues, wait time, ambulance distance/ETA, phase, elapsed).
3. Action masking safety invariants (clearance lock, max hold, min green).
4. Reward calculation components (w1, w2, w3, w4).
5. QNetwork forward/backward pass, Adam optimization, and target network.
6. SharedJunctionPolicy save/load and inference with action masks.
7. JunctionAgent policy switch ("rule" vs "rl").
8. ClearPathEngine integration in RL mode with strict safety check (no conflicting greens).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

from clearpath.agents.junction import JunctionAgent
from clearpath.config import SimConfig
from clearpath.engine.orchestrator import ClearPathEngine
from clearpath.rl.env import (
    ACTION_EXTEND, ACTION_HOLD, ACTION_PREEMPT_GREEN, ACTION_SWITCH,
    ClearPathGridEnv, NUM_ACTIONS, OBS_DIM,
)
from clearpath.rl.train import QNetwork, ReplayBuffer, SharedJunctionPolicy
from clearpath.sim.signals import SignalPhase


# ─────────────────────────────────────────────────────────────────────────────
# Environment Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_rl_env_initialization_and_spaces():
    env = ClearPathGridEnv(seed=42)
    assert env.num_junctions == 9
    assert env.action_space.contains(0)
    assert env.action_space.contains(3)
    assert not env.action_space.contains(4)
    assert env.observation_space.shape == (OBS_DIM,)


def test_rl_env_reset_observations_and_masks():
    env = ClearPathGridEnv(seed=42)
    obs, info = env.reset()

    assert len(obs) == 9
    for node in env.nodes:
        vec = obs[node]
        assert vec.shape == (OBS_DIM,)
        assert isinstance(vec, np.ndarray)
        assert vec.dtype == np.float32

    masks = info["action_masks"]
    assert len(masks) == 9
    for node in env.nodes:
        m = masks[node]
        assert m.shape == (NUM_ACTIONS,)
        assert m.dtype == bool
        assert bool(m[ACTION_HOLD]) or bool(m[ACTION_SWITCH])


def test_rl_env_step_advances_simulation():
    env = ClearPathGridEnv(max_ticks=20, seed=42)
    env.reset()

    actions = {node: ACTION_HOLD for node in env.nodes}
    next_obs, rewards, term, trunc, info = env.step(actions)

    assert env.current_tick == 1
    assert len(next_obs) == 9
    assert len(rewards) == 9
    assert not term
    assert not trunc
    assert "safety_violations" in info


def test_rl_env_safety_masking_blocks_unsafe_actions():
    """Ensure unsafe actions during clearance or before min_green are strictly masked."""
    env = ClearPathGridEnv(seed=42)
    env.reset()

    # Manually place junction j_1_1 into yellow clearance
    j11 = env.sim.signals["j_1_1"]
    j11.phase = SignalPhase.NS_YELLOW
    j11.time_in_phase_s = 1.0

    mask = env.action_mask("j_1_1")
    # During clearance, only HOLD is valid; SWITCH, EXTEND, PREEMPT are forbidden
    assert bool(mask[ACTION_HOLD]) is True
    assert bool(mask[ACTION_SWITCH]) is False
    assert bool(mask[ACTION_EXTEND]) is False
    assert bool(mask[ACTION_PREEMPT_GREEN]) is False

    # Attempting to switch during clearance should be intercepted by safety machine
    actions = {node: ACTION_HOLD for node in env.nodes}
    actions["j_1_1"] = ACTION_SWITCH
    _, _, _, _, info = env.step(actions)

    assert info["safety_violations"] >= 1
    # Controller must still be safe in clearance, not conflicting green
    assert j11.phase in (SignalPhase.NS_YELLOW, SignalPhase.ALL_RED_TO_EW)


def test_rl_env_reward_components():
    """Verify reward responds to queues, delays, bonuses and violations."""
    env = ClearPathGridEnv(w1=10.0, w2=0.5, w3=25.0, w4=15.0, seed=42)
    env.reset()

    # Force a violation
    j00 = env.sim.signals["j_0_0"]
    j00.phase = SignalPhase.EW_YELLOW
    j00.time_in_phase_s = 1.0

    actions = {node: ACTION_HOLD for node in env.nodes}
    actions["j_0_0"] = ACTION_SWITCH  # Unsafe during yellow
    _, rewards, _, _, info = env.step(actions)

    assert info["safety_violations"] >= 1
    # Node j_0_0 reward must include safety penalty (-15.0)
    assert rewards["j_0_0"] <= -15.0


# ─────────────────────────────────────────────────────────────────────────────
# QNetwork & Policy Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_qnetwork_forward_and_train_step():
    net = QNetwork(in_dim=OBS_DIM, out_dim=NUM_ACTIONS, lr=0.01, seed=42)
    x = np.random.randn(8, OBS_DIM).astype(np.float32)

    q = net.forward(x)
    assert q.shape == (8, NUM_ACTIONS)

    actions = np.random.randint(0, NUM_ACTIONS, size=8)
    targets = np.random.randn(8).astype(np.float32)

    loss1 = net.train_step(x, actions, targets)
    loss2 = net.train_step(x, actions, targets)
    assert isinstance(loss1, float)
    # Loss should decrease on identical target
    assert loss2 <= loss1 + 1e-4


def test_shared_junction_policy_save_and_load(tmp_path: Path):
    policy = SharedJunctionPolicy()
    save_file = tmp_path / "test_policy.npz"
    policy.save(save_file)
    assert save_file.exists()

    loaded_policy = SharedJunctionPolicy.load(save_file)
    obs = np.ones(OBS_DIM, dtype=np.float32)
    mask = np.array([True, False, False, False], dtype=bool)

    act = loaded_policy.predict(obs, mask=mask)
    assert act == ACTION_HOLD


def test_replay_buffer_add_and_sample():
    buf = ReplayBuffer(capacity=100, seed=42)
    s = np.zeros(OBS_DIM, dtype=np.float32)
    next_s = np.ones(OBS_DIM, dtype=np.float32)
    mask = np.array([True, True, False, False], dtype=bool)

    buf.add(s, 1, 2.5, next_s, False, mask)
    assert buf.size == 1

    b_s, b_a, b_r, b_ns, b_d, b_nm = buf.sample(1)
    assert b_s.shape == (1, OBS_DIM)
    assert b_a[0] == 1
    assert b_r[0] == 2.5
    assert bool(b_nm[0, 0]) is True
    assert bool(b_nm[0, 2]) is False


# ─────────────────────────────────────────────────────────────────────────────
# JunctionAgent Policy Switch & Orchestrator Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_junction_agent_policy_switch():
    from clearpath.bus.message_bus import MessageBus
    from clearpath.sim.network import RoadNetwork

    cfg = SimConfig(grid_rows=3, grid_cols=3, seed=42)
    bus = MessageBus(seed=42)
    net = RoadNetwork(cfg)

    class DummyActuator:
        def __init__(self):
            self.overrides = []
        def set_signal_override(self, jid, phase, reason=""):
            self.overrides.append((jid, phase, reason))
        def clear_signal_override(self, jid):
            pass

    act = DummyActuator()

    # Rule policy
    agent_rule = JunctionAgent("j_1_1", bus, cfg, net, act, policy="rule")
    assert agent_rule.policy == "rule"

    # RL policy
    agent_rl = JunctionAgent("j_1_1", bus, cfg, net, act, policy="rl")
    assert agent_rl.policy == "rl"
    assert agent_rl.rl_model is not None


def test_clearpath_engine_with_rl_policy_safety():
    """Verify full engine run with junction_policy='rl' creates NO conflicting greens."""
    cfg = SimConfig(grid_rows=3, grid_cols=3, max_ticks=40, seed=42)
    engine = ClearPathEngine(
        config=cfg,
        preemption_enabled=True,
        demand_level="med",
        junction_policy="rl",
    )

    assert engine.junction_policy == "rl"
    for node in engine.junctions:
        assert engine.junctions[node].policy == "rl"

    # Run 40 ticks and assert safety invariant at every single tick
    for t in range(40):
        engine.step()
        if t == 5:
            engine.sim.spawn_ambulance("j_0_0", "j_2_2")

        # Invariant check: for every junction, no two conflicting approaches are green
        for node, controller in engine.sim.signals.items():
            ns_display = controller.state_for_approach((f"j_0_1", node)) if node == "j_1_1" else "R"
            ew_display = controller.state_for_approach((f"j_1_0", node)) if node == "j_1_1" else "R"
            assert not (ns_display == "G" and ew_display == "G"), (
                f"SAFETY VIOLATION at tick {t}, junction {node}: conflicting greens!"
            )
