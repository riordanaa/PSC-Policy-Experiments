import itertools


class Order(object):
    """ Order is a message sent from an downstream node to upstream node to
        buy some drug
    """

    _id_counter = itertools.count()

    def __init__(self):
        self.id = next(Order._id_counter)

        self.src = None
        self.dst = None
        self.amount = int(0)
        self.place_time = 0

        self.delivery = []

        self.recv_time = 0
        self.exp_recv_time = 0
        self.expire_time = 0

    def __getstate__(self):
        # Copy the object's state from self.__dict__ which contains
        # all our instance attributes. Always use the dict.copy()
        # method to avoid modifying the original state.
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state):
        # Restore instance attributes (i.e., filename and lineno).
        self.__dict__.update(state)
