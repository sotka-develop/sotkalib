# Changelog

## v0.2.1

- Added `func.importutil` module for comfortable work with low-level importing
- Added `ormsgpack` optional dependency, `impl.ormsgpack.OrmsgpackSerializer` with ability to modify option parameter passed.
- Added ability to modify enc/dec hooks for `msgspec` serializers.

## v0.2.0.post1

- Fixed autoloading of optional packages on `sotkalib` import
- Made generic mixin for `TypedSerializer` publicl availible under `sotkalib.serializer.impl.mixin`

## v0.2.0

- **Breaking:** `redis` and `sqlalchemy` moved to optional dependencies (`redis`, `sqla`)
- **Breaking:** `serializer` extracted to top-level package (`sotkalib.serializer`)
- **Breaking:** `type` internals moved to `type.iface` subpackage; public API unchanged
- Added `serializer` package with typed/untyped msgspec JSON and msgpack serializers
- Added `TypedSerializer` protocol and `__class_getitem__`-based typed serializer mixin
- Added `StdJSONSerializer` (stdlib json), `ORJSONSerializer`, `PydanticSerializer[T]` and (`msgspec`-derived as an optional dependency)
- Added `type.generics` module with reusable type aliases (`coro`, `method`, `async_method`, etc.)
- Added `type.iface.compatible()` for runtime type compatibility checks (including unions)
- Added `CheckableProtocol` with `%` operator for concise protocol checks
- Refactored `sqla.Database` -- simplified `_raise_on_uninitialized`, switched `DatabaseSettings` to dataclass
- Refactored `redis.locker`, `redis.lru`, `redis.pool` into subpackages
- Fixed `functools.wraps` argument order in `sqla.db._raise_on_uninitialized`

## v0.1.6

- Maintenance release

## v0.1.5rc1

- Pre-release for v0.1.6

## v0.1.4

- Added Apache 2.0 license
- Fixed database config schema

## v0.1.3

- Improved database session handling with safe wrappers
- Added graceful closing option for sessions
- Reimplemented `DistributedLock` in LRU-style (builder pattern)
- Fixed `StrEnum` parent missing from `ValuesMixin`
- Fixed recursion in `safe_serialize_value`

## v0.1.2

- Added `dict` utilities (`mod_dict`, filters)
- Added `func.defer` family (deferred awaiting context managers)
- Added `json.safe_serialize` for recursive JSON serialization
- Fixed dict annotations

## v0.1.1

- Added `RedisLRU` async function cache
- Added `PydanticJSON` SQLAlchemy column type

## v0.1.0

- Added `HTTPSession` with retry, middleware pipeline, and settings merging
- Added exception handlers with stack variable capture
- Added loguru logger factory

## v0.0.6

- Added `config.AppSettings` environment-based configuration
- Added `enum` mixins (`ValidatorMixin`, `UppercaseMixin`, `ValuesMixin`)
- Added `time` UTC helpers
- Added `type.Unset` sentinel
- Added `type.implements` runtime protocol checking
