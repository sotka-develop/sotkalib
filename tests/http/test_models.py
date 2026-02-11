from http import HTTPStatus

import pytest
from aiohttp import client_exceptions

from sotkalib.http.models import (
	ClientSettings,
	ExceptionSettings,
	StatusSettings,
	_MergeableSettings,
)


class TestStatusSettingsMerge:
	def test_merge_overrides_explicit_fields(self):
		base = StatusSettings(not_found_as_none=True, unspecified="retry")
		patch = StatusSettings(unspecified="raise")
		result = base | patch
		assert result.not_found_as_none is True
		assert result.unspecified == "raise"

	def test_merge_does_not_mutate_base(self):
		base = StatusSettings(not_found_as_none=True)
		patch = StatusSettings(not_found_as_none=False)
		_ = base | patch
		assert base.not_found_as_none is True

	def test_merge_ignores_default_fields(self):
		base = StatusSettings(not_found_as_none=False, unspecified="raise")
		patch = StatusSettings(not_found_as_none=True)
		result = base | patch
		assert result.not_found_as_none is True
		assert result.unspecified == "raise"

	def test_merge_to_raise_set(self):
		base = StatusSettings(to_raise={HTTPStatus.FORBIDDEN})
		patch = StatusSettings(to_raise={HTTPStatus.UNAUTHORIZED, HTTPStatus.NOT_FOUND})
		result = base | patch
		assert result.to_raise == {HTTPStatus.UNAUTHORIZED, HTTPStatus.NOT_FOUND}

	def test_merge_to_retry_set(self):
		base = StatusSettings(to_retry={HTTPStatus.TOO_MANY_REQUESTS})
		patch = StatusSettings(to_retry={HTTPStatus.SERVICE_UNAVAILABLE})
		result = base | patch
		assert result.to_retry == {HTTPStatus.SERVICE_UNAVAILABLE}

	def test_merge_exc_to_raise(self):
		base = StatusSettings()
		patch = StatusSettings(exc_to_raise=ValueError)
		result = base | patch
		assert result.exc_to_raise is ValueError

	def test_merge_chained(self):
		base = StatusSettings(not_found_as_none=True)
		a = StatusSettings(unspecified="raise")
		b = StatusSettings(to_raise={HTTPStatus.UNAUTHORIZED})
		result = base | a | b
		assert result.not_found_as_none is True
		assert result.unspecified == "raise"
		assert result.to_raise == {HTTPStatus.UNAUTHORIZED}

	def test_merge_with_incompatible_type_returns_not_implemented(self):
		base = StatusSettings()
		result = base.__or__("invalid")
		assert result is NotImplemented


class TestExceptionSettingsMerge:
	def test_merge_overrides_explicit_fields(self):
		base = ExceptionSettings(unspecified="retry")
		patch = ExceptionSettings(unspecified="raise")
		result = base | patch
		assert result.unspecified == "raise"

	def test_merge_does_not_mutate_base(self):
		base = ExceptionSettings(unspecified="retry")
		patch = ExceptionSettings(unspecified="raise")
		_ = base | patch
		assert base.unspecified == "retry"

	def test_merge_ignores_default_fields(self):
		base = ExceptionSettings(unspecified="raise", exc_to_raise=ValueError)
		patch = ExceptionSettings(unspecified="retry")
		result = base | patch
		assert result.unspecified == "retry"
		assert result.exc_to_raise is ValueError

	def test_merge_to_raise_tuple(self):
		base = ExceptionSettings(to_raise=(TimeoutError,))
		patch = ExceptionSettings(to_raise=(ValueError, TypeError))
		result = base | patch
		assert result.to_raise == (ValueError, TypeError)

	def test_merge_to_retry_tuple(self):
		base = ExceptionSettings(to_retry=(TimeoutError,))
		patch = ExceptionSettings(to_retry=(client_exceptions.ServerDisconnectedError,))
		result = base | patch
		assert result.to_retry == (client_exceptions.ServerDisconnectedError,)

	def test_merge_exc_to_raise(self):
		base = ExceptionSettings()
		patch = ExceptionSettings(exc_to_raise=RuntimeError)
		result = base | patch
		assert result.exc_to_raise is RuntimeError

	def test_merge_chained(self):
		base = ExceptionSettings(unspecified="retry")
		a = ExceptionSettings(exc_to_raise=ValueError)
		b = ExceptionSettings(to_raise=(TypeError,))
		result = base | a | b
		assert result.unspecified == "retry"
		assert result.exc_to_raise is ValueError
		assert result.to_raise == (TypeError,)

	def test_merge_with_incompatible_type_returns_not_implemented(self):
		base = ExceptionSettings()
		result = base.__or__(123)
		assert result is NotImplemented


class TestClientSettingsMergeEdgeCases:
	def test_merge_with_empty_patch(self):
		base = ClientSettings(timeout=10.0, maximum_retries=5)
		patch = ClientSettings()
		result = base | patch
		assert result.timeout == 10.0
		assert result.maximum_retries == 5

	def test_merge_empty_base_with_patch(self):
		base = ClientSettings()
		patch = ClientSettings(timeout=30.0, backoff=5.0)
		result = base | patch
		assert result.timeout == 30.0
		assert result.backoff == 5.0
		assert result.maximum_retries == 3  # default

	def test_merge_preserves_nested_defaults_when_not_set(self):
		base = ClientSettings(timeout=10.0)
		patch = ClientSettings(maximum_retries=1)
		result = base | patch
		# nested settings should have defaults
		assert result.status_settings.not_found_as_none is True
		assert result.exception_settings.unspecified == "retry"

	def test_merge_deeply_nested_does_not_mutate(self):
		base = ClientSettings(status_settings=StatusSettings(not_found_as_none=True, unspecified="retry"))
		patch = ClientSettings(status_settings=StatusSettings(unspecified="raise"))
		_ = base | patch
		assert base.status_settings.unspecified == "retry"
		assert base.status_settings.not_found_as_none is True

	def test_merge_with_incompatible_type_returns_not_implemented(self):
		base = ClientSettings()
		result = base.__or__("invalid")
		assert result is NotImplemented

	def test_merge_with_incompatible_settings_type_returns_not_implemented(self):
		base = ClientSettings()

		class OtherSettings(_MergeableSettings):
			value: int = 1

		result = base.__or__(OtherSettings())
		assert result is NotImplemented

	def test_merge_session_kwargs(self):
		base = ClientSettings(session_kwargs={"timeout": 10})
		patch = ClientSettings(session_kwargs={"timeout": 30, "headers": {"X-Custom": "val"}})
		result = base | patch
		assert result.session_kwargs == {"timeout": 30, "headers": {"X-Custom": "val"}}

	def test_merge_useragent_factory(self):
		def factory_a():
			return "Agent A"

		def factory_b():
			return "Agent B"

		base = ClientSettings(useragent_factory=factory_a)
		patch = ClientSettings(useragent_factory=factory_b)
		result = base | patch
		assert result.useragent_factory is factory_b
		assert result.useragent_factory() == "Agent B"

	def test_merge_all_types(self):
		def factory_a():
			return "Agent A"

		def factory_b():
			return "Agent B"

		result = (
			ClientSettings(useragent_factory=factory_a)
			| ClientSettings(useragent_factory=factory_b)
			| ExceptionSettings(unspecified="raise")
			| StatusSettings(unspecified="raise")
		)

		print(result)
		assert result.exception_settings.unspecified == "raise"
		assert result.status_settings.unspecified == "raise"
		assert result.useragent_factory() == "Agent B"

	def test_merge_use_cookies_from_response(self):
		base = ClientSettings(use_cookies_from_response=False)
		patch = ClientSettings(use_cookies_from_response=True)
		result = base | patch
		assert result.use_cookies_from_response is True


class TestMergeableSettingsInternals:
	def test_merge_from_method_directly(self):
		base = StatusSettings(not_found_as_none=True)
		patch = StatusSettings(unspecified="raise")
		result = base._merge_from(patch)
		assert result.not_found_as_none is True
		assert result.unspecified == "raise"

	def test_merge_from_does_not_mutate_original(self):
		base = StatusSettings(not_found_as_none=True)
		patch = StatusSettings(not_found_as_none=False)
		_ = base._merge_from(patch)
		assert base.not_found_as_none is True

	def test_model_fields_set_tracking(self):
		# Pydantic tracks which fields were explicitly set
		s = StatusSettings(not_found_as_none=False)
		assert "not_found_as_none" in s.model_fields_set
		assert "unspecified" not in s.model_fields_set

	def test_merge_only_applies_explicitly_set_fields(self):
		base = StatusSettings(not_found_as_none=True, unspecified="raise")
		# Only set not_found_as_none, unspecified uses default
		patch = StatusSettings(not_found_as_none=False)
		result = base | patch
		assert result.not_found_as_none is False
		# unspecified should retain base value since it wasn't explicitly set in patch
		assert result.unspecified == "raise"


class TestDeprecatedWithMethod:
	def test_with_emits_deprecation_warning(self):
		base = ClientSettings(timeout=10.0)
		with pytest.warns(DeprecationWarning, match="with_.*deprecated"):
			_ = base.with_(maximum_retries=5)

	def test_with_simple_override(self):
		base = ClientSettings(timeout=10.0)
		with pytest.warns(DeprecationWarning):
			result = base.with_(maximum_retries=5)
		assert result.timeout == 10.0
		assert result.maximum_retries == 5

	def test_with_nested_override(self):
		base = ClientSettings(status_settings=StatusSettings(not_found_as_none=True))
		with pytest.warns(DeprecationWarning):
			result = base.with_(**{"status_settings.unspecified": "raise"})
		assert result.status_settings.not_found_as_none is True
		assert result.status_settings.unspecified == "raise"

	def test_with_does_not_mutate_base(self):
		base = ClientSettings(timeout=10.0)
		with pytest.warns(DeprecationWarning):
			_ = base.with_(timeout=30.0)
		assert base.timeout == 10.0
