import typing
from collections.abc import Sequence
from typing import Any, Protocol

from sotkalib.type.iface import compatible


class TestIdentityAndAny:
	def test_same_type(self):
		assert compatible(int, int) is True

	def test_want_any(self):
		assert compatible(Any, int) is True

	def test_have_any(self):
		assert compatible(int, Any) is True

	def test_both_any(self):
		assert compatible(Any, Any) is True


class TestUnions:
	def test_both_unions_exact(self):
		assert compatible(str | int, str | int) is True

	def test_have_broader_union(self):
		assert compatible(str | int, str | int | float) is True

	def test_have_narrower_union_fails(self):
		assert compatible(str | int | float, str | int) is False

	def test_optional(self):
		assert compatible(str | None, str | None) is True


class TestGenerics:
	def test_same_parameterized(self):
		assert compatible(list[int], list[int]) is True

	def test_different_args(self):
		assert compatible(list[int], list[str]) is False

	def test_want_bare_have_parameterized(self):
		"""want=list (doesn't care about inner type) accepts list[int]"""
		assert compatible(list, list[int]) is True

	def test_want_parameterized_have_bare(self):
		"""want=list[int] rejects list (less specific)"""
		assert compatible(list[int], list) is False

	def test_dict_same(self):
		assert compatible(dict[str, int], dict[str, int]) is True

	def test_dict_value_mismatch(self):
		assert compatible(dict[str, int], dict[str, str]) is False

	def test_arg_subclass_compat(self):
		"""want=list[int], have=list[bool] — bool is subclass of int."""
		assert compatible(list[int], list[bool]) is True

	def test_arg_superclass_incompatible(self):
		"""want=list[bool], have=list[int] — int is not subclass of bool."""
		assert compatible(list[bool], list[int]) is False

	def test_dict_value_subclass(self):
		"""want=dict[str, int], have=dict[str, bool] — bool < int."""
		assert compatible(dict[str, int], dict[str, bool]) is True

	def test_dict_key_subclass_value_mismatch(self):
		"""want=dict[int, str], have=dict[bool, int] — key ok, value not."""
		assert compatible(dict[int, str], dict[bool, int]) is False

	def test_nested_same(self):
		assert compatible(list[list[int]], list[list[int]]) is True

	def test_nested_inner_mismatch(self):
		assert compatible(list[list[int]], list[list[str]]) is False

	def test_nested_inner_subclass(self):
		"""want=list[list[int]], have=list[list[bool]] — inner bool < int."""
		assert compatible(list[list[int]], list[list[bool]]) is True

	def test_want_any_arg(self):
		"""want=list[Any] accepts any parameterized list."""
		assert compatible(list[Any], list[int]) is True

	def test_have_any_arg(self):
		"""have=list[Any] satisfies want=list[int] (Any is always compat)."""
		assert compatible(list[int], list[Any]) is True

	def test_both_bare(self):
		"""Both bare — identity check via origin=None, falls to issubclass."""
		assert compatible(list, list) is True

	def test_unrelated_origins_lenient(self):
		"""want=list[int], have=tuple[int] — unrelated origins, lenient passes via fallback."""
		assert compatible(list[int], tuple[int]) is True

	def test_unrelated_origins_strict(self):
		"""want=list[int], have=tuple[int] — unrelated origins, strict rejects."""
		assert compatible(list[int], tuple[int], strict=True) is False

	def test_sequence_vs_list(self):
		"""want=Sequence[int], have=list[int] — list implements Sequence, should accept."""
		assert compatible(Sequence[int], list[int]) is True

	def test_sequence_vs_list_strict(self):
		"""Cross-origin subclass works in strict mode too."""
		assert compatible(Sequence[int], list[int], strict=True) is True

	def test_sequence_vs_list_arg_mismatch(self):
		"""Cross-origin but arg types don't match."""
		assert compatible(Sequence[str], list[int]) is False

	def test_list_vs_sequence_not_compat(self):
		"""want=list[int], have=Sequence[int] — Sequence is not subclass of list."""
		assert compatible(list[int], Sequence[int], strict=True) is False

	def test_want_more_args_than_have(self):
		"""want=dict[str, int] vs have=dict[str] — zip truncates, partial match."""
		# zip(strict=False) means extra args in want are ignored
		assert compatible(dict[str, int], dict[str]) is True

	def test_have_more_args_than_want(self):
		"""want=dict[str] vs have=dict[str, int] — zip truncates."""
		assert compatible(dict[str], dict[str, int]) is True


class TestSubclass:
	def test_same_class(self):
		assert compatible(int, int) is True

	def test_bool_is_int(self):
		assert compatible(int, bool) is True

	def test_int_is_not_str(self):
		assert compatible(str, int) is False


class TestStrictFallback:
	def test_fallback_lenient_by_default(self):
		"""Unrecognized type forms pass in lenient mode."""
		assert compatible(typing.TypeVar("T"), int) is True

	def test_fallback_strict_rejects(self):
		"""Unrecognized type forms fail in strict mode."""
		assert compatible(typing.TypeVar("T"), int, strict=True) is False


class TestHaveUnionWantConcrete:
	def test_all_members_subclass(self):
		"""want=int, have=int|bool — bool is subclass of int, so compatible."""
		assert compatible(int, int | bool) is True

	def test_some_members_incompatible(self):
		"""want=int, have=int|str — str is not int, so incompatible."""
		assert compatible(int, int | str) is False

	def test_want_generic_have_union_of_generics(self):
		"""want=list[int], have=list[int]|list[int] — all compatible."""
		assert compatible(list[int], list[int] | list[int]) is True

	def test_want_concrete_have_union_incompatible(self):
		"""want=str, have=int|float — neither is str."""
		assert compatible(str, int | float) is False


class TestProtocolCompat:
	def test_concrete_implements_protocol(self):
		class Strable(Protocol):
			def __str__(self) -> str: ...

		assert compatible(Strable, str) is True

	def test_concrete_does_not_implement_protocol(self):
		class HasFoo(Protocol):
			def foo(self) -> int: ...

		assert compatible(HasFoo, str) is False

	def test_union_all_implement_protocol(self):
		class Strable(Protocol):
			def __str__(self) -> str: ...

		assert compatible(Strable, str | int | float) is True

	def test_union_some_fail_protocol(self):
		class HasFoo(Protocol):
			def foo(self) -> int: ...

		class Good:
			def foo(self) -> int:
				return 1

		assert compatible(HasFoo, Good | str) is False

	def test_protocol_vs_protocol_subclass(self):
		"""If want is a protocol and have is also a protocol, check structural compat."""

		class Base(Protocol):
			def m(self) -> int: ...

		class Extended(Protocol):
			def m(self) -> int: ...
			def n(self) -> str: ...

		# Extended structurally satisfies Base (has m)
		assert compatible(Base, Extended) is True
