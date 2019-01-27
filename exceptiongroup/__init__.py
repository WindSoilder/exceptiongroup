"""Top-level package for exceptiongroup."""

from ._version import __version__

__all__ = ["ExceptionGroup", "split", "catch", "leaf_exceptions"]


class ExceptionGroup(BaseException):
    """An exception that contains other exceptions.

    Its main use is to represent the situation when multiple child tasks all
    raise errors "in parallel".

    Args:
      message (str): A description of the overall exception.
      exceptions (list): The exceptions.
      sources (list): For each exception, a string describing where it came
        from.

    Raises:
      TypeError: if any of the passed in objects are not instances of
          :exc:`BaseException`.
      ValueError: if the exceptions and sources lists don't have the same
          length.

    """

    def __init__(self, message, exceptions, sources):
        super().__init__(message)
        self.exceptions = list(exceptions)
        for exc in self.exceptions:
            if not isinstance(exc, BaseException):
                raise TypeError(
                    "Expected an exception object, not {!r}".format(exc)
                )
        self.message = message
        self.sources = list(sources)
        if len(self.sources) != len(self.exceptions):
            raise ValueError(
                "different number of sources ({}) and exceptions ({})".format(
                    len(self.sources), len(self.exceptions)
                )
            )

    # copy.copy doesn't work for ExceptionGroup, because BaseException have
    # rewrite __reduce_ex__ method.  We need to add __copy__ method to
    # make it can be copied.
    def __copy__(self):
        new_group = self.__class__(self.message, self.exceptions, self.sources)
        new_group.__traceback__ = self.__traceback__
        new_group.__context__ = self.__context__
        new_group.__cause__ = self.__cause__
        return new_group


from . import _monkeypatch
from ._tools import split, catch, leaf_exceptions
