""" Test script for the HandlerChain.

From here we can see the output exception after HandlerChain handled.
"""
from exceptiongroup import HandlerChain

chain = HandlerChain()


def raise_error_with_context():
    try:
        raise RuntimeError("This is a runtime error")
    except Exception:
        try:
            raise ValueError("This is a value error")
        except Exception:
            raise ZeroDivisionError("Fake zero division error")


with chain:

    @chain.handle(ZeroDivisionError)
    def handler(exc):
        raise

    raise_error_with_context()
