################################################################
# Core primitives for working with ExceptionGroups
################################################################

import copy
from functools import wraps
from collections import OrderedDict
from . import ExceptionGroup


def split(exc_type, exc, *, match=None):
    """ splits the exception into one half (matched) representing all the parts of
    the exception that match the predicate, and another half (not matched)
    representing all the parts that don't match.

    Args:
        exc_type (type of exception): The exception type we use to split.
        exc (BaseException): Exception object we want to split.
        match (None or func): predicate function to restict the split process,
            if the argument is not None, only exceptions with match(exception)
            will go into matched part.

    Note that if the `exc` is type of ExceptionGroup, then the return
    value will be tuple of (ExceptionGroup or None, ExceptionGroup or None)
    """
    if not isinstance(exc, BaseException):
        raise TypeError(
            "Argument `exc` should be an instance of BaseException."
        )
    if isinstance(exc, ExceptionGroup):
        matches = []
        match_notes = []
        rests = []
        rest_notes = []
        for subexc, note in zip(exc.exceptions, exc.sources):
            matched, rest = split(exc_type, subexc, match=match)
            if matched is not None:
                matches.append(matched)
                match_notes.append(note)
            if rest is not None:
                rests.append(rest)
                rest_notes.append(note)
        if matches and not rests:
            return exc, None
        elif rests and not matches:
            return None, exc
        else:
            matched_group = copy.copy(exc)
            matched_group.exceptions = matches
            matched_group.sources = match_notes
            rest_group = copy.copy(exc)
            rest_group.exceptions = rests
            rest_group.sources = rest_notes
            return matched_group, rest_group
    else:
        if isinstance(exc, exc_type) and (match is None or match(exc)):
            return exc, None
        else:
            return None, exc


class HandlerChain:
    """ An handler manager which chains many handlers.

    Examples:
        handler = HandlerChain()

        @handler.handle(RuntimeError)
        def handler1(exc):
            pass

        @handler.handle(ValueError)
        def handler2(exc):
            pass

        with handler:
            # do anything we want to do.

    Note that when there are any error(s) inside the handler, the handler will
    always raise an instance of ExceptionGroup.  And we want to show more
    readable messageses, and exception raised by handler will not have an
    extra context.
    """

    def __init__(self):
        self.handlers = OrderedDict()

    def handle(self, exc_type, match=None):
        """ An decorator to chain decorated functions.

        Args:
            exc_type (BaseException): The exception type which need to be
                handled.
            match (None or func): match function to restict the handle
                process, if the argument is not None, only exceptions with
                match(exception) will go into handler.
        """

        def decorator(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                return fn(*args, **kwargs)

            self.handlers[exc_type] = (match, fn)
            return wrapper

        return decorator

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        # for now the __exit__ just handle for the simplest case.
        # is that the exc is not an instance of `ExceptionGroup`
        rest = exc
        re_raised = []
        for e_type, (match, handle) in self.handlers.items():
            if rest is None:
                break
            caught, rest = split(e_type, rest, match=match)
            if caught is not None:
                # when handler handle exception, it may re-raise an exception.
                # for the re-raised exception, we don't need the extra context.
                # and __traceback__, which provide more information about user
                # code, so we save the context for now.
                saved_caught_context = caught.__context__
                saved_caught_traceback = caught.__traceback__
                try:
                    handle(caught)
                except BaseException as e:
                    e.__context__ = saved_caught_context
                    e.__traceback__ = saved_caught_traceback
                    re_raised.append(e)
        if rest is not None:
            re_raised.append(rest)
        if re_raised:
            group = ExceptionGroup(
                "Errors after handled by handler(s).",
                re_raised,
                [str(exc) for exc in re_raised],
            )
            # HACK: When we catch exception, and set the __context__
            # with value None.  Then re-raise it, we can raise the exception
            # without context, which can make our exception information more
            # readable.
            try:
                raise group
            except ExceptionGroup as e:
                e.__context__ = None
                # use `raise` rather than `raise e` to make our traceback
                # more readable
                raise


class Catcher:
    def __init__(self, exc_type, handler, match):
        self._exc_type = exc_type
        self._handler = handler
        self._match = match

    def __enter__(self):
        pass

    # Cases to think about:
    #
    # except RuntimeError:
    #     pass
    #
    # -> raise 'rest' if any, it gets one extra tb entry
    #
    # except RuntimeError as exc:
    #     raise OtherError
    #
    # -> set __context__ on OtherError, raise (OtherError, rest)
    #    obviously gets one extra tb entry, unavoidable. doesn't really matter
    #    whether rest exists.
    #
    # except RuntimeError as exc:
    #     raise
    # except RuntimeError as exc:
    #     raise exc
    #
    # -> in regular Python these are different. ('raise' resets the
    # __traceback__ to whatever it was when it was caught, and leaves
    # __context__ alone; 'raise exc' treats 'exc' like a new exception and
    # triggers that processing.) We can't realistically tell the difference
    # between these two cases, so we treat them both like 'raise'.
    # Specifically, if handler re-raises then we clear all context and tb
    # changes and then let the original exception propagate.
    #
    # Weird language semantics to watch out for:
    # If __exit__ returns False, then exc is reraised, *after restoring its
    # traceback to whatever it was on entry*. I think.
    #
    # And bare 'raise' restores the traceback to whatever was in
    # sys.exc_info()[2] when the exception was caught. I think. (This is why
    # we restore caught.__traceback__ *after* the handler runs, because
    # otherwise it might reset the tb back to a mangled state.)
    def __exit__(self, etype, exc, tb):
        __traceback_hide__ = True  # for pytest
        caught, rest = split(self._exc_type, exc, match=self._match)
        if caught is None:
            return False
        # 'raise caught' might mangle some of caught's attributes, and then
        # handler() might mangle them more. So we save and restore them.
        saved_caught_context = caught.__context__
        saved_caught_traceback = caught.__traceback__
        # Arrange that inside the handler, any new exceptions will get
        # 'caught' as their __context__, and bare 'raise' will work.
        try:
            raise caught
        except type(caught):
            try:
                self._handler(caught)
            except BaseException as handler_exc:
                if handler_exc is caught:
                    return False
                if rest is None:
                    exceptiongroup_catch_exc = handler_exc
                else:
                    exceptiongroup_catch_exc = ExceptionGroup(
                        "caught {}".format(self._exc_type.__class__.__name__),
                        [handler_exc, rest],
                        ["exception raised by handler", "uncaught exceptions"],
                    )
            else:
                exceptiongroup_catch_exc = rest
            finally:
                caught.__context__ = saved_caught_context
                caught.__traceback__ = saved_caught_traceback

        # The 'raise' line here is arcane plumbling that regular end users
        # will see in the middle of tracebacks, so we try to make it readable
        # out-of-context.
        saved_context = exceptiongroup_catch_exc.__context__
        try:
            raise exceptiongroup_catch_exc
        finally:
            exceptiongroup_catch_exc.__context__ = saved_context


def catch(exc_type, handler, match=None):
    """Return a context manager that catches and re-throws exception.
        after running :meth:`handle` on them.

    Args:
        exc_type: An exception type or A tuple of exception type that need
            to be handled by ``handler``.  Exceptions which doesn't belong to
            exc_type or doesn't match the predicate will not be handled by
            ``handler``.
        handler: the handler to handle exception which match exc_type and
            predicate.
        match: when the match is not None, ``handler`` will only handle when
            match(exc) is True
    """
    return Catcher(exc_type, handler, match)
