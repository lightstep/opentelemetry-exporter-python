import random

_GUID_RNG = random.Random()


def _generate_guid():
    """Construct a guid - a random 64 bit integer"""
    return _GUID_RNG.getrandbits(64) - 1
