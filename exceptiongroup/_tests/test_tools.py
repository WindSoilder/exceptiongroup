import pytest
from exceptiongroup import ExceptionGroup, split, HandlerChain


def raise_error(err):
    raise err


def raise_error_from_another(out_err, another_err):
    # use try..except approache so out_error have meaningful
    # __context__, __cause__ attribute.
    try:
        raise another_err
    except Exception as e:
        raise out_err from e


def test_split_for_none_exception_should_raise_value_error():
    with pytest.raises(TypeError):
        matched, unmatched = split(RuntimeError, None)


def test_split_when_all_exception_matched():
    group = ExceptionGroup(
        "Many Errors",
        [RuntimeError("Runtime Error1"), RuntimeError("Runtime Error2")],
        ["Runtime Error1", "Runtime Error2"],
    )
    matched, unmatched = split(RuntimeError, group)
    assert matched is group
    assert unmatched is None


def test_split_when_all_exception_unmatched():
    group = ExceptionGroup(
        "Many Errors",
        [RuntimeError("Runtime Error1"), RuntimeError("Runtime Error2")],
        ["Runtime Error1", "Runtime Error2"],
    )
    matched, unmatched = split(ValueError, group)
    assert matched is None
    assert unmatched is group


def test_split_when_contains_matched_and_unmatched():
    error1 = RuntimeError("Runtime Error1")
    error2 = ValueError("Value Error2")
    group = ExceptionGroup(
        "Many Errors", [error1, error2], ["Runtime Error1", "Value Error2"]
    )
    matched, unmatched = split(RuntimeError, group)
    assert isinstance(matched, ExceptionGroup)
    assert isinstance(unmatched, ExceptionGroup)
    assert matched.exceptions == [error1]
    assert matched.message == "Many Errors"
    assert matched.sources == ["Runtime Error1"]
    assert unmatched.exceptions == [error2]
    assert unmatched.message == "Many Errors"
    assert unmatched.sources == ["Value Error2"]


def test_split_with_predicate():
    def _match(err):
        return str(err) != "skip"

    error1 = RuntimeError("skip")
    error2 = RuntimeError("Runtime Error")
    group = ExceptionGroup(
        "Many Errors", [error1, error2], ["skip", "Runtime Error"]
    )
    matched, unmatched = split(RuntimeError, group, match=_match)
    assert matched.exceptions == [error2]
    assert unmatched.exceptions == [error1]


def test_split_with_single_exception():
    err = RuntimeError("Error")
    matched, unmatched = split(RuntimeError, err)
    assert matched is err
    assert unmatched is None

    matched, unmatched = split(ValueError, err)
    assert matched is None
    assert unmatched is err


def test_split_and_check_attributes_same():
    try:
        raise_error(RuntimeError("RuntimeError"))
    except Exception as e:
        run_error = e

    try:
        raise_error(ValueError("ValueError"))
    except Exception as e:
        val_error = e

    group = ExceptionGroup(
        "ErrorGroup", [run_error, val_error], ["RuntimeError", "ValueError"]
    )
    # go and check __traceback__, __cause__ attributes
    try:
        raise_error_from_another(group, RuntimeError("Cause"))
    except BaseException as e:
        new_group = e

    matched, unmatched = split(RuntimeError, group)
    assert matched.__traceback__ is new_group.__traceback__
    assert matched.__cause__ is new_group.__cause__
    assert matched.__context__ is new_group.__context__
    assert matched.__suppress_context__ is new_group.__suppress_context__
    assert unmatched.__traceback__ is new_group.__traceback__
    assert unmatched.__cause__ is new_group.__cause__
    assert unmatched.__context__ is new_group.__context__
    assert unmatched.__suppress_context__ is new_group.__suppress_context__


def test_handler_chain_when_raise_bare_exception():
    chain = HandlerChain()
    with pytest.raises(ExceptionGroup):
        with chain:
            raise ValueError("This is a value error.")

    @chain.handle(ValueError)
    def value_error_handler(exc):
        return None

    # Here we should work successfully.
    with chain:
        raise ValueError("This is a value error which should not be raised.")

    @chain.handle(ValueError)
    def value_error_handler2(exc):
        raise RuntimeError("This is a runtime error.")

    with pytest.raises(ExceptionGroup):
        with chain:
            raise ValueError("This is a value error")

    @chain.handle(ValueError)
    def value_error_handler3(exc):
        raise

    with pytest.raises(ExceptionGroup):
        with chain:
            raise ValueError("This is a value error")


def test_handler_chain_re_raised_properties():
    chain = HandlerChain()

    try:
        with chain:
            raise ValueError("This is a value error.")
    except ExceptionGroup as e:
        assert e.__context__ is None, "We should ensure that we get"
        "None context to make tb more readable"
        assert len(e.exceptions) == 1
        assert isinstance(e.exceptions[0], ValueError)

    try:
        with chain:

            @chain.handle(ValueError)
            def value_error_handler(exc):
                raise RuntimeError("This is a runtime error")

            raise ValueError("This is a value error.")
    except ExceptionGroup as e:
        assert e.__context__ is None, "We should ensure that we get"
        "None context to make tb more readable"
        assert len(e.exceptions) == 1
        assert isinstance(e.exceptions[0], RuntimeError)
        # We should also make sure that the when handler re-raised exception,
        # the exception's context is not changed by the handler.
        # TODO: How to check the __traceback__? By check the frame object ?
        assert e.exceptions[0].__context__ is None
