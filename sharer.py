from abc import ABC

class Sharer(ABC):
    """
    Abstract base class for sharing content.
    """

    @classmethod
    def trim_post(cls, post):
        raise NotImplementedError("Subclasses must implement this method.")
