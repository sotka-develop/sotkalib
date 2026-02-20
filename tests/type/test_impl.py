from typing import Any, Protocol

import pytest

from sotkalib.type.iface import DoesNotImplementError, implements

# ============================================================
# exception
# ============================================================


class TestDoesNotImplementError:
	def test_stores_violations_proto_failed(self):
		violations = ["missing method foo", "wrong type"]
		proto = Protocol
		target = object

		err = DoesNotImplementError(violations, proto, target)

		assert err.violations is violations
		assert err.proto is proto
		assert err.target is target

	def test_repr_contains_class_info(self):
		err = DoesNotImplementError(["v"], Protocol, object)
		r = repr(err)

		assert "DoesNotImplementError" in r
		assert "does not implement protocol" in r
		assert "Protocol" in r

	def test_repr_contains_all_violations(self):
		viols = ["missing method foo", "wrong type bar", "third issue"]
		err = DoesNotImplementError(viols, Protocol, object)
		r = repr(err)

		for v in viols:
			assert v in r

	def test_str_equals_repr(self):
		err = DoesNotImplementError(["v"], Protocol, object)
		assert str(err) == repr(err)

	def test_is_base_exception(self):
		err = DoesNotImplementError([], Protocol, object)
		assert isinstance(err, BaseException)

	def test_single_violation(self):
		err = DoesNotImplementError(["only one"], Protocol, object)
		assert "only one" in repr(err)


# ============================================================
# shared protocols
# ============================================================


class ProtocolWithMethod(Protocol):
	def method(self, x: int) -> str: ...


class ProtocolWithAttr(Protocol):
	attr: str


# ============================================================
# basic: pass / fail
# ============================================================


class TestBasicPass:
	def test_correct_method(self):
		class Impl:
			def method(self, x: int) -> str:
				return str(x)

		implements(Impl, ProtocolWithMethod)

	def test_attr_with_default(self):
		class Impl:
			attr: str = "hello"

		implements(Impl, ProtocolWithAttr)

	def test_attr_annotation_only(self):
		class Impl:
			attr: str

		implements(Impl, ProtocolWithAttr)

	def test_empty_protocol(self):
		class Empty(Protocol): ...

		class Impl:
			pass

		implements(Impl, Empty)

	def test_extra_members_ok(self):
		class Impl:
			attr: str = "hi"
			bonus: int = 42

		implements(Impl, ProtocolWithAttr)


class TestBasicFail:
	def test_missing_method(self):
		class Impl:
			pass

		with pytest.raises(DoesNotImplementError, match="expected member `method`"):
			implements(Impl, ProtocolWithMethod)

	def test_missing_attr(self):
		class Impl:
			pass

		with pytest.raises(DoesNotImplementError, match="expected annotated attribute `attr`"):
			implements(Impl, ProtocolWithAttr)

	def test_method_is_not_callable(self):
		class Impl:
			method: str = "not a function"

		with pytest.raises(DoesNotImplementError, match="expected `method` to be callable"):
			implements(Impl, ProtocolWithMethod)

	def test_attr_is_callable(self):
		class Impl:
			def attr(self) -> str:
				return "oops"

		with pytest.raises(DoesNotImplementError, match="expected `attr` to be a data attribute"):
			implements(Impl, ProtocolWithAttr)

	def test_non_protocol_raises_typeerror(self):
		class NotProto:
			pass

		with pytest.raises(TypeError, match="expected protocol"):
			implements(NotProto, NotProto)

	def test_multiple_violations_collected(self):
		class Multi(Protocol):
			def foo(self) -> int: ...
			def bar(self) -> str: ...

			val: int

		class Impl:
			pass

		with pytest.raises(DoesNotImplementError) as exc_info:
			implements(Impl, Multi)

		assert len(exc_info.value.violations) >= 3


# ============================================================
# signatures
# ============================================================


class TestSignatures:
	def test_param_type_mismatch(self):
		class Impl:
			def method(self, x: str) -> str:
				return x

		with pytest.raises(DoesNotImplementError, match="expected annotated parameter"):
			implements(Impl, ProtocolWithMethod)

	def test_return_type_mismatch(self):
		class Impl:
			def method(self, x: int) -> int:
				return x

		with pytest.raises(DoesNotImplementError, match="return type"):
			implements(Impl, ProtocolWithMethod)

	def test_missing_param(self):
		class Proto(Protocol):
			def m(self, a: int, b: str) -> None: ...

		class Impl:
			def m(self, a: int) -> None:
				pass

		with pytest.raises(DoesNotImplementError, match="expected parameter `b`"):
			implements(Impl, Proto)

	def test_signatures_disabled(self):
		class Impl:
			def method(self, totally: float, different: bytes) -> dict:
				return {}

		implements(Impl, ProtocolWithMethod, signatures=False)

	def test_type_hints_disabled(self):
		class Impl:
			attr: int = 42

		implements(Impl, ProtocolWithAttr, type_hints=False)


# ============================================================
# strict mode
# ============================================================


class TestStrictMode:
	def test_extra_required_param_raises(self):
		class Impl:
			def method(self, x: int, extra: int) -> str:
				return str(x)

		with pytest.raises(DoesNotImplementError, match="unexpected required parameter"):
			implements(Impl, ProtocolWithMethod, disallow_extra=True)

	def test_extra_param_with_default_ok(self):
		class Impl:
			def method(self, x: int, extra: str = "default") -> str:
				return str(x)

		implements(Impl, ProtocolWithMethod, disallow_extra=True)

	def test_extra_args_ok(self):
		class Impl:
			def method(self, x: int, *args: Any) -> str:
				return str(x)

		implements(Impl, ProtocolWithMethod, disallow_extra=True)

	def test_extra_kwargs_ok(self):
		class Impl:
			def method(self, x: int, **kwargs: Any) -> str:
				return str(x)

		implements(Impl, ProtocolWithMethod, disallow_extra=True)

	def test_non_strict_ignores_extra_required(self):
		class Impl:
			def method(self, x: int, extra: int) -> str:
				return str(x)

		# non-strict — should pass
		implements(Impl, ProtocolWithMethod, disallow_extra=False)


# ============================================================
# *args / **kwargs absorption
# ============================================================


class TestVarArgs:
	def test_kwargs_absorbs_positional_or_keyword(self):
		class Proto(Protocol):
			def m(self, x: int, y: str) -> None: ...

		class Impl:
			def m(self, **kwargs: Any) -> None:
				pass

		implements(Impl, Proto)

	def test_args_absorbs_positional(self):
		class Proto(Protocol):
			def m(self, x: int, y: str) -> None: ...

		class Impl:
			def m(self, *args: Any) -> None:
				pass

		implements(Impl, Proto)

	def test_kwargs_absorbs_keyword_only(self):
		class Proto(Protocol):
			def m(self, *, key: int) -> None: ...

		class Impl:
			def m(self, **kwargs: Any) -> None:
				pass

		implements(Impl, Proto)

	def test_args_does_not_absorb_keyword_only(self):
		class Proto(Protocol):
			def m(self, *, key: int) -> None: ...

		class Impl:
			def m(self, *args: Any) -> None:
				pass

		with pytest.raises(DoesNotImplementError, match="expected keyword parameter `key`"):
			implements(Impl, Proto)


# ============================================================
# keyword-only / positional-only params
# ============================================================


class TestParamKinds:
	def test_keyword_only_match(self):
		class Proto(Protocol):
			def m(self, *, x: int) -> None: ...

		class Impl:
			def m(self, *, x: int) -> None:
				pass

		implements(Impl, Proto)

	def test_keyword_only_mismatch(self):
		class Proto(Protocol):
			def m(self, *, x: int) -> None: ...

		class Impl:
			def m(self, x: int) -> None:
				pass

		with pytest.raises(DoesNotImplementError, match="KEYWORD_ONLY"):
			implements(Impl, Proto)

	def test_positional_only_satisfies_positional_or_keyword(self):
		"""POSITIONAL_ONLY should be accepted where POSITIONAL_OR_KEYWORD is expected."""

		class Proto(Protocol):
			def m(self, x: int) -> None: ...

		class Impl:
			def m(self, x: int, /) -> None:
				pass

		implements(Impl, Proto)


# ============================================================
# union / generic type compat
# ============================================================


class TestTypeCompat:
	def test_union_compatible_broader(self):
		class Proto(Protocol):
			attr: str | int

		class Impl:
			attr: str | int | float

		implements(Impl, Proto)

	def test_union_incompatible_narrower(self):
		class Proto(Protocol):
			attr: str | int | float | bytes

		class Impl:
			attr: str | int

		with pytest.raises(DoesNotImplementError):
			implements(Impl, Proto)

	def test_union_pep604_syntax(self):
		"""str | int (PEP 604 / types.UnionType) must work."""

		class Proto(Protocol):
			attr: str | int

		class Impl:
			attr: str | int

		implements(Impl, Proto)

	def test_optional_is_union_with_none(self):

		class Proto(Protocol):
			attr: str | None

		class Impl:
			attr: str | None

		implements(Impl, Proto)

	def test_generic_list_compatible(self):
		class Proto(Protocol):
			attr: list[int]

		class Impl:
			attr: list[int]

		implements(Impl, Proto)

	def test_generic_list_incompatible(self):
		class Proto(Protocol):
			attr: list[int]

		class Impl:
			attr: list[str]

		with pytest.raises(DoesNotImplementError):
			implements(Impl, Proto)

	def test_generic_unparameterized_ok(self):
		class Proto(Protocol):
			attr: list

		class Impl:
			attr: list[int]

		implements(Impl, Proto)

	def test_generic_dict_compatible(self):
		class Proto(Protocol):
			attr: dict[str, int]

		class Impl:
			attr: dict[str, int]

		implements(Impl, Proto)

	def test_generic_dict_incompatible_value(self):
		class Proto(Protocol):
			attr: dict[str, int]

		class Impl:
			attr: dict[str, str]

		with pytest.raises(DoesNotImplementError):
			implements(Impl, Proto)

	def test_any_always_compat(self):
		class Proto(Protocol):
			attr: Any

		class Impl:
			attr: int = 42

		implements(Impl, Proto)

	def test_subclass_compat(self):
		"""int is a subclass of int — same type should match."""

		class Proto(Protocol):
			def m(self, x: int) -> None: ...

		class Impl:
			def m(self, x: int) -> None:
				pass

		implements(Impl, Proto)

	def test_subclass_compat_bool_is_int(self):
		class Proto(Protocol):
			attr: int

		class Impl:
			attr: bool = True

		implements(Impl, Proto)


# ============================================================
# properties
# ============================================================


class TestProperties:
	def test_property_vs_property_matching_types(self):
		class Proto(Protocol):
			@property
			def val(self) -> int: ...

		class Impl:
			@property
			def val(self) -> int:
				return 42

		implements(Impl, Proto)

	def test_property_vs_property_mismatched_types(self):
		class Proto(Protocol):
			@property
			def val(self) -> int: ...

		class Impl:
			@property
			def val(self) -> str:
				return "oops"

		with pytest.raises(DoesNotImplementError, match="expected property.*to be of type"):
			implements(Impl, Proto)

	def test_property_satisfied_by_annotation(self):
		class Proto(Protocol):
			@property
			def val(self) -> int: ...

		class Impl:
			val: int

		implements(Impl, Proto)

	def test_property_satisfied_by_class_attr(self):
		class Proto(Protocol):
			@property
			def val(self) -> int: ...

		class Impl:
			val: int = 10

		implements(Impl, Proto)

	def test_property_missing(self):
		class Proto(Protocol):
			@property
			def val(self) -> int: ...

		class Impl:
			pass

		with pytest.raises(DoesNotImplementError):
			implements(Impl, Proto)

	def test_property_annotation_type_mismatch(self):
		class Proto(Protocol):
			@property
			def val(self) -> int: ...

		class Impl:
			val: str

		with pytest.raises(DoesNotImplementError, match="expected property.*to be of type"):
			implements(Impl, Proto)


# ============================================================
# staticmethod / classmethod
# ============================================================


class TestDescriptorKinds:
	def test_staticmethod_match(self):
		class Proto(Protocol):
			@staticmethod
			def create() -> int: ...

		class Impl:
			@staticmethod
			def create() -> int:
				return 42

		implements(Impl, Proto)

	def test_staticmethod_mismatch(self):
		class Proto(Protocol):
			@staticmethod
			def create() -> int: ...

		class Impl:
			def create(self) -> int:
				return 42

		with pytest.raises(DoesNotImplementError, match="to be static"):
			implements(Impl, Proto)

	def test_classmethod_match(self):
		class Proto(Protocol):
			@classmethod
			def create(cls) -> int: ...

		class Impl:
			@classmethod
			def create(cls) -> int:
				return 42

		implements(Impl, Proto)

	def test_classmethod_mismatch(self):
		class Proto(Protocol):
			@classmethod
			def create(cls) -> int: ...

		class Impl:
			def create(self) -> int:
				return 42

		with pytest.raises(DoesNotImplementError, match="to be classmethod"):
			implements(Impl, Proto)

	def test_staticmethod_signature_checked(self):
		class Proto(Protocol):
			@staticmethod
			def make(x: int) -> str: ...

		class Impl:
			@staticmethod
			def make(x: str) -> str:
				return x

		with pytest.raises(DoesNotImplementError, match="expected annotated parameter"):
			implements(Impl, Proto)


# ============================================================
# dunder protocol members
# ============================================================


class TestDunderMembers:
	def test_call_protocol(self):
		class Callable(Protocol):
			def __call__(self, x: int) -> str: ...

		class Impl:
			def __call__(self, x: int) -> str:
				return str(x)

		implements(Impl, Callable)

	def test_call_protocol_wrong_signature(self):
		class Callable(Protocol):
			def __call__(self, x: int) -> str: ...

		class Impl:
			def __call__(self, x: str) -> str:
				return x

		with pytest.raises(DoesNotImplementError, match="expected annotated parameter"):
			implements(Impl, Callable)

	def test_getitem_protocol(self):
		class Indexable(Protocol):
			def __getitem__(self, key: str) -> int: ...

		class Impl:
			def __getitem__(self, key: str) -> int:
				return 0

		implements(Impl, Indexable)

	def test_len_protocol(self):
		class Sized(Protocol):
			def __len__(self) -> int: ...

		class Impl:
			def __len__(self) -> int:
				return 0

		implements(Impl, Sized)

	def test_iter_protocol(self):
		class Iterable(Protocol):
			def __iter__(self): ...

		class Impl:
			def __iter__(self):
				return iter([])

		implements(Impl, Iterable)

	def test_contains_protocol(self):
		class Container(Protocol):
			def __contains__(self, item: Any) -> bool: ...

		class Impl:
			def __contains__(self, item: Any) -> bool:
				return False

		implements(Impl, Container)

	def test_contains_missing(self):
		class Container(Protocol):
			def __contains__(self, item: Any) -> bool: ...

		class Impl:
			pass

		with pytest.raises(DoesNotImplementError, match="__contains__"):
			implements(Impl, Container)


# ============================================================
# inheritance
# ============================================================


class TestInheritance:
	def test_inherited_method_satisfies(self):
		class Base:
			def method(self, x: int) -> str:
				return str(x)

		class Impl(Base):
			pass

		implements(Impl, ProtocolWithMethod)

	def test_inherited_attr_satisfies(self):
		class Base:
			attr: str = "hello"

		class Impl(Base):
			pass

		implements(Impl, ProtocolWithAttr)

	def test_partial_inherited_partial_own(self):
		class Proto(Protocol):
			def foo(self) -> int: ...
			def bar(self) -> str: ...

		class Base:
			def foo(self) -> int:
				return 1

		class Impl(Base):
			def bar(self) -> str:
				return "x"

		implements(Impl, Proto)


# ============================================================
# annotated-only attributes (no default)
# ============================================================


class TestAnnotatedOnly:
	def test_annotation_only_satisfies_annotation_only(self):
		class Proto(Protocol):
			x: int

		class Impl:
			x: int

		implements(Impl, Proto)

	def test_annotation_with_default_satisfies(self):
		class Proto(Protocol):
			x: int

		class Impl:
			x: int = 5

		implements(Impl, Proto)

	def test_annotation_type_mismatch(self):
		class Proto(Protocol):
			x: int

		class Impl:
			x: str = "oops"

		with pytest.raises(DoesNotImplementError):
			implements(Impl, Proto)

	def test_multiple_annotations(self):
		class Proto(Protocol):
			x: int
			y: str
			z: float

		class Impl:
			x: int
			y: str
			z: float

		implements(Impl, Proto)

	def test_some_annotations_missing(self):
		class Proto(Protocol):
			x: int
			y: str
			z: float

		class Impl:
			x: int

		with pytest.raises(DoesNotImplementError) as exc_info:
			implements(Impl, Proto)

		assert len(exc_info.value.violations) >= 2


# ============================================================
# complex / multi-member protocols
# ============================================================


class TestComplexProtocols:
	def test_mixed_methods_and_attrs(self):
		class Proto(Protocol):
			name: str

			def process(self, data: bytes) -> str: ...
			def validate(self) -> bool: ...

		class Impl:
			name: str = "impl"

			def process(self, data: bytes) -> str:
				return data.decode()

			def validate(self) -> bool:
				return True

		implements(Impl, Proto)

	def test_all_wrong(self):
		class Proto(Protocol):
			name: str

			def process(self, data: bytes) -> str: ...

		class Impl:
			name: int = 42

			def process(self, data: int) -> int:
				return data

		with pytest.raises(DoesNotImplementError) as exc_info:
			implements(Impl, Proto)

		assert len(exc_info.value.violations) >= 2

	def test_method_and_property_together(self):
		class Proto(Protocol):
			@property
			def id(self) -> int: ...
			def run(self) -> None: ...

		class Impl:
			id: int = 1

			def run(self) -> None:
				pass

		implements(Impl, Proto)

	def test_protocol_with_only_dunders(self):
		class Proto(Protocol):
			def __len__(self) -> int: ...
			def __getitem__(self, idx: int) -> str: ...

		class Impl:
			def __len__(self) -> int:
				return 0

			def __getitem__(self, idx: int) -> str:
				return ""

		implements(Impl, Proto)


# ============================================================
# edge cases
# ============================================================


class TestEdgeCases:
	def test_protocol_attr_with_none_default(self):
		class Proto(Protocol):
			attr: str | None

		class Impl:
			attr: str | None = None

		implements(Impl, Proto)

	def test_impl_has_any_annotation(self):
		class Proto(Protocol):
			attr: str

		class Impl:
			attr: Any = "hello"

		implements(Impl, Proto)

	def test_method_no_return_annotation(self):
		"""no return annotation on either side — should pass."""

		class Proto(Protocol):
			def m(self): ...

		class Impl:
			def m(self):
				pass

		implements(Impl, Proto)

	def test_method_no_param_annotations(self):
		class Proto(Protocol):
			def m(self, x): ...

		class Impl:
			def m(self, x):
				pass

		implements(Impl, Proto)

	def test_method_partial_annotations(self):
		"""protocol annotated, impl not — no crash."""

		class Proto(Protocol):
			def m(self, x: int) -> str: ...

		class Impl:
			def m(self, x):
				return ""

		# should not crash — unannotated impl param is not checked
		implements(Impl, Proto)

	def test_class_with_slots(self):
		class Proto(Protocol):
			def m(self) -> int: ...

		class Impl:
			__slots__ = ()

			def m(self) -> int:
				return 0

		implements(Impl, Proto)

	def test_builtin_type_against_protocol(self):
		"""list has __len__, __getitem__ etc."""

		class Sized(Protocol):
			def __len__(self) -> int: ...

		# should not crash
		implements(list, Sized)


# ============================================================
# protocol-typed annotations
# ============================================================


class TestProtocolTypedAnnotations:
	def test_attr_typed_as_protocol_satisfied(self):
		class Strable(Protocol):
			def __str__(self) -> str: ...

		class Proto(Protocol):
			attr: Strable

		class Impl:
			attr: str = "hello"

		implements(Impl, Proto)

	def test_attr_typed_as_protocol_not_satisfied(self):
		class HasFoo(Protocol):
			def foo(self) -> int: ...

		class Proto(Protocol):
			attr: HasFoo

		class Impl:
			attr: str = "hello"

		with pytest.raises(DoesNotImplementError):
			implements(Impl, Proto)

	def test_attr_typed_as_protocol_union_all_satisfy(self):
		class Strable(Protocol):
			def __str__(self) -> str: ...

		class Proto(Protocol):
			attr: Strable

		class Impl:
			attr: str | int | float

		implements(Impl, Proto)

	def test_attr_typed_as_protocol_union_partial_fail(self):
		class HasFoo(Protocol):
			def foo(self) -> int: ...

		class Good:
			def foo(self) -> int:
				return 1

		class Proto(Protocol):
			attr: HasFoo

		class Impl:
			attr: Good | str  # str doesn't have foo

		with pytest.raises(DoesNotImplementError):
			implements(Impl, Proto)
