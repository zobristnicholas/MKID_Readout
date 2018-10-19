import warnings
import numpy as np
from analogreadout.custom_warnings import ConnectionWarning


class NotASensor:
    def __init__(self, name=''):
        self.name = name
        self.warn()

    def initialize(self):
        pass

    @staticmethod
    def read_value():
        return np.nan

    def close(self):
        pass

    def reset(self):
        pass

    def warn(self):
        message = "{} sensor is not connected and was not initialized"
        warnings.warn(message.format(self.name), ConnectionWarning)