from typing import TYPE_CHECKING, final, override

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import ColumnProperty, DeclarativeBase
from sqlalchemy.orm.attributes import flag_modified

if TYPE_CHECKING:
	from typing import Any  # noqa
	from sqlalchemy import Dialect  # noqa
	from sqlalchemy.sql.type_api import TypeEngine  # noqa


@final
class PydanticJSON(sa.types.TypeDecorator["BaseModel"]):
	impl = sa.types.JSON

	def __init__(self, pydantic_type: type["BaseModel"], postgres_explicit_json: bool = False) -> None:
		super().__init__()
		if not issubclass(pydantic_type, BaseModel):
			raise TypeError(f"{pydantic_type.__name__} is not a subclass of `pydantic.BaseModel`")
		self.pydantic_type = pydantic_type
		self.postgres_explicit_json = postgres_explicit_json

	@override
	def load_dialect_impl(self, dialect: "Dialect") -> "TypeEngine[JSONB | sa.JSON]":
		if dialect.name == "postgresql" and not self.postgres_explicit_json:
			return dialect.type_descriptor(JSONB())
		else:
			return dialect.type_descriptor(sa.JSON())

	@override
	def process_bind_param(
		self,
		value: "BaseModel | None",
		dialect: "Dialect",
	) -> "dict[str, Any] | None":
		if value is None:
			return None

		if not isinstance(value, BaseModel):
			raise TypeError(f"{value.__class__.__name__} is not an instance of `pydantic.BaseModel`")

		return value.model_dump(mode="json")

	@override
	def process_result_value(
		self,
		value: "dict[str, Any] | None",
		dialect: "Dialect",
	) -> "BaseModel | None":
		return self.pydantic_type(**value) if value else None

	@override
	@property
	def python_type(self) -> type[BaseModel]:
		return self.pydantic_type


def flag_pydantic_changes[T: DeclarativeBase](target: T) -> None:
	"""
	This function is used to flag changes to `PydanticJSON` in SQLAlchemy models.

	You should add an event listener to the `before_update` event of your SQLAlchemy model
	containing a pydantic model as a column.

	See SQLAlchemy's 'event_toplevel' ref for more information.

	Example:

		>>>	event.listen(model, "before_update", flag_pydantic_changes)

		or

		>>> @event.listens_for(model, "before_update")
		>>> def _(target):
		...     flag_pydantic_changes(target)
	"""

	inspector = sa.inspect(target)
	mapper = inspector.mapper

	for attr in inspector.attrs:
		key = attr.key
		prop = mapper.attrs.get(key)

		if not isinstance(prop, ColumnProperty):
			continue

		is_pyd_type = any(isinstance(col.type, PydanticJSON) for col in prop.columns)

		if is_pyd_type:
			hist = attr.history
			original_dict = hist.unchanged[0] if hist.unchanged else None
			current_dict = attr.value.model_dump() if issubclass(attr.value.__class__, BaseModel) else attr.value

			if original_dict != current_dict:
				flag_modified(target, key)
