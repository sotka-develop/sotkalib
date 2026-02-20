from sotkalib.redis.pool import RedisPoolfrom pydantic import BaseModelfrom datetime import timezonefrom sotkalib.time import dtfunc

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
prod_settings = Config(dotenv_path=".env.prod", strict=True)  # strict rejects mutable types
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
	enable_sync_engine=False, 
    pool_size=10,
    echo=False,
    expire_on_commit=False,
    implicit_safe=True,        # .asession returns safe wrapper
))

# async usage -- auto-commits, rolls back on exception
async with db as d: # would raise with async_engine=None
    async with d.asession as session:
        session.add(row) 

# sync usage
with db as d: # would raise with enable_sync_engine=False
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
LRU = RedisLRU(pool, LRUSettings(ttl=600, version=1))

@LRU.version(2).ttl(60)
async def get_user(user_id: int) -> User: ...

@LRU.ttl(300).version(3).serializer(JSONSerializer)
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
from sotkalib.redis.locker import DistributedLock, DLSettings, exponential_delay
from sotkalib.redis.pool import RedisPool

# base instance
Locker = DistributedLock(RedisPool(), DLSettings())



async def main():
    async with (
		Locker
		.wait(timeout=30.0, backoff=exponential_delay(0.1, 2))
		.acquire("resource:123", ttl=10)
	):
        ...  # lock held
    
    # shorthand
    async with (
		Locker
		.spin(attempts=100)
		.no_wait()
		.acq("resource:123", timeout=5)
	):
        ...
```

Builder methods: `.wait()`, `.no_wait()`, `.spin()`, `.if_taken()`, `.exc()`

Backoff helpers:

```python
from sotkalib.redis.locker import plain_delay, additive_delay, exponential_delay

plain_delay(0.5)               # constant 0.5s
additive_delay(0.1, 0.1)      # 0.1, 0.2, 0.3, ...
exponential_delay(0.1, 2)     # 0.1, 0.2, 0.4, 0.8, ...
```

Raises `ContextLockError` on failure. The `.can_retry` attribute indicates whether the caller should retry.

---

### `http` -- HTTP client with retry and middleware

aiohttp wrapper with configurable retry logic, status code handling, exception routing, and a middleware pipeline. Like the Redis utilities, define a base `HTTPSession` and derive variants via settings or middleware.

```python
import asyncio
from http import HTTPStatus
from aiohttp import ServerDisconnectedError, ContentTypeError
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

# branch from base config with |
base = ClientSettings(timeout=10.0, maximum_retries=3)

async def main():
	async with (
            base 
            | ClientSettings(maximum_retries=5) 
            | StatusSettings(not_found_as_none=False)
	) as http:
		resp = await http.get("https://api.example.com/users/1")
		data = await http.post("https://api.example.com/users", json={"User": "Me"})
	
asyncio.run(main())
```

#### Middleware

Middleware wraps the request pipeline. Each middleware receives a `RequestContext` and a `next` callable. `.use()` is generic -- a middleware can change the session's return type. The base `HTTPSession` returns `aiohttp.ClientResponse | None`; a middleware that deserializes JSON can produce an `HTTPSession[dict]`, etc.

```python
import asyncio
from http import HTTPStatus
from sotkalib.http import HTTPSession, ClientSettings, StatusSettings, ExceptionSettings, RequestContext

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

async def main():
    async with json_client as http:
        data: dict = await http.get("https://api.example.com/users/1")
		
asyncio.run(main())
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

#### `type guards`

```python
from sotkalib.func import or_raise, type_or_raise

class User(object):...

def get_user() -> User | None: ...

user_res = get_user()

# raises ValueError if None, user inferred as User
user = or_raise(user_res, "user not found") 

value: float = 1.0

# raises TypeError, port inferred as int
port = type_or_raise(value, int, "port must be int")  
```

#### `suppress`

Context manager with two modes:

```python
from sotkalib.func import suppress

def risky():
	raise RuntimeError

with suppress():  # suppresses all exceptions
	risky()

d = {}
with suppress(mode="exact", exact_types=(KeyError,)):  # only these types (exact match, not subclasses)
	_ = d["missing"]
```

#### Async checks

```python
from sotkalib.func import asyncfn, asyncfn_or_raise

def my_func(): ...

asyncfn(my_func)            # True if coroutine function
asyncfn_or_raise(my_func)   # raises TypeError if not
```

#### Deferred awaiting

```python
from sotkalib.func import defer, defer_ok, defer_exc, defer_exc_mute

async def coro(): ...
async def coro2(): ...
async def coro3(): ...


# awaited in finally (always runs)
async with defer(coro(), coro2(), coro3()):     
    ...

# awaited only if no exception
async with defer_ok(coro(), coro2(), coro3()):   
    ...

# awaited only if exception raised
# -> bubbles exception up
async with defer_exc(coro(), coro2(), coro3()):  
    ...

# awaited only if exception raised
# -> silences exception
async with defer_exc_mute(coro(), coro2(), coro3()):    # awaited only if no exception
    ...
```

---

### `json` -- Safe serialization

Recursively serializes Python objects to JSON bytes via `orjson`. 
Handles `datetime`, `Decimal`, `UUID`, `Enum`, `bytes`, Pydantic models, and nested structures.
Falls back to `str()` for unknown types. Depth-limited to prevent infinite recursion.

```python
from sotkalib.json import safe_serialize
from sotkalib.time import now
from decimal import Decimal
from pydantic import BaseModel

class PM(BaseModel): 
	a: bytes = "2"
	b: int = 3

pydantic_model = PM()
	
raw: bytes = safe_serialize(
	{
		"created": now(),
		"amount":  Decimal("19.99"),
		"profile": pydantic_model,
	}
)
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

col: Color = Color.RED
Color.validate(val="RED", req=True)   # Color.RED
Color.get("blue", default=Color.RED)  # Color.RED
col.in_(Color.RED, Color.GREEN) # True
```

---

### `time` -- UTC helpers

```python
from sotkalib.time import utcnow, now
from datetime import timezone, timedelta

tz = timezone(offset=timedelta(hours=12))
utcnow() # datetime.now(UTC)
now()    # datetime.now() with local tz
now(tz)  # datetime.now(tz)
```

---

### `type` -- Sentinel types and runtime protocol checking

#### `Unset` sentinel

`Unset` singleton to distinguish "not provided" from `None`.

```python
from sotkalib.type import Unset, unset, UnsetT


def update(name: str | UnsetT = Unset):
	if not unset(name):
		...
```

#### `implements` -- Runtime protocol checking

Check if a class implements a Protocol at runtime, with optional signature and type hint validation.

```python
from typing import Protocol
from sotkalib.type import implements, DoesNotImplementError


class UserGetter(Protocol):
	def get_user(self, user_id: int) -> str: ...


class DB:
	def get_user(self, user_id: int) -> str:
		return "user"


# Check without raising
if implements(DB, UserGetter, early=True):
	print("DB implements UserGetter")

# Strict check with raising
try:
	implements(DB, UserGetter, disallow_extra=True)
except DoesNotImplementError as e:
	print(e.violations)  # list of what failed
```

Options:
- `signatures` -- compare callable signatures (default: True)
- `type_hints` -- compare type annotations (default: True)
- `disallow_extra` -- flag extra parameters not in protocol (default: False)
- `early` -- return bool instead of raising (default: False)

#### `CheckableProtocol` -- Protocol with `%` operator

A Protocol subclass that supports the `%` operator for concise runtime checks.

```python
from sotkalib.type import CheckableProtocol

class UserGetter(CheckableProtocol):
    @property
    def val(self) -> int: ...

class Impl:
    val: int

class Impl2:
    val: str  # wrong type

print(Impl % UserGetter)   # True
print(Impl2 % UserGetter) # False (val is str, not int)
```

---

### `dict` -- Dictionary utilities

Extended dict (`mod_dict`) with attribute access and chainable filter methods. Works with the `Unset` sentinel.

```python
from sotkalib.dict.util import mod_dict, valid, not_none
from sotkalib.type import Unset

d = mod_dict(a=1, b=None, c=Unset)

v = d.a  # 1 (attribute access)
d.valid()  # mod_dict(a=1, b=None)  -- strips Unset values
d.not_none()  # mod_dict(a=1, c=Unset) -- strips None values
d.keys_()  # [a, b, c] as list
```

Standalone functions: `valid(d)`, `unset(d)`, `not_none(d)`
