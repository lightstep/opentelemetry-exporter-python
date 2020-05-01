import random

_GUID_RNG = random.Random()


def _generate_guid():
    """Construct a guid - a random 64 bit integer"""
    guid = _GUID_RNG.getrandbits(64) - 1
    return 0 if guid < 0 else guid
