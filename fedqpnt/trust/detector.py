"""Learnable spoof/jam detector, ARCHITECTURE.md §3.2 (WP-4.2, TRUST agent).

``f_theta``: MLP 52 -> 16 (tanh) -> 2 (sigmoid), heads p_spoof / p_jam,
p = max(p_spoof, p_jam). 882 parameters (52*16+16 + 16*2+2 = 832+34+... see
``TrustMLP.n_params``). ``detector.arch = "logreg"`` is the required ablation
(52 -> 2 linear + sigmoid, no hidden layer). ``torch.set_num_threads(1)`` is
set at import time per the spec (one thread per process, many processes in
the FL simulation).

Feature normalisation (§4.2): running mean/std per raw feature (13,),
updated ONLY on pseudo-label-NEGATIVE samples (so an ongoing attack does not
pollute the "clean" reference distribution), aggregated across nodes by
coordinate-wise MEDIAN (not mean) -- the median aggregation itself is FL
server-side code (owned by the FEDERATED agent); this module only exposes
the local running stats via ``get_params``/``set_params`` so that later
code can do so.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import torch
import torch.nn as nn

torch.set_num_threads(1)

from fedqpnt.trust.features import N_FEATURES

STACK_DIM = 4 * N_FEATURES  # 52


@dataclass
class FeatureNormalizer:
    """Running mean/std over raw (13,) features, updated on negative
    (pseudo-label y=0) samples only. ``mu``/``sd`` seed at (0, 1) so an
    untrained node degrades to "no normalisation" rather than div-by-zero."""

    n: int = N_FEATURES
    mu: np.ndarray = field(default_factory=lambda: np.zeros(N_FEATURES))
    m2: np.ndarray = field(default_factory=lambda: np.zeros(N_FEATURES))  # Welford accumulator
    count: float = 0.0
    min_sd: float = 1e-3

    def update(self, x: np.ndarray) -> None:
        self.count += 1.0
        delta = x - self.mu
        self.mu = self.mu + delta / self.count
        delta2 = x - self.mu
        self.m2 = self.m2 + delta * delta2

    @property
    def sd(self) -> np.ndarray:
        if self.count < 2:
            return np.ones(self.n)
        var = self.m2 / max(self.count - 1, 1.0)
        return np.sqrt(np.maximum(var, self.min_sd ** 2))

    def normalize(self, x: np.ndarray) -> np.ndarray:
        return (x - self.mu) / self.sd

    def get_params(self) -> dict[str, np.ndarray]:
        return {"norm_mu": self.mu.copy(), "norm_sd": self.sd.copy(), "norm_count": np.array([self.count])}

    def set_params(self, params: dict[str, np.ndarray]) -> None:
        self.mu = np.asarray(params["norm_mu"], dtype=np.float64).copy()
        sd = np.asarray(params["norm_sd"], dtype=np.float64)
        # store as m2 consistent with a fresh count so `sd` round-trips exactly
        self.count = float(params.get("norm_count", np.array([max(self.count, 2.0)]))[0])
        self.m2 = (sd ** 2) * max(self.count - 1, 1.0)


class TrustMLP(nn.Module):
    """52 -> 16 (tanh) -> 2 (sigmoid). 882 parameters."""

    def __init__(self, in_dim: int = STACK_DIM, hidden: int = 16):
        super().__init__()
        self.fc1 = nn.Linear(in_dim, hidden)
        self.fc2 = nn.Linear(hidden, 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = torch.tanh(self.fc1(x))
        return torch.sigmoid(self.fc2(h))

    @property
    def n_params(self) -> int:
        return sum(p.numel() for p in self.parameters())


class LogRegDetector(nn.Module):
    """Ablation: 52 -> 2 linear + sigmoid, no hidden layer/non-linearity."""

    def __init__(self, in_dim: int = STACK_DIM):
        super().__init__()
        self.fc = nn.Linear(in_dim, 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.fc(x))


def _param_dict(model: nn.Module) -> dict[str, np.ndarray]:
    return {name: p.detach().cpu().numpy().copy() for name, p in model.named_parameters()}


def _load_param_dict(model: nn.Module, params: dict[str, np.ndarray]) -> None:
    with torch.no_grad():
        for name, p in model.named_parameters():
            if name in params:
                p.copy_(torch.as_tensor(np.asarray(params[name], dtype=np.float32)))


@dataclass
class TrustDetector:
    """Wraps normalizer + EWMA-stacker + MLP/logreg into one causal-inference
    + trainable object. ``score`` is causal (feed one raw (13,) vector per
    GNSS epoch, in order); ``train_local`` is the (non-causal, offline)
    local-SGD step the FL client wraps.
    """

    arch: Literal["mlp", "logreg"] = "mlp"
    seed: int = 0
    normalizer: FeatureNormalizer = field(default_factory=FeatureNormalizer)

    def __post_init__(self) -> None:
        torch.manual_seed(self.seed)
        self.model: nn.Module = TrustMLP() if self.arch == "mlp" else LogRegDetector()
        from fedqpnt.trust.features import EwmaStack
        self._stack = EwmaStack()

    def reset_stream(self) -> None:
        self._stack.reset()

    def score(self, t: float, raw_features: np.ndarray) -> tuple[float, float, np.ndarray]:
        """Causal single-step inference. Returns (p_spoof, p_jam, u_52)."""
        xtilde = self.normalizer.normalize(raw_features)
        u = self._stack.step(t, xtilde)
        with torch.no_grad():
            out = self.model(torch.as_tensor(u, dtype=torch.float32)).numpy()
        return float(out[0]), float(out[1]), u

    def get_params(self) -> dict[str, np.ndarray]:
        p = _param_dict(self.model)
        p.update(self.normalizer.get_params())
        return p

    def set_params(self, params: dict[str, np.ndarray]) -> None:
        _load_param_dict(self.model, params)
        if "norm_mu" in params:
            self.normalizer.set_params(params)

    def train_local(
        self,
        U: np.ndarray,             # (N, 52) already-stacked+normalised features (non-causal batch OK: this is offline training)
        y_spoof: np.ndarray,       # (N,) in {0,1}
        y_jam: np.ndarray,         # (N,) in {0,1}
        epochs: int = 2,
        lr: float = 0.05,
        batch_size: int = 64,
        prox_mu: float = 0.01,
        theta_g: dict[str, np.ndarray] | None = None,
        rng: np.random.Generator | None = None,
        max_pos_fraction: float = 0.5,
        balance: bool = True,
        n_min: int = 10,
    ) -> dict[str, float]:
        """§4.2 local SGD step with an optional FedProx term. Returns
        ``{"n_pos", "n_neg", "loss", "pl_rate"}`` (the only metrics §4.1
        allows to leave the node).

        D-026: mirrors §4.2's FL replay-buffer design rule ("class-balanced
        reservoir: at most 50% positives") for LOCAL training too, via
        SAMPLING (down-sampling the majority/positive class to the cap),
        not loss re-weighting -- this is a design rule, not a tuning knob,
        so it is applied unconditionally when ``balance=True`` (default).
        The class-weighted BCE below is kept in addition (harmless once the
        sample is already ~balanced) but is not what enforces the cap.

        PROPOSED-DECISION (D-039): "balance-rule dead zone" fix. With very
        few negatives (``n_neg < n_min``), the subsampling cap
        ``max_pos_kept = n_neg * max_pos_fraction/(1-max_pos_fraction)``
        rounds down to ~0, so historically ALL samples were dropped
        (including every positive) and the SGD loop never ran -- a node
        could go arbitrarily many rounds without training at all purely
        from having drawn too few negative pseudo-labels, which is a
        correctness bug (found via a downstream FL validation artifact,
        D-037/D-039), not a tuning choice. Below ``n_min`` samples per the
        minority class, subsampling is skipped entirely and the model
        trains on ALL available samples, relying on the existing inverse-
        class-frequency loss weights (``w_pos``/``w_neg`` below) instead.
        ``n_min = 10`` is a conservative default: large enough that a
        single negative doesn't dominate a whole batch's weighting, small
        enough that the dead zone (previously "always" when n_neg=0) is
        actually closed. At or above ``n_min`` negatives, the original
        subsampling behaviour (unchanged) applies.
        """
        rng = rng or np.random.default_rng(0)
        n = U.shape[0]
        if n == 0:
            return {"n_pos": 0.0, "n_neg": 0.0, "loss": float("nan"), "pl_rate": 0.0}

        if balance:
            pos_mask = (y_spoof > 0) | (y_jam > 0)
            neg_idx = np.flatnonzero(~pos_mask)
            pos_idx = np.flatnonzero(pos_mask)
            if len(neg_idx) < n_min:
                # Dead-zone fix: too few negatives to subsample meaningfully
                # against -- train on everything, lean on class weighting.
                keep = np.arange(n)
            else:
                # cap: n_pos_kept / (n_pos_kept + n_neg) <= max_pos_fraction
                max_pos_kept = int(len(neg_idx) * max_pos_fraction / max(1 - max_pos_fraction, 1e-9))
                if len(pos_idx) > max_pos_kept:
                    pos_idx = rng.choice(pos_idx, size=max_pos_kept, replace=False)
                keep = np.sort(np.concatenate([neg_idx, pos_idx]))
            U, y_spoof, y_jam = U[keep], y_spoof[keep], y_jam[keep]
            n = U.shape[0]
            if n == 0:
                return {"n_pos": 0.0, "n_neg": 0.0, "loss": float("nan"), "pl_rate": 0.0}

        n_pos = float(np.sum((y_spoof > 0) | (y_jam > 0)))
        n_neg = float(n - n_pos)
        w_pos = n / max(2 * n_pos, 1.0)
        w_neg = n / max(2 * n_neg, 1.0)

        opt = torch.optim.SGD(self.model.parameters(), lr=lr)
        theta_g_t = None
        if theta_g is not None and prox_mu > 0:
            theta_g_t = {k: torch.as_tensor(np.asarray(v, dtype=np.float32)) for k, v in theta_g.items()}

        Ut = torch.as_tensor(U, dtype=torch.float32)
        yt = torch.as_tensor(np.stack([y_spoof, y_jam], axis=1), dtype=torch.float32)
        weight = torch.where(yt > 0, w_pos, w_neg)

        losses = []
        for _ in range(epochs):
            idx = rng.permutation(n)
            for start in range(0, n, batch_size):
                bidx = idx[start:start + batch_size]
                xb, yb, wb = Ut[bidx], yt[bidx], weight[bidx]
                opt.zero_grad()
                pred = self.model(xb)
                bce = nn.functional.binary_cross_entropy(pred, yb, weight=wb, reduction="mean")
                if theta_g_t is not None:
                    prox = sum(((p - theta_g_t[name]) ** 2).sum()
                               for name, p in self.model.named_parameters() if name in theta_g_t)
                    bce = bce + 0.5 * prox_mu * prox
                bce.backward()
                opt.step()
                losses.append(float(bce.detach()))
        return {"n_pos": n_pos, "n_neg": n_neg, "loss": float(np.mean(losses)), "pl_rate": n_pos / n}
