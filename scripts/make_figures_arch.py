"""
Generate publication-quality architecture figures for FedQPNT (WP-1.1 spec).

Owner: VISUALIZATION agent. Reads only docs/specs/ARCHITECTURE.md,
docs/specs/TRUST_DESIGN_V2.md and DECISION_LOG D-011 for labels/parameters —
no numbers are invented here.

Outputs (figures/):
  fig_architecture.{pdf,png}       - fleet / node boundary / FL server
  fig_closed_loop.{pdf,png}        - per-tick closed loop (a)-(j)
  fig_trust_state_machine.{pdf,png}- trust law v2 TRUST/DISTRUST/PROBE FSM
  fig_fl_protocol.{pdf,png}        - FL round timeline

Widths follow IEEE two-column: single-column 3.5 in, full-width 7.16 in.
Colour-blind-safe palette: Okabe-Ito.
Run: python scripts/make_figures_arch.py
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle
from matplotlib.lines import Line2D

# ---------------------------------------------------------------- style ----
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["DejaVu Serif", "Times New Roman", "Times"],
    "font.size": 7.5,
    "axes.linewidth": 0.7,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
})

# Okabe-Ito colour-blind-safe palette
C_BLACK = "#000000"
C_ORANGE = "#E69F00"
C_SKY = "#56B4E9"
C_GREEN = "#009E73"
C_YELLOW = "#F0E442"
C_BLUE = "#0072B2"
C_VERM = "#D55E00"
C_PURPLE = "#CC79A7"
C_GREY = "#7F7F7F"

FIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "figures")
os.makedirs(FIG_DIR, exist_ok=True)

IN_1COL = 3.5
IN_2COL = 7.16


def save(fig, name):
    pdf = os.path.join(FIG_DIR, f"{name}.pdf")
    png = os.path.join(FIG_DIR, f"{name}.png")
    fig.savefig(pdf, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(png, dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(f"wrote {pdf}\nwrote {png}")


def box(ax, xy, w, h, text, fc="white", ec=C_BLACK, lw=0.8, fs=7.0, style="round,pad=0.02,rounding_size=0.02",
        zorder=3, weight="normal", text_color=C_BLACK):
    x, y = xy
    p = FancyBboxPatch((x, y), w, h, boxstyle=style, fc=fc, ec=ec, lw=lw, zorder=zorder)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
             zorder=zorder + 1, weight=weight, color=text_color)
    return p


def arrow(ax, p0, p1, color=C_BLACK, lw=0.9, style="-|>", ls="-", mut=6, zorder=2, connstyle=None):
    a = FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=mut, color=color, lw=lw,
                         ls=ls, shrinkA=0, shrinkB=0, zorder=zorder,
                         connectionstyle=connstyle)
    ax.add_patch(a)
    return a


# ============================================================ FIGURE 1 =====
# fig_architecture: fleet of nodes, Environment/Agent split, node boundary,
# FL server, only-model-updates crossing.
def fig_architecture():
    fig, ax = plt.subplots(figsize=(IN_2COL, 4.3))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 59)
    ax.axis("off")

    # --- FL server: wide enough that a vertical line from every node's Agent column
    # (row-0 box) reaches its bottom edge without slanting. ---
    sx, sy, sw, sh = 19, 47, 79, 9.0
    box(ax, (sx, sy), sw, sh,
        "FL Server\nTRIM-NB-R aggregator (§4.5)\nnode-id-order aggregation, reputation, quarantine",
        fc=C_YELLOW, fs=6.4, weight="bold")

    def draw_node(cx, label):
        """One node: Environment column (left, 4 stacked items) | boundary channel |
        Agent column (right, row0 detector+trust/FL client, rows1-2 one tall ES-EKF+clock-KF
        box, row3 receiver). All sensor-crossing arrows are horizontal, row-aligned.
        Returns geometry the caller needs to attach the uplink/downlink arrows."""
        w, h = 30, 30
        we, gap = 12, 5                       # Environment width, boundary-channel width (widened)
        agt_w = w - we - gap
        x0 = cx - w / 2
        env_x0, env_x1 = x0, x0 + we
        gap_x0, gap_x1 = env_x1, env_x1 + gap
        agt_x0, agt_x1 = gap_x1, gap_x1 + agt_w
        y0 = 6

        box(ax, (env_x0, y0), we, h, "", fc="#EAF3FB", ec=C_GREY, lw=0.6, style="square,pad=0")
        box(ax, (agt_x0, y0), agt_w, h, "", fc="#EAF7F1", ec=C_GREY, lw=0.6, style="square,pad=0")
        ax.add_patch(Rectangle((x0, y0), w, h, fc="none", ec=C_BLACK, lw=1.3, zorder=4))
        gap_c = (gap_x0 + gap_x1) / 2
        ax.plot([gap_c, gap_c], [y0, y0 + h], color=C_BLACK, lw=1.3, ls=(0, (3, 1.5)), zorder=4)
        env_c, agt_c = (env_x0 + env_x1) / 2, (agt_x0 + agt_x1) / 2
        ax.text(env_c, y0 + h + 1.1, "Environment", ha="center", va="bottom", fontsize=6.1, style="italic")
        ax.text(agt_c, y0 + h + 1.1, "Agent", ha="center", va="bottom", fontsize=6.1, style="italic")
        ax.text(cx, y0 - 1.0, label, ha="center", va="top", fontsize=7.2, weight="bold")

        n = 4
        ih = h / n

        def row_y(i):  # bottom edge (data y) of row i, 0 = top row .. n-1 = bottom row
            return y0 + h - (i + 1) * ih

        env_items = ["truth\n(TruthState)", "IMU model", "CAI (quantum)", "GNSS signal +\nattacks"]
        env_c_pt = {}
        for i, it in enumerate(env_items):
            iy = row_y(i)
            box(ax, (env_x0 + 0.6, iy + 0.6), we - 1.2, ih - 1.2, it, fc="white", lw=0.5, fs=5.0)
            env_c_pt[i] = (env_x1, iy + ih / 2)

        # Agent: row0 detector+trust/FL client; rows1-2 one tall ES-EKF+clock-KF box; row3 receiver
        r0y = row_y(0)
        box(ax, (agt_x0 + 0.6, r0y + 0.6), agt_w - 1.2, ih - 1.2,
            "detector + trust\nengine / FL client\n(§3–4)", fc="white", lw=0.5, fs=4.6)
        r12y = row_y(2)
        box(ax, (agt_x0 + 0.6, r12y + 0.6), agt_w - 1.2, 2 * ih - 1.2,
            "ES-EKF (§2)\n+ clock KF", fc="white", lw=0.5, fs=5.2)
        r3y = row_y(3)
        box(ax, (agt_x0 + 0.6, r3y + 0.6), agt_w - 1.2, ih - 1.2,
            "receiver\n(GnssFix)", fc="white", lw=0.5, fs=5.0)
        agt_c_pt = {
            0: (agt_x0, r0y + ih / 2),
            1: (agt_x0, row_y(1) + ih / 2),   # upper part of the tall ES-EKF box (IMU level)
            2: (agt_x0, row_y(2) + ih / 2),   # lower part of the tall ES-EKF box (CAI level)
            3: (agt_x0, r3y + ih / 2),
        }

        # Sensor outputs crossing the boundary: horizontal, row-aligned, nothing from truth.
        arrow(ax, env_c_pt[1], agt_c_pt[1], color=C_BLUE, lw=1.2, mut=6, zorder=6)  # IMU -> ES-EKF
        arrow(ax, env_c_pt[2], agt_c_pt[2], color=C_BLUE, lw=1.2, mut=6, zorder=6)  # CAI -> ES-EKF
        arrow(ax, env_c_pt[3], agt_c_pt[3], color=C_BLUE, lw=1.2, mut=6, zorder=6)  # GNSS -> receiver

        # Internal Agent flow (short vertical arrows in the narrow gaps between stacked boxes,
        # never crossing a box): receiver -> ES-EKF (fix); ES-EKF <-> detector/trust engine.
        fix_x = agt_x0 + agt_w * 0.5
        receiver_top = r3y + ih - 0.6
        tall_bottom = r12y + 0.6
        arrow(ax, (fix_x, receiver_top), (fix_x, tall_bottom), color=C_PURPLE, lw=1.0, mut=4.5, zorder=6)
        ax.text(fix_x + 0.5, (receiver_top + tall_bottom) / 2, "fix", fontsize=4.0, color=C_PURPLE, va="center")

        tall_top = r12y + 2 * ih - 0.6
        row0_bottom = r0y + 0.6
        innov_x = agt_x0 + agt_w * 0.28
        trustw_x = agt_x0 + agt_w * 0.72
        arrow(ax, (innov_x, tall_top), (innov_x, row0_bottom), color=C_PURPLE, lw=1.0, mut=4.5, zorder=6)
        arrow(ax, (trustw_x, row0_bottom), (trustw_x, tall_top), color=C_PURPLE, lw=1.0, mut=4.5, zorder=6)
        ax.text(innov_x - 0.3, (tall_top + row0_bottom) / 2, "innov.", fontsize=3.6, color=C_PURPLE,
                ha="right", va="center", rotation=90)
        ax.text(trustw_x + 0.3, (tall_top + row0_bottom) / 2, "trust w", fontsize=3.6, color=C_PURPLE,
                ha="left", va="center", rotation=90)

        ax.text(cx, y0 - 2.7, "only sensor outputs cross\n(AttackLabel, TruthState, meta never do)",
                ha="center", va="top", fontsize=4.9, color=C_VERM, style="italic")

        row0_top = r0y + ih - 0.6  # top edge of the row-0 (detector+trust/FL client) box
        return agt_x0, agt_x1, row0_top

    n1 = draw_node(17, "Node 1")
    n2 = draw_node(50, "Node i")
    n3 = draw_node(83, "Node N")

    # FL client <-> server: short, purely vertical arrows from the TOP edge of the row-0
    # (detector+trust/FL client) box straight up to the server — side by side, offset well
    # clear of the centred "Agent" label, and crossing no other box.
    for agt_x0, agt_x1, row0_top in [n1, n2, n3]:
        agt_w_local = agt_x1 - agt_x0
        up_x = agt_x0 + agt_w_local * 0.15
        dn_x = agt_x0 + agt_w_local * 0.85
        arrow(ax, (up_x, row0_top), (up_x, sy), color=C_GREEN, lw=1.1, mut=6, zorder=6)
        arrow(ax, (dn_x, sy), (dn_x, row0_top), color=C_ORANGE, lw=1.0, mut=6, ls=(0, (4, 2)), zorder=6)

    # legend
    leg_handles = [
        Line2D([0], [0], color=C_BLUE, lw=1.2, label="sensor output (Env→Agent, within node)"),
        Line2D([0], [0], color=C_GREEN, lw=1.2, label="uplink: ModelUpdate Δθ (detector deltas only)"),
        Line2D([0], [0], color=C_ORANGE, lw=1.2, ls=(0, (4, 2)), label="downlink: GlobalModel"),
        Line2D([0], [0], color=C_BLACK, lw=1.3, label="node boundary (explicit)"),
    ]
    ax.legend(handles=leg_handles, loc="upper center", bbox_to_anchor=(0.5, 0.02), ncol=2,
              frameon=False, fontsize=5.6, handlelength=2.2)

    fig.tight_layout(pad=0.15)
    save(fig, "fig_architecture")


# ============================================================ FIGURE 2 =====
# fig_closed_loop: per-tick closed loop with rates.
def fig_closed_loop():
    fig, ax = plt.subplots(figsize=(IN_2COL, 2.9))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 40)
    ax.axis("off")

    steps = [
        ("(a) propagate\nekf.propagate(t, imu)", C_SKY, "IMU 100 Hz"),
        ("(d) innovations\nν, S, NIS (nominal R)", C_SKY, "GNSS 1 Hz /\nCAI ≈0.65 Hz"),
        ("(f)(g) detector +\ntrust update\np_j → w_s", C_ORANGE, None),
        ("(h) correct\nekf.correct(R_eff(w))", C_SKY, None),
        ("NavSolution\nnav_k", C_GREEN, "logged 10 Hz"),
    ]
    n = len(steps)
    bw, bh = 16, 10
    y = 20
    xs = [6 + i * (100 - 12 - bw) / (n - 1) for i in range(n)]
    for (txt, fc, rate), x in zip(steps, xs):
        box(ax, (x, y), bw, bh, txt, fc=fc, fs=6.0)
        if rate:
            ax.text(x + bw / 2, y + bh + 1.5, rate, ha="center", va="bottom", fontsize=5.6,
                     color=C_VERM, style="italic")
    for i in range(n - 1):
        x0 = xs[i] + bw
        x1 = xs[i + 1]
        arrow(ax, (x0, y + bh / 2), (x1, y + bh / 2), color=C_BLACK, lw=1.1)

    # feedback arrow: NavSolution -> propagate (next tick), under the row
    fx0 = xs[-1] + bw / 2
    fx1 = xs[0] + bw / 2
    arrow(ax, (fx0, y - 1.5), (fx0, y - 7), color=C_PURPLE, lw=1.0,
          connstyle=None)
    arrow(ax, (fx0, y - 7), (fx1, y - 7), color=C_PURPLE, lw=1.0)
    arrow(ax, (fx1, y - 7), (fx1, y - 1.5), color=C_PURPLE, lw=1.0)
    ax.text((fx0 + fx1) / 2, y - 9.3,
            "feedback: nav_k carries trust-weighted correction into tick k+1's INS prior\n"
            "(innovations at k depend on trust at k−1 through the navigation state)",
            ha="center", va="top", fontsize=5.6, color=C_PURPLE)

    # E-step markers above steps a and d (Environment vs Agent emphasis)
    ax.text(xs[0] + bw / 2, y + bh + 5.2, "tick k = k·dt  (dt = 0.01 s)", ha="center", va="bottom",
            fontsize=6.4, weight="bold")

    fig.tight_layout(pad=0.15)
    save(fig, "fig_closed_loop")


# ============================================================ FIGURE 3 =====
# fig_trust_state_machine: TRUST / DISTRUST / PROBE (trust law v2).
def fig_trust_state_machine():
    fig, ax = plt.subplots(figsize=(IN_1COL, 5.0))
    ax.set_xlim(0, 48)
    ax.set_ylim(0, 60)
    ax.axis("off")

    r = 5.4
    centers = {
        "TRUST": (10, 46),
        "DISTRUST": (34, 46),
        "PROBE": (22, 22),
    }
    colors = {"TRUST": C_GREEN, "DISTRUST": C_VERM, "PROBE": C_ORANGE}
    for name, (cx, cy) in centers.items():
        circ = plt.Circle((cx, cy), r, fc=colors[name], ec=C_BLACK, lw=1.1, alpha=0.30, zorder=3)
        ax.add_patch(circ)
        ax.text(cx, cy + 1.1, name, ha="center", va="center", fontsize=8.0, weight="bold", zorder=4)

    # PROBE self-label placed below the state name, inside the circle
    ax.text(22, 22 - 1.6, "$w_{gnss}=w_{probe}=0.3$", ha="center", va="center", fontsize=5.2,
             style="italic", zorder=5)

    # TRUST -> DISTRUST : hysteresis on calibrated p̄ (§3.3 (3))
    arrow(ax, (10 + r, 48.5), (34 - r, 48.5), color=C_BLACK, lw=1.0,
          connstyle="arc3,rad=-0.15")
    ax.text(22, 54.0, "D: p̄ ≥ θ_on for T_on\n(hysteresis, calibrated p̄)", ha="center", fontsize=5.6)

    # DISTRUST -> PROBE : T_ex = 60 s continuously in DISTRUST (solid, bulges right)
    arrow(ax, (34 - 0.3, 46 - r + 0.3), (22 + r + 0.3, 22 + 2.6), color=C_BLACK, lw=1.0,
          connstyle="arc3,rad=-0.45")
    ax.text(46, 37, "$T_{ex}$ = 60 s\ncontinuously\nin DISTRUST", ha="right", va="center", fontsize=5.4)

    # PROBE -> DISTRUST : otherwise, for another T_ex (dashed, closer to the circles)
    arrow(ax, (22 + r - 0.2, 22 + 2.2), (34 - 2.8, 46 - r - 0.2), color=C_GREY, lw=1.0, ls=(0, (3, 1.5)),
          connstyle="arc3,rad=0.20")
    ax.text(46, 27, "otherwise\n→ DISTRUST\nfor another $T_{ex}$", ha="right", va="center", fontsize=5.0, color=C_GREY)

    # PROBE -> TRUST : mean NIS in bound AND E_s empty (left leg)
    arrow(ax, (22 - r + 0.3, 22 + 2.6), (10 + 0.3, 46 - r + 0.3), color=C_BLACK, lw=1.0,
          connstyle="arc3,rad=-0.15")
    ax.text(2, 34,
            "mean NIS ≤\n$\\chi^2_{dof}(0.95)$\nAND $E_s$ empty\n→ recovery ramp;\nsuppress $T_{sup}$=120 s",
            ha="left", va="center", fontsize=5.0)

    # side note box: jamming does not block recovery
    box(ax, (2, 1), 44, 7.5,
        "Jamming evidence (AGC drop, C/N0 loss, lock loss) does NOT block recovery —\n"
        "only physical spoof evidence $E_s$ does (clock/drift jump >5σ, x-sat C/N0 corr.,\n"
        "meaconing C/N0 bump ≥3 dB, abrupt position-innovation gate excursion).",
        fc="#F5F5F5", ec=C_GREY, lw=0.6, fs=5.4)

    ax.text(24, 58.5, "Trust law v2 (D-051): evidence-bounded exclusion", ha="center", fontsize=7.0, weight="bold")

    fig.tight_layout(pad=0.15)
    save(fig, "fig_trust_state_machine")


# ============================================================ FIGURE 4 =====
# fig_fl_protocol: FL round timeline (bulk-synchronous, sim time).
def fig_fl_protocol():
    fig, ax = plt.subplots(figsize=(IN_2COL, 4.1))
    ax.set_xlim(0, 112)
    ax.set_ylim(0, 50)
    ax.axis("off")

    rows_y = {"Server": 40, "Node i (veteran)": 23, "Node j (cold-start, t_join)": 7}
    for label, y in rows_y.items():
        ax.text(-1, y, label, ha="right", va="center", fontsize=6.3, weight="bold")
        ax.plot([2, 98], [y, y], color=C_GREY, lw=0.6, zorder=1)

    t_r0, t_r1 = 24, 78  # round boundary x-positions (t_r, t_{r+1})
    for tr, lab in [(t_r0, "t_r"), (t_r1, "t_{r+1}")]:
        ax.plot([tr, tr], [3, 45.5], color=C_BLACK, lw=0.7, ls=(0, (2, 2)), zorder=1)
        ax.text(tr, 47.0, f"round boundary, $T_{{round}}$=60 s\n({lab} = r·T_round)", ha="center", fontsize=5.4)

    ys = rows_y["Node i (veteran)"]
    ysj = rows_y["Node j (cold-start, t_join)"]
    ysv = rows_y["Server"]
    bh = 4.6

    # veteran node: local train E=2 epochs, send ModelUpdate with uplink delay/loss
    box(ax, (t_r0, ys + 1.6), 13, bh, "local train\nE=2 epochs\n(SGD, FedProx)", fc=C_SKY, fs=5.2)
    arrow(ax, (t_r0 + 13, ys + 3.9), (t_r0 + 22, ysv - 1.6), color=C_GREEN, lw=1.1,
          connstyle="arc3,rad=-0.2")

    # server: aggregate in node-id order, quorum, staleness weighting
    box(ax, (t_r0 + 22, ysv - 2.3), 22, 5.8,
        "aggregate (node-id order)\nTRIM-NB-R: clip→exclude→trim mean\n→reputation→quarantine\n"
        "staleness weight $(1+s)^{-0.5}$; quorum $\\geq\\lceil0.5N_{live}\\rceil$",
        fc=C_YELLOW, fs=4.6)

    # server -> node i downlink
    swap_x = 58
    arrow(ax, (t_r0 + 44, ysv - 1.6), (swap_x + 5, ys + 3.9), color=C_ORANGE, lw=1.1,
          ls=(0, (4, 2)), connstyle="arc3,rad=-0.2")
    box(ax, (swap_x, ys + 1.6), 14, bh, "swap detector at next\nGNSS epoch $\\geq t_r+d_{up}+d_{down}$",
        fc=C_SKY, fs=4.6)

    # round r+1 repeat marker, clear of the swap-detector box (starts at t_r1)
    box(ax, (t_r1, ys + 1.6), 13, bh, "round r+1:\nlocal train …", fc=C_SKY, fs=5.0, ec=C_GREY)

    # cold-start node j: dormant then joins
    box(ax, (2, ysj + 1.6), t_r0 - 5, bh, "dormant (pre $t_{join}$): does not simulate or send", fc="#EEEEEE",
        ec=C_GREY, fs=5.0)
    ax.plot([t_r0 - 2.5, t_r0 - 2.5], [ysj - 0.5, ysj + 7.5], color=C_PURPLE, lw=1.0, ls=(0, (1, 1)))
    ax.text(t_r0 - 2.5, ysj + 8.0, "$t_{join}$", ha="center", fontsize=5.4, color=C_PURPLE)
    box(ax, (t_r0, ysj + 1.6), 17, bh, "requests latest GlobalModel;\n$\\theta_0$ + probation clip $c{=}1\\times$median",
        fc=C_PURPLE, fs=4.6)
    arrow(ax, (t_r0 + 17, ysj + 3.9), (t_r0 + 24, ysv - 2.3), color=C_ORANGE, lw=1.0, ls=(0, (4, 2)),
          connstyle="arc3,rad=0.25")

    # small legend key in the empty right margin (clear of all boxes and titles)
    ax.plot([95, 99], [33, 33], color=C_GREEN, lw=1.2)
    ax.text(100, 33, "uplink: ModelUpdate\n(LogNormal delay,\nG-E loss, §4.6)", fontsize=4.8, va="center")
    ax.plot([95, 99], [22, 22], color=C_ORANGE, lw=1.2, ls=(0, (4, 2)))
    ax.text(100, 22, "downlink:\nGlobalModel", fontsize=4.8, va="center")

    ax.text(45, 1.0,
            "bulk-synchronous in sim time: node blocks at $t_r$ until GlobalModel (or Lost) arrives; "
            "wall-clock speed never changes results (§8)",
            ha="center", fontsize=5.4, style="italic")

    fig.tight_layout(pad=0.15)
    save(fig, "fig_fl_protocol")


if __name__ == "__main__":
    fig_architecture()
    fig_closed_loop()
    fig_trust_state_machine()
    fig_fl_protocol()
    print("done.")
