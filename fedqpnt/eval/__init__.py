"""Evaluator (WP-8.1/§6). Reads recorded run data (truth + labels + nav +
trust streams); computes metrics offline, after the mission. Never imported
by ``fedqpnt.node`` or any Agent-side package -- this IS the "evaluator"
half of the section 4.4 leakage guard (oracle labels / truth are read only
here)."""
