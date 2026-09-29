"""Single source of truth for cross-layer default constants (leaf module: imports nothing)."""

# D-061: kappa_R re-tuned to 60 after the D-043 (eigenvalue clip) and D-057 (soft gating) core fixes
# (scripts/tune_kappa_r.py, tuning seeds 500-504, 600 s, fixed_trust: ANEES_pos = 0.9499 at 60;
# the earlier 40 was tuned before those fixes and gave 1.38). D-067: this constant is what every
# layer (methods, runner, agent, campaign, fleet, dataset builder, scenarios stamp) resolves to.
# ESKFConfig.kappa_R keeps its raw filter default of 1.0; the methods layer applies this value.
DEFAULT_KAPPA_R = 60.0


# D-066 addendum / D-071: TCXO two-state clock model (range units), single source for the truth clock
# (fedqpnt/gnss/signal.py ClockState), ClockKFConfig, and the clock-jump feature normalisation
# (fedqpnt/trust/features.py). Brown & Hwang, Introduction to Random Signals and Applied Kalman
# Filtering, 4th ed., Wiley 2012: h0 = 2e-19 s, h_-2 = 2e-20 1/s (h_-1 = 7e-21 not modelled), as cited in
# Krawinkel & Schon 2021, NAVIGATION, doi:10.1002/navi.444; q_b = h0/2 and q_d = 2 pi^2 h_-2 from
# Qin et al. 2021, Sensors 21:466, doi:10.3390/s21020466; scaled by c^2.
import math as _math

_C = 299_792_458.0
CLOCK_Q_BIAS = 0.5 * _C ** 2 * 2e-19                        # [m^2/s]      ~ 8.99e-3
CLOCK_Q_DRIFT = _C ** 2 * 2.0 * _math.pi ** 2 * 2e-20       # [m^2/s^3]    ~ 3.55e-2
