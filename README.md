# sotkalib

Async-first utility library for Python 3.13+. Reusable building blocks for web applications with database, caching, and HTTP support.

Most base classes (`RedisLRU`, `DistributedLock`, `HTTPSession`, `Database`, etc.) are designed to be declared once as a constant and then shallow-copied with per-use overrides via builder methods. This lets you define a baseline configuration in one place and derive specialized variants without mutating the original.

## Install

```sh
pip install sotkalib
```

## Modules

---

### `config` -- Environment-based configuration

Type-safe settings read from environment variables (with `.env` support). Only immutable primitives are allowed (`int`, `float`, `complex`, `str`, `bool`, `None`). Attribute names must be `UPPER_SNAKE_CASE` by default.

```python
import secrets
from sotkalib.config import AppSettings, SettingsField

class Config(AppSettings):
    BOT_TOKEN: str = SettingsField(nullable=False)
    POSTGRES_USER: str = SettingsField(default="pg_user")
    POSTGRES_PASSWORD: str = SettingsField(factory=lambda: secrets.token_urlsafe(8))
    SECRET: str = SettingsField(factory="computed_secret")  # resolved from a @property

    @property
    def computed_secret(self) -> str:
        return "derived-from-other-fields"

settings = Config()                                    # loads from env / .env
settings = Config(dotenv_path=".env.prod", strict=True)  # strict rejects mutable types
```

`SettingsField` options:
- `default` -- static fallback value
- `factory` -- callable, or a `str` referencing a `@property` on the class (resolved after all other fields)
- `nullable` -- if `True`, missing env vars become `None` instead of raising

---

### `sqla` -- SQLAlchemy database management

#### `Database`

Manages sync and async SQLAlchemy engines and session factories. Sessions come in two flavors: `unsafe` (raw sessionmaker context manager) and `safe` (auto-commit on success, rollback on exception, close on exit). The `explicit_safe` setting (default `True`) makes `.session` / `.asession` return safe wrappers.

```python
from sotkalib.sqla import Database, DatabaseSettings, BasicDBM

db = Database(DatabaseSettings(
    uri="postgresql://user:pass@localhost:5432/mydb",
    async_driver="psycopg",   # set to None to disable async
    pool_size=10,
    echo=False,
    expire_on_commit=False,
    implicit_safe=True,        # .asession returns safe wrapper
))

# async usage -- auto-commits, rolls back on exception
async with db as d:
    async with d.asession as session:
        session.add(row)

# sync usage
with db as d:
    with d.session as session:
        session.add(row)

# explicit unsafe if needed
async with db.asession_unsafe as session:
    ...

# create tables from declarative base
db = Database(DatabaseSettings(uri=..., decl_base=BasicDBM))
db.create()
```

#### `BasicDBM`

Declarative base with `.dict()` for converting ORM models to plain dicts, optionally filtered through a Pydantic model's fields.

```python
from sotkalib.sqla import BasicDBM

class User(BasicDBM):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)

user.dict()                                       # all columns
user.dict(pydantic_model=UserSchema)              # only fields in UserSchema
user.dict(explicitly_include=["id", "name"])      # only specified fields
user.dict(name="not_that_model_has")              # inject/override keys

user.is_loaded(attr="email")                      # check if attr is loaded (useful with lazy relationships)
```

#### `PydanticJSON`

Column type that stores Pydantic models as JSON (JSONB on PostgreSQL).

```python
from sotkalib.sqla import PydanticJSON

class Profile(BaseModel):
    bio: str
    links: list[str]

class User(BasicDBM):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    profile = Column(PydanticJSON(Profile))  # stored as JSONB in postgres, JSON elsewhere
```

Use `flag_pydantic_changes` to detect mutations during updates:

```python
from sqlalchemy import event
from sotkalib.sqla import flag_pydantic_changes

event.listen(User, "before_update", flag_pydantic_changes)
```

---

### `redis` -- Distributed caching and locking

All Redis utilities take an `AbstractAsyncContextManager[Redis]` as their first argument -- typically a `RedisPool` instance,
but you can use any AsyncContextManager that yields a `Redis` client (standard `redis.asyncio.Redis` is supported). 
Base instances are immutable; builder methods return shallow copies so you can derive variants from one constant.

#### `RedisPool`

Connection pool wrapper. Implements `AbstractAsyncContextManager[Redis]` -- use as a context manager to get a `Redis` client.

```python
from sotkalib.redis import RedisPool, RedisPoolSettings

pool = RedisPool(RedisPoolSettings(
    uri="redis://localhost:6379",
    db_num=4,
    max_connections=50,
    health_check_interval=30,
))

async with pool as rc:
    await rc.set("key", "value")
```

#### `RedisLRU`

Async function cache backed by Redis. 
Define a base instance, then derive variants with different TTLs, versions, serializers, or key functions.

```python
from sotkalib.redis import RedisLRU, LRUSettings

# base instance -- define once, import everywhere
cache = RedisLRU(pool, LRUSettings(ttl=600, version=1))

# derive variants (returns a copy, original is untouched)
short_cache = cache.ttl(60)
v2_cache = cache.version(2)
custom_cache = cache.ttl(300).version(3).serializer(MySerializer)

@cache
async def get_user(user_id: int) -> User: ...

@short_cache
async def get_session(token: str) -> Session: ...
```

Builder methods: `.ttl()`, `.version()`, `.serializer()`, `.keyfunc()`

The default serializer is `B64Pickle` (base64-encoded pickle). A `SecurityWarning` is emitted unless you set `LRU_CACHE_ALLOW_PICKLE=yes` or provide a different serializer.

Custom serializers implement the `Serializer` protocol:

```python
class Serializer(Protocol):
    @staticmethod
    def marshal(data: Any) -> bytes: ...
    @staticmethod
    def unmarshal(raw_data: bytes) -> Any: ...
```

#### `DistributedLock`

Redis-based distributed lock with three acquisition phases: spin (tight loop, no delay), single attempt, and wait (with backoff). Define a base, derive per-use variants.

```python
from sotkalib.redis import DistributedLock, DLSettings

# base instance
dlock = DistributedLock(pool, DLSettings())

# derive variants
wait_lock = dlock.wait(timeout=30.0, backoff=exponential_delay(0.1, 2))
nowait_lock = dlock.no_wait().if_taken(retry=False)
spin_lock = dlock.spin(attempts=100).no_wait()

# use
async with wait_lock.acquire("resource:123", ttl=10):
    ...  # lock held

# shorthand
async with dlock.acq("resource:123", timeout=5):
    ...
```

Builder methods: `.wait()`, `.no_wait()`, `.spin()`, `.if_taken()`, `.exc()`

Backoff helpers:

```python
from sotkalib.redis import plain_delay, additive_delay, exponential_delay

plain_delay(0.5)               # constant 0.5s
additive_delay(0.1, 0.1)      # 0.1, 0.2, 0.3, ...
exponential_delay(0.1, 2)     # 0.1, 0.2, 0.4, 0.8, ...
```

Raises `ContextLockError` on failure. The `.can_retry` attribute indicates whether the caller should retry.

---

### `http` -- HTTP client with retry and middleware

aiohttp wrapper with configurable retry logic, status code handling, exception routing, and a middleware pipeline. Like the Redis utilities, define a base `HTTPSession` and derive variants via settings or middleware.

```python
from http import HTTPStatus
from sotkalib.http import HTTPSession, ClientSettings, StatusSettings, ExceptionSettings

# base config -- define once
client = HTTPSession(ClientSettings(
    timeout=10.0,
    maximum_retries=3,
    base=1.0,              # base delay
    backoff=2.0,           # exponential backoff factor
    status_settings=StatusSettings(
        to_retry={HTTPStatus.TOO_MANY_REQUESTS, HTTPStatus.SERVICE_UNAVAILABLE},
        to_raise={HTTPStatus.FORBIDDEN},
        not_found_as_none=True,
        unspecified="retry",   # or "raise"
    ),
    exception_settings=ExceptionSettings(
        to_retry=(TimeoutError, ServerDisconnectedError),
        to_raise=(ContentTypeError,),
        unspecified="retry",
    ),
))

# tweak inline with .with_()
aggressive = ClientSettings(maximum_retries=5).with_(
    **{"status_settings.not_found_as_none": False}
)

async with client as http:
    resp = await http.get("https://api.example.com/users/1")
    data = await http.post("https://api.example.com/users", json=payload)
```

#### Middleware

Middleware wraps the request pipeline. Each middleware receives a `RequestContext` and a `next` callable. `.use()` is generic -- a middleware can change the session's return type. The base `HTTPSession` returns `aiohttp.ClientResponse | None`; a middleware that deserializes JSON can produce an `HTTPSession[dict]`, etc.

```python
async def auth_middleware(ctx: RequestContext, next):
    ctx.merge_headers({"Authorization": "Bearer ..."})
    return await next(ctx)

async def logging_middleware(ctx: RequestContext, next):
    result = await next(ctx)
    print(f"{ctx.method} {ctx.url} -> {ctx.status} in {ctx.elapsed:.2f}s")
    return result

# passthrough middleware -- return type unchanged (HTTPSession[ClientResponse | None])
client = HTTPSession().use(auth_middleware).use(logging_middleware)

# type-transforming middleware -- return type becomes HTTPSession[dict]
async def json_middleware(ctx: RequestContext, next) -> dict:
    resp = await next(ctx)
    return await resp.json() if resp else {}

json_client: HTTPSession[dict] = HTTPSession().use(auth_middleware).use(json_middleware)

async with json_client as http:
    data: dict = await http.get("https://api.example.com/users/1")
```

`RequestContext` exposes: `method`, `url`, `attempt`, `max_attempts`, `response`, `elapsed`, `attempt_elapsed`, `is_retry`, `status`, `errors`, `last_error`, `state` (arbitrary dict for middleware to share data).

---

### `exceptions` -- Structured API errors

#### `APIError`

Structured error with status code, error code, description, and context. Serializes to JSON via an `ErrorSchema` Pydantic model.

```python
from sotkalib.exceptions import APIError

raise APIError(
    status=409,
    code="CONFLICT",
    desc="Username already taken",
    ctx={"field": "username"},
)
```

#### Exception handlers

Decorators that catch exceptions, log them, and re-raise as `ArgsIncludedError` with the caller's local variables captured from the stack (useful for debugging).

```python
from sotkalib.exceptions import exception_handler, aexception_handler

@exception_handler
def sync_fn(): ...

@aexception_handler
async def async_fn(): ...
```

#### `traceback_from`

```python
from sotkalib.exceptions import traceback_from

try:
    ...
except Exception as e:
    tb_str = traceback_from(e)  # formatted traceback string
```

---

### `func` -- Functional utilities

#### Guards

```python
from sotkalib.func import or_raise, type_or_raise

user = or_raise(maybe_none, "user not found")     # raises ValueError if None
port = type_or_raise(value, int, "port must be int")  # raises TypeError
```

#### `suppress`

Context manager with two modes:

```python
from sotkalib.func import suppress

with suppress():                                        # suppresses all exceptions
    risky()

with suppress(mode="exact", excts=[KeyError, IndexError]):  # only these types (exact match, not subclasses)
    d["missing"]
```

#### Async checks

```python
from sotkalib.func import asyncfn, asyncfn_or_raise

asyncfn(my_func)            # True if coroutine function
asyncfn_or_raise(my_func)   # raises TypeError if not
```

#### Deferred awaiting

```python
from sotkalib.func import defer, defer_ok

async with defer(cleanup_coro()):      # awaited in finally (always runs)
    ...

async with defer_ok(commit_coro()):    # awaited only if no exception
    ...
```

---

### `json` -- Safe serialization

Recursively serializes Python objects to JSON bytes via `orjson`. 
Handles `datetime`, `Decimal`, `UUID`, `Enum`, `bytes`, Pydantic models, and nested structures.
Falls back to `str()` for unknown types. Depth-limited to prevent infinite recursion.

```python
from sotkalib.json import safe_serialize

raw: bytes = safe_serialize({
    "created": datetime.now(),
    "amount": Decimal("19.99"),
    "profile": pydantic_model,
})
```

---

### `log` -- Loguru logging

Cached loguru logger factory. Names are transformed for readability (`"myapp.db.session"` -> `"myapp -> db -> session"`).

```python
from sotkalib.log import get_logger

log = get_logger("myapp.service")
log.info("starting")
```

---

### `enum` -- Enum mixins

All mixins extend `StrEnum`.

- **`UppercaseMixin`** -- auto-uppercases member values
- **`ValidatorMixin`** -- `.validate(val=..., req=True/False)`, `.get(val, default)`, `.in_(*members)`, `.values()`
- **`ValuesMixin`** -- `.values_list()`, `.values_set()`, `.names_list()`, `.names_set()`

```python
from sotkalib.enum import ValidatorMixin, UppercaseMixin, ValuesMixin

class Color(ValidatorMixin, UppercaseMixin):
    RED = auto()
    GREEN = auto()

Color.validate(val="RED", req=True)   # Color.RED
Color.get("blue", default=Color.RED)  # Color.RED
Color.RED.in_(Color.RED, Color.GREEN) # True
```

---

### `time` -- UTC helpers

```python
from sotkalib.time import utcnow, now

utcnow()    # datetime.now(UTC)
now()       # datetime.now() with local tz
now(tz)     # datetime.now(tz)
```

---

### `type` -- Sentinel types

`Unset` singleton to distinguish "not provided" from `None`.

```python
from sotkalib.type import Unset, unset

def update(name: str | _UnsetType = Unset):
    if not unset(name):
        ...
```

---

### `dict` -- Dictionary utilities

Extended dict (`_dict`) with attribute access and chainable filter methods. Works with the `Unset` sentinel.

```python
from sotkalib.dict import _dict, valid, not_none

d = _dict(a=1, b=None, c=Unset)

d.a              # 1 (attribute access)
d.valid()        # _dict(a=1, b=None)  -- strips Unset values
d.not_none()     # _dict(a=1, c=Unset) -- strips None values
d.keys_()        # [a, b, c] as list
```

Standalone functions: `valid(d)`, `unset(d)`, `not_none(d)`
