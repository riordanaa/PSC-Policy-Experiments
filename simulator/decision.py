""" decision provide definitions for various types of decisions """



class Decision(object):
    # pass
    def __getstate__(self):
        # Copy the object's state from self.__dict__ which contains
        # all our instance attributes. Always use the dict.copy()
        # method to avoid modifying the original state.
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state):
        # Restore instance attributes (i.e., filename and lineno).
        self.__dict__.update(state)


class ProduceDecision(Decision):
    def __init__(self):
        self.amount = int(0)


class AllocateDecision(Decision):
    def __init__(self):
        self.item = None
        self.downstream_node = None
        self.order = None
        self.amount = int(0)


class OrderDecision(Decision):
    def __init__(self):
        self.upstream = None
        self.amount = int(0)


class TreatDecision(Decision):
    def __init__(self):
        self.urgent = int(0)
        self.non_urgent = int(0)
