"""A minimal bot written against the Sid contract (sidplay/engine.py), for tests."""


class ToySid:
    def __init__(self, bundle, meta):
        self.meta = meta

    def bid(self, hand, seat, dealer, vulnerability, calls):
        return '1C' if not calls else 'PASS'

    def play(self, observation, facing, systems, rng):
        assert facing in ('human', 'sid')
        return rng.choice(observation.legal)
