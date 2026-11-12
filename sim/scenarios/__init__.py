"""Scenarios run by default."""

from scenarios.circular_orbit import make_scenario as make_circular_orbit
from scenarios.tennis_racket import make_scenario as make_tennis_racket

SCENARIOS = (make_circular_orbit, make_tennis_racket)
