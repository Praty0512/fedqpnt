"""Single source of truth for cross-layer default constants (leaf module: imports nothing)."""

# D-061: kappa_R re-tuned to 60 after the D-043 (eigenvalue clip) and D-057 (soft gating) core fixes
# (scripts/tune_kappa_r.py, tuning seeds 500-504, 600 s, fixed_trust: ANEES_pos = 0.9499 at 60;
# the earlier 40 was tuned before those fixes and gave 1.38). D-067: this constant is what every
# layer (methods, runner, agent, campaign, fleet, dataset builder, scenarios stamp) resolves to.
# ESKFConfig.kappa_R keeps its raw filter default of 1.0; the methods layer applies this value.
DEFAULT_KAPPA_R = 60.0
