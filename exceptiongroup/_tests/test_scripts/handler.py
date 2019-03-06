""" Test script for the HandlerChain.

From here we can see the output exception after HandlerChain handled.
"""
from exceptiongroup import HandlerChain, ExceptionGroup

chain = HandlerChain()


def raise_error():
    raise ValueError("Another value error")


def raise_another_error():
    raise RuntimeError("Another runtime error")


def raise_group():
    try:
        raise_error()
    except Exception as e:
        val_err = e

    try:
        raise_another_error()
    except Exception as e:
        run_err = e

    raise ExceptionGroup(
        "group", [val_err, run_err], [str(val_err), str(run_err)]
    )


with chain:

    @chain.handle(ValueError)
    def handler(exc):
        raise ZeroDivisionError("zero division error.")

    raise_group()
