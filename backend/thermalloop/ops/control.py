"""Reusable goal-seeking controllers for the agents.

The first-generation agents used fixed thresholds ("if temp > 42 trim to 0.7").
That is coarse and chatters. These controllers let an agent hold a *setpoint*
smoothly and adapt over time, which is what turns the agents from reactive
switches into genuine operators.

Everything here is deterministic and anti-windup-protected. No randomness, no
hidden state beyond the integral term, so runs stay reproducible for a seed.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PIController:
    """Proportional-Integral controller with output clamping + anti-windup.

    ``kp``/``ki`` are the gains, ``out_min``/``out_max`` clamp the command.
    ``direction`` is +1 when raising the command raises the measured value, or
    -1 when raising the command *lowers* it (e.g. more pump flow lowers
    temperature). The controller is framed so a positive error (setpoint above
    measurement) always drives the command the correct way.
    """

    kp: float
    ki: float
    out_min: float
    out_max: float
    direction: float = 1.0
    integral: float = 0.0
    last_error: float = 0.0
    last_output: float = 0.0

    def reset(self) -> None:
        self.integral = 0.0
        self.last_error = 0.0
        self.last_output = 0.0

    def update(self, setpoint: float, measured: float, dt_s: float) -> float:
        error = (setpoint - measured) * self.direction
        # Tentative integral, then clamp output and only keep integral growth
        # that does not push the (already saturated) output further out.
        tentative_integral = self.integral + error * dt_s
        raw = self.kp * error + self.ki * tentative_integral
        clamped = max(self.out_min, min(self.out_max, raw))
        if clamped == raw or (clamped > raw) == (error < 0):
            # not saturating in the windup direction -> accept the integral
            self.integral = tentative_integral
        self.last_error = error
        self.last_output = clamped
        return clamped


@dataclass
class AdaptiveGain:
    """Tiny self-tuner: nudges a gain based on tracking performance.

    If the controller keeps overshooting (error sign flips often) it lowers the
    gain; if it is sluggish (persistent same-sign error) it raises it, within
    bounds. This is the "measure the result -> adjust" step made concrete, and
    it is bounded + deterministic so it cannot run away.
    """

    gain: float
    lo: float
    hi: float
    step: float = 0.05
    _sign_flips: int = 0
    _same_sign: int = 0
    _prev_error: float = 0.0
    history: list[float] = field(default_factory=list)

    def observe(self, error: float) -> float:
        if self._prev_error != 0.0:
            if (error > 0) != (self._prev_error > 0):
                self._sign_flips += 1
                self._same_sign = 0
            else:
                self._same_sign += 1
                self._sign_flips = max(0, self._sign_flips - 1)
        self._prev_error = error
        if self._sign_flips >= 3:            # oscillating -> calm down
            self.gain = max(self.lo, self.gain - self.step)
            self._sign_flips = 0
        elif self._same_sign >= 5 and abs(error) > 0.5:  # sluggish -> push
            self.gain = min(self.hi, self.gain + self.step)
            self._same_sign = 0
        self.history.append(self.gain)
        return self.gain
