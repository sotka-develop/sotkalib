"""useful repetative generics"""

from collections.abc import Callable, Coroutine
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from typing import Any, Concatenate

type strlike = str | bytes | bytearray | memoryview


# functionals
type coro[typ] = Coroutine[Any, Any, typ]
type func[**pspec, rtype] = Callable[pspec, rtype]
type async_function[**pspec, rtype] = Callable[pspec, coro[rtype]]
type any_function[**pspec, rtype] = func[pspec, rtype | coro[rtype]]
# methods
type method[inst, **pspec, rtype] = func[Concatenate[inst, pspec], rtype]
type async_method[inst, **pspec, rtype] = func[Concatenate[inst, pspec], coro[rtype]]
type any_method[inst, **pspec, rtype] = method[inst, pspec, rtype | coro[rtype]]
# classmethods
type cls_meth[inst, **pspec, rtype] = method[type[inst], pspec, rtype]
type async_cls_meth[inst, **pspec, rtype] = async_method[type[inst], pspec, rtype]
type any_cls_meth[inst, **pspec, rtype] = any_method[type[inst], pspec, rtype]
# context managers
type contextmgr[typ] = AbstractContextManager[typ]
type async_contextmgr[typ] = AbstractAsyncContextManager[typ]
