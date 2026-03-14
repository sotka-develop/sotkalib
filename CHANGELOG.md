# Changelog

## v0.2.4.post2

- More fixes to typing, accidentally broken something in post1

## v0.2.4.post1

- Fix typing error with relationship loads in repository

## v0.2.4

- Add support for `ABC` inference
- Add more appropriate method `.impl_by(Any)` to `iface.CheckableProtocol`
- Fix invalid `sqla.BasicDBM.merge` logic, add more tests for `sqla.BasicDBM`
- Minor patches

## v0.2.3

- Add `valid(type | object)` method to `CheckableProtocol` with type narrowing.

## v0.2.2

- Add `infer: bool = False` parameter to `iface.implements()`, deprecated `early` parameter. Now with `infer` (or
  `early`) set to True, function returns not only if the type is valid for the interface, but also hints static type
  checkers that it is implemented.
- Widen `cls` type bound in `iface.implements()` from `type` to `type | object`, now runtime-set methods / attributes
  will be correctly validated.
- Add `type.is_unset() -> TypeIs[UnsetT]` function.
- Widen type bound for `http.ArgumentFunc` from `async_function[...]` to `any_function[...]` (
  `async_function | sync_function`)

## v0.2.1

- Add `func.importutil` module for comfortable work with low-level importing
- Add `ormsgpack` optional dependency, `impl.ormsgpack.OrmsgpackSerializer` with ability to modify option parameter
  passed.
- Add ability to modify enc/dec hooks for `msgspec` serializers.

## v0.2.0.post1

- Fix autoloading of optional packages on `sotkalib` import
- Made generic mixin for `TypedSerializer` publicly availible under `sotkalib.serializer.impl.mixin`

## v0.2.0

- **Breaking:** `redis` and `sqlalchemy` moved to optional dependencies (`redis`, `sqla`)
- **Breaking:** `serializer` extracted to top-level package (`sotkalib.serializer`)
- **Breaking:** `type` internals moved to `type.iface` subpackage; public API unchanged
- Add `serializer` package with typed/untyped msgspec JSON and msgpack serializers
- Add `TypedSerializer` protocol and `__class_getitem__`-based typed serializer mixin
- Add `StdJSONSerializer` (stdlib json), `ORJSONSerializer`, `PydanticSerializer[T]` and (`msgspec`-derived as an
  optional dependency)
- Add `type.generics` module with reusable type aliases (`coro`, `method`, `async_method`, etc.)
- Add `type.iface.compatible()` for runtime type compatibility checks (including unions)
- Add `CheckableProtocol` with `%` operator for concise protocol checks
- Refactor `sqla.Database` -- simplified `_raise_on_uninitialized`, switched `DatabaseSettings` to dataclass
- Refactor `redis.locker`, `redis.lru`, `redis.pool` into subpackages
- Fix `functools.wraps` argument order in `sqla.db._raise_on_uninitialized`

## v0.1.6

- Maintenance release

## v0.1.5rc1

- Pre-release for v0.1.6

## v0.1.4

- Add Apache 2.0 license
- Fix database config schema

## v0.1.3

- Improved database session handling with safe wrappers
- Add graceful closing option for sessions
- Reimplemented `DistributedLock` in LRU-style (builder pattern)
- Fix `StrEnum` parent missing from `ValuesMixin`
- Fix recursion in `safe_serialize_value`

## v0.1.2

- Add `dict` utilities (`mod_dict`, filters)
- Add `func.defer` family (deferred awaiting context managers)
- Add `json.safe_serialize` for recursive JSON serialization
- Fix dict annotations

## v0.1.1

- Add `RedisLRU` async function cache
- Add `PydanticJSON` SQLAlchemy column type

## v0.1.0

- Add `HTTPSession` with retry, middleware pipeline, and settings merging
- Add exception handlers with stack variable capture
- Add loguru logger factory

## v0.0.6

- Add `config.AppSettings` environment-based configuration
- Add `enum` mixins (`ValidatorMixin`, `UppercaseMixin`, `ValuesMixin`)
- Add `time` UTC helpers
- Add `type.Unset` sentinel
- Add `type.implements` runtime protocol checking
