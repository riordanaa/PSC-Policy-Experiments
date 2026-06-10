import numpy as np


class Network(object):
    def __init__(self, numAgent):
        self.num_agent = numAgent
        self.connectivity = np.full((numAgent, numAgent), -1, dtype=np.int64)
        self.payloads = []

    def to_json(self):
        s = '{'
        s += '\n\t"num_agents":' + str(self.num_agent) + ','

        s += '\n\t"connectivity_matrix": ['
        first = True
        for x in np.nditer(self.connectivity):
            if not first:
                s += ','
            first = False
            s += str(x)
        s += '],'

        s += '\n\t"payload":['
        first = True
        for p in self.payloads:
            if not first:
                s += ','
            first = False
            s += '\n\t\t' + p.to_json()
        s += ']\n'

        s += '}'
        return s

    def __getstate__(self):
        # Copy the object's state from self.__dict__ which contains
        # all our instance attributes. Always use the dict.copy()
        # method to avoid modifying the original state.
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state):
        # Restore instance attributes (i.e., filename and lineno).
        self.__dict__.update(state)


class NetworkPayload(object):
    def __init__(self):
        self.src = None
        self.dst = None
        self.sendTime = 0
        self.leadTime = 0

    def __getstate__(self):
        # Copy the object's state from self.__dict__ which contains
        # all our instance attributes. Always use the dict.copy()
        # method to avoid modifying the original state.
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state):
        # Restore instance attributes (i.e., filename and lineno).
        self.__dict__.update(state)


class InTransit(NetworkPayload):
    def __init__(self, item):
        super(InTransit, self).__init__()
        self.item = item

    def to_json(self):
        src_id = self.src if isinstance(self.src, str) else str(self.src.id)
        dst_id = self.dst if isinstance(self.dst, str) else str(self.dst.id)
        s = '{'
        s += '"src":"' + src_id + '",'
        s += '"dst":"' + dst_id + '",'
        s += '"leadTime":' + str(self.leadTime)
        s += '}'
        return s


class OrderMessage(NetworkPayload):
    def __init__(self, order):
        super(OrderMessage, self).__init__()
        self.order = order

    def to_json(self):
        src_id = self.src if isinstance(self.src, str) else str(self.src.id)
        dst_id = self.dst if isinstance(self.dst, str) else str(self.dst.id)
        s = '{'
        s += '"src":"' + src_id + '",'
        s += '"dst":"' + dst_id + '",'
        s += '"leadTime":' + str(self.leadTime)
        s += '}'
        return s

