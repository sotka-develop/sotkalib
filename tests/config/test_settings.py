import pytest

from sotkalib.config.field import SettingsField
from sotkalib.config.struct import AppSettings


class TestSettingsField:
	def test_defaults(self):
		f = SettingsField()
		assert f.default is None
		assert f.factory is None
		assert f.nullable is False

	def test_frozen(self):
		f = SettingsField(default="x")
		with pytest.raises(AttributeError):
			# pyrefly: ignore [read-only]
			f.default = "y"


class TestAppSettings:
	def test_from_env(self, monkeypatch):
		monkeypatch.setenv("MY_TOKEN", "secret123")

		class Settings(AppSettings):
			MY_TOKEN: str = SettingsField(nullable=False)

		s = Settings(explicit_format=True)
		assert s.MY_TOKEN == "secret123"

	def test_default_value(self):
		class Settings(AppSettings):
			MY_VAR: str = SettingsField(default="fallback")

		s = Settings()
		assert s.MY_VAR == "fallback"

	def test_factory_callable(self):
		class Settings(AppSettings):
			MY_VAR: str = SettingsField(factory=lambda: "from_factory")

		s = Settings()
		assert s.MY_VAR == "from_factory"

	def test_factory_property(self):
		class Settings(AppSettings):
			MY_VAR: str = SettingsField(factory="computed")

			@property
			def computed(self) -> str:
				return "from_property"

		s = Settings()
		assert s.MY_VAR == "from_property"

	def test_factory_property_missing(self):
		class Settings(AppSettings):
			MY_VAR: str = SettingsField(factory="nonexistent")

		with pytest.raises(AttributeError, match="nonexistent"):
			Settings()

	def test_factory_property_not_property(self):
		class Settings(AppSettings):
			MY_VAR: str = SettingsField(factory="not_a_prop")

			def not_a_prop(self) -> str:
				return "x"

		with pytest.raises(TypeError, match="not a property"):
			Settings()

	def test_nullable(self):
		class Settings(AppSettings):
			MY_VAR: str | None = SettingsField(nullable=True)

		s = Settings()
		assert s.MY_VAR is None

	def test_required_missing_raises(self):
		class Settings(AppSettings):
			MISSING_VAR: str = SettingsField(nullable=False)

		with pytest.raises(ValueError, match="reqd field"):
			Settings()

	def test_explicit_format_rejects_lowercase(self):
		class Settings(AppSettings):
			bad_name: str = SettingsField(default="x")

		with pytest.raises(AttributeError, match="capital letters"):
			Settings(explicit_format=True)

	def test_explicit_format_off_allows_lowercase(self):
		class Settings(AppSettings):
			bad_name: str = SettingsField(default="x")

		s = Settings(explicit_format=False)
		assert s.bad_name == "x"

	def test_bool_from_env(self, monkeypatch):
		monkeypatch.setenv("MY_FLAG", "true")

		class Settings(AppSettings):
			MY_FLAG: bool = SettingsField(nullable=False)

		s = Settings()
		assert s.MY_FLAG is True

	def test_bool_false_from_env(self, monkeypatch):
		monkeypatch.setenv("MY_FLAG", "no")

		class Settings(AppSettings):
			MY_FLAG: bool = SettingsField(nullable=False)

		s = Settings()
		assert s.MY_FLAG is False

	def test_int_from_env(self, monkeypatch):
		monkeypatch.setenv("MY_PORT", "8080")

		class Settings(AppSettings):
			MY_PORT: int = SettingsField(nullable=False)

		s = Settings()
		assert s.MY_PORT == 8080

	def test_strict_rejects_mutable(self):
		class Settings(AppSettings):
			MY_VAR: str = SettingsField(factory=lambda: [1, 2, 3])

		with pytest.raises(TypeError, match="not an allowed immutable type"):
			Settings(strict=True)

	def test_non_strict_sets_mutable_to_none(self):
		class Settings(AppSettings):
			MY_VAR: str = SettingsField(factory=lambda: [1, 2, 3])

		with pytest.warns(match="mutable"):
			s = Settings(strict=False)

		assert s.MY_VAR is None
