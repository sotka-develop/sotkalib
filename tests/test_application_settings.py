import os
from unittest.mock import MagicMock

import pytest

from sotkalib.config.field import SettingsField
from sotkalib.config.struct import AppSettings


class TestAppSettings:
    """Test suite for AppSettings class"""

    def test_basic_initialization(self):
        """Test basic initialization with no environment variables"""

        class TestSettings(AppSettings):
            TEST_VAR = SettingsField[str](nullable=True)

        settings = TestSettings()
        assert hasattr(settings, "TEST_VAR")
        assert settings.TEST_VAR is None

    def test_environment_variable_loading(self):
        """Test loading values from environment variables"""
        os.environ["STRING_VAR"] = "test_value"
        os.environ["INT_VAR"] = "42"
        os.environ["BOOL_VAR"] = "true"
        os.environ["FLOAT_VAR"] = "3.14"

        class TestSettings(AppSettings):
            STRING_VAR: str = SettingsField(nullable=False)
            INT_VAR: int = SettingsField(nullable=False)
            BOOL_VAR: bool = SettingsField(nullable=False)
            FLOAT_VAR: float = SettingsField(nullable=False)

        settings = TestSettings()
        assert settings.STRING_VAR == "test_value"
        assert settings.INT_VAR == 42
        assert settings.BOOL_VAR is True
        assert settings.FLOAT_VAR == 3.14

        # Clean up
        del os.environ["STRING_VAR"]
        del os.environ["INT_VAR"]
        del os.environ["BOOL_VAR"]
        del os.environ["FLOAT_VAR"]

    def test_default_values(self):
        """Test default value usage when environment variable is missing"""

        class TestSettings(AppSettings):
            DEFAULT_STR: str = SettingsField(default="default_value")
            DEFAULT_INT: int = SettingsField(default=100)

        settings = TestSettings()
        assert settings.DEFAULT_STR == "default_value"
        assert settings.DEFAULT_INT == 100

    def test_callable_factory(self):
        """Test callable factory functions"""

        def generate_token():
            return "generated_token"

        class TestSettings(AppSettings):
            TOKEN: str = SettingsField(factory=generate_token)

        settings = TestSettings()
        assert settings.TOKEN == "generated_token"

    def test_property_factory(self):
        """Test property-based factory resolution"""

        class TestSettings(AppSettings):
            COMPUTED_VALUE: str = SettingsField(factory="computed_property")

            @property
            def computed_property(self) -> str:
                return "computed_result"

        settings = TestSettings()
        assert settings.COMPUTED_VALUE == "computed_result"

    def test_nullable_fields(self):
        """Test nullable field behavior"""

        class TestSettings(AppSettings):
            NULLABLE_VAR: str = SettingsField(nullable=True)
            NON_NULLABLE_VAR: str = SettingsField(nullable=False, default="required")

        settings = TestSettings()
        assert settings.NULLABLE_VAR is None
        assert settings.NON_NULLABLE_VAR == "required"

    def test_missing_required_field_error(self):
        """Test error when required field is missing"""

        class TestSettings(AppSettings):
            REQUIRED_VAR: str = SettingsField(nullable=False)

        with pytest.raises(ValueError, match="Required field REQUIRED_VAR was not found in .env"):
            TestSettings()

    def test_invalid_attribute_name_format(self):
        """Test error when attribute name doesn't match explicit_format"""

        class TestSettings(AppSettings):
            invalid_name: str = SettingsField(nullable=True)

        with pytest.raises(
            AttributeError, match="AppSettings attributes should contain only capital letters and underscores"
        ):
            TestSettings()

    def test_explicit_format_disabled(self):
        """Test that explicit_format=False allows any attribute name"""

        class TestSettings(AppSettings):
            any_name: str = SettingsField(nullable=True)

        settings = TestSettings(explicit_format=False)
        assert settings.any_name is None

    def test_missing_property_error(self):
        """Test error when factory references non-existent property"""

        class TestSettings(AppSettings):
            MISSING_PROP: str = SettingsField(factory="non_existent_property")

        with pytest.raises(AttributeError, match="Property non_existent_property was not found"):
            TestSettings()

    def test_non_property_factory_error(self):
        """Test error when factory references non-property method"""

        class TestSettings(AppSettings):
            INVALID_FACTORY: str = SettingsField(factory="regular_method")

            def regular_method(self):
                return "not_a_property"

        with pytest.raises(TypeError, match="Method regular_method is not a property"):
            TestSettings()

    def test_immutable_value_validation(self):
        """Test that only immutable types are allowed"""

        class TestSettings(AppSettings):
            VALID_STR: str = SettingsField(nullable=True)

        settings = TestSettings()
        assert settings.VALID_STR is None

        # Test that mutable types are rejected
        with pytest.raises(TypeError, match="is not allowed for annotations as it is mutable"):

            class InvalidSettings(AppSettings):
                INVALID_LIST: list = SettingsField(nullable=True)

    def test_bool_evaluation(self):
        """Test boolean evaluation from string values"""
        os.environ["BOOL_TRUE"] = "yes"
        os.environ["BOOL_FALSE"] = "no"

        class TestSettings(AppSettings):
            BOOL_TRUE: bool = SettingsField(nullable=False)
            BOOL_FALSE: bool = SettingsField(nullable=False)

        settings = TestSettings()
        assert settings.BOOL_TRUE is True
        assert settings.BOOL_FALSE is False

        # Clean up
        del os.environ["BOOL_TRUE"]
        del os.environ["BOOL_FALSE"]

    def test_complex_type(self):
        """Test complex number type"""
        os.environ["COMPLEX_VAR"] = "1+2j"

        class TestSettings(AppSettings):
            COMPLEX_VAR: complex = SettingsField(nullable=False)

        settings = TestSettings()
        assert settings.COMPLEX_VAR == 1 + 2j

        # Clean up
        del os.environ["COMPLEX_VAR"]

    def test_dotenv_loading(self, tmp_path):
        """Test .env file loading"""
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_VAR=from_env_file\nANOTHER_VAR=123")

        class TestSettings(AppSettings):
            TEST_VAR: str = SettingsField(nullable=False)
            ANOTHER_VAR: int = SettingsField(nullable=False)

        settings = TestSettings(dotenv_path=env_file)
        assert settings.TEST_VAR == "from_env_file"
        assert settings.ANOTHER_VAR == 123

    def test_logger_integration(self):
        """Test custom logger integration"""
        mock_logger = MagicMock()

        class TestSettings(AppSettings):
            TEST_VAR: str = SettingsField(default="test")

        settings = TestSettings(logger=mock_logger)
        assert settings.TEST_VAR == "test"
        # Verify logger was used
        assert settings._logger == mock_logger

    def test_mixed_field_types(self):
        """Test a mix of different field configurations"""
        os.environ["FROM_ENV"] = "env_value"

        class TestSettings(AppSettings):
            FROM_ENV: str = SettingsField(nullable=False)
            WITH_DEFAULT: str = SettingsField(default="default")
            FROM_FACTORY: str = SettingsField(factory=lambda: "factory_value")
            NULLABLE: str = SettingsField(nullable=True)
            FROM_PROPERTY: str = SettingsField(factory="prop_value")

            @property
            def prop_value(self) -> str:
                return "property_value"

        settings = TestSettings()
        assert settings.FROM_ENV == "env_value"
        assert settings.WITH_DEFAULT == "default"
        assert settings.FROM_FACTORY == "factory_value"
        assert settings.NULLABLE is None
        assert settings.FROM_PROPERTY == "property_value"

        # Clean up
        del os.environ["FROM_ENV"]

    def test_immutable_value_assignment(self):
        """Test that only immutable values can be assigned"""

        class TestSettings(AppSettings):
            STR_VAR: str = SettingsField(default="initial")

        settings = TestSettings()
        assert settings.STR_VAR == "initial"

        # Test that we can't assign mutable values
        with pytest.raises(TypeError, match="is not allowed for annotations as it is mutable"):
            settings.STR_VAR = ["mutable", "list"]

    def test_union_types(self):
        """Test Union type handling"""
        os.environ["UNION_VAR"] = "42"

        class TestSettings(AppSettings):
            UNION_VAR: int | str = SettingsField(nullable=False)

        settings = TestSettings()
        assert settings.UNION_VAR == 42

        # Clean up
        del os.environ["UNION_VAR"]

    def test_empty_string_handling(self):
        """Test empty string handling"""
        os.environ["EMPTY_VAR"] = ""

        class TestSettings(AppSettings):
            EMPTY_VAR: str = SettingsField(nullable=False)

        settings = TestSettings()
        assert settings.EMPTY_VAR == ""

        # Clean up
        del os.environ["EMPTY_VAR"]

    def test_special_boolean_values(self):
        """Test various boolean string representations"""
        test_cases = [
            ("yes", True),
            ("true", True),
            ("1", True),
            ("y", True),
            ("no", False),
            ("false", False),
            ("0", False),
            ("n", False),
        ]

        for env_value, expected in test_cases:
            os.environ["BOOL_TEST"] = env_value

            class TestSettings(AppSettings):
                BOOL_TEST: bool = SettingsField(nullable=False)

            settings = TestSettings()
            assert expected == settings.BOOL_TEST

            # Clean up
            del os.environ["BOOL_TEST"]

    def test_numeric_edge_cases(self):
        """Test numeric edge cases"""
        os.environ["ZERO_INT"] = "0"
        os.environ["NEGATIVE_INT"] = "-42"
        os.environ["ZERO_FLOAT"] = "0.0"
        os.environ["NEGATIVE_FLOAT"] = "-3.14"

        class TestSettings(AppSettings):
            ZERO_INT: int = SettingsField(nullable=False)
            NEGATIVE_INT: int = SettingsField(nullable=False)
            ZERO_FLOAT: float = SettingsField(nullable=False)
            NEGATIVE_FLOAT: float = SettingsField(nullable=False)

        settings = TestSettings()
        assert settings.ZERO_INT == 0
        assert settings.NEGATIVE_INT == -42
        assert settings.ZERO_FLOAT == 0.0
        assert settings.NEGATIVE_FLOAT == -3.14

        # Clean up
        del os.environ["ZERO_INT"]
        del os.environ["NEGATIVE_INT"]
        del os.environ["ZERO_FLOAT"]
        del os.environ["NEGATIVE_FLOAT"]

    def test_environment_priority(self):
        """Test that environment variables take precedence over defaults"""
        os.environ["PRIORITY_VAR"] = "from_environment"

        class TestSettings(AppSettings):
            PRIORITY_VAR: str = SettingsField(default="from_default")

        settings = TestSettings()
        assert settings.PRIORITY_VAR == "from_environment"

        # Clean up
        del os.environ["PRIORITY_VAR"]

    def test_factory_priority(self):
        """Test factory precedence when no environment variable"""

        class TestSettings(AppSettings):
            FACTORY_VAR: str = SettingsField(factory=lambda: "from_factory", default="from_default")

        settings = TestSettings()
        assert settings.FACTORY_VAR == "from_factory"

    def test_none_type_handling(self):
        """Test None type handling"""

        class TestSettings(AppSettings):
            NONE_VAR: None = SettingsField(nullable=True)

        settings = TestSettings()
        assert settings.NONE_VAR is None

    def test_inheritance(self):
        """Test AppSettings inheritance"""

        class BaseSettings(AppSettings):
            BASE_VAR: str = SettingsField(default="base_value")

        class DerivedSettings(BaseSettings):
            DERIVED_VAR: str = SettingsField(default="derived_value")

        settings = DerivedSettings()
        assert settings.BASE_VAR == "base_value"
        assert settings.DERIVED_VAR == "derived_value"

    def test_multiple_instances(self):
        """Test multiple instances of same settings class"""
        os.environ["SHARED_VAR"] = "shared_value"

        class TestSettings(AppSettings):
            SHARED_VAR: str = SettingsField(nullable=False)
            INSTANCE_VAR: str = SettingsField(factory=lambda: f"instance_{id(self)}")

        settings1 = TestSettings()
        settings2 = TestSettings()

        assert settings1.SHARED_VAR == "shared_value"
        assert settings2.SHARED_VAR == "shared_value"
        assert settings1.INSTANCE_VAR != settings2.INSTANCE_VAR
        assert settings1.INSTANCE_VAR.startswith("instance_")
        assert settings2.INSTANCE_VAR.startswith("instance_")

        # Clean up
        del os.environ["SHARED_VAR"]

    def test_attribute_access_after_initialization(self):
        """Test that attributes can be accessed normally after initialization"""

        class TestSettings(AppSettings):
            TEST_VAR: str = SettingsField(default="test_value")

        settings = TestSettings()
        assert hasattr(settings, "TEST_VAR")
        assert settings.TEST_VAR == "test_value"
        assert settings.TEST_VAR == "test_value"

    def test_underscore_only_names(self):
        """Test attribute names with underscores"""

        class TestSettings(AppSettings):
            _PRIVATE_VAR: str = SettingsField(default="private")
            __DUNDER_VAR: str = SettingsField(default="dunder")

        settings = TestSettings()
        assert settings._PRIVATE_VAR == "private"
        assert settings.__DUNDER_VAR == "dunder"

    def test_case_sensitivity(self):
        """Test that attribute names are case-sensitive"""
        os.environ["UPPER_VAR"] = "upper_value"
        os.environ["lower_var"] = "lower_value"

        class TestSettings(AppSettings):
            UPPER_VAR: str = SettingsField(nullable=False)
            lower_var: str = SettingsField(nullable=False)

        settings = TestSettings(explicit_format=False)
        assert settings.UPPER_VAR == "upper_value"
        assert settings.lower_var == "lower_value"

        # Clean up
        del os.environ["UPPER_VAR"]
        del os.environ["lower_var"]

    def test_whitespace_in_values(self):
        """Test handling of whitespace in environment values"""
        os.environ["WHITESPACE_VAR"] = "  trimmed_value  "

        class TestSettings(AppSettings):
            WHITESPACE_VAR: str = SettingsField(nullable=False)

        settings = TestSettings()
        assert settings.WHITESPACE_VAR == "  trimmed_value  "

        # Clean up
        del os.environ["WHITESPACE_VAR"]

    def test_special_characters_in_values(self):
        """Test handling of special characters in environment values"""
        os.environ["SPECIAL_VAR"] = "special!@#$%^&*()_+-=[]{}|;:,.<>?"

        class TestSettings(AppSettings):
            SPECIAL_VAR: str = SettingsField(nullable=False)

        settings = TestSettings()
        assert settings.SPECIAL_VAR == "special!@#$%^&*()_+-=[]{}|;:,.<>?"

        # Clean up
        del os.environ["SPECIAL_VAR"]

    def test_unicode_values(self):
        """Test handling of unicode values"""
        os.environ["UNICODE_VAR"] = "Hello 世界 🌍"

        class TestSettings(AppSettings):
            UNICODE_VAR: str = SettingsField(nullable=False)

        settings = TestSettings()
        assert settings.UNICODE_VAR == "Hello 世界 🌍"

        # Clean up
        del os.environ["UNICODE_VAR"]

    def test_large_numeric_values(self):
        """Test handling of large numeric values"""
        os.environ["LARGE_INT"] = "999999999999999999"
        os.environ["LARGE_FLOAT"] = "999999999999999999.999999999999999999"

        class TestSettings(AppSettings):
            LARGE_INT: int = SettingsField(nullable=False)
            LARGE_FLOAT: float = SettingsField(nullable=False)

        settings = TestSettings()
        assert settings.LARGE_INT == 999999999999999999
        assert settings.LARGE_FLOAT == 999999999999999999.999999999999999999

        # Clean up
        del os.environ["LARGE_INT"]
        del os.environ["LARGE_FLOAT"]

    def test_scientific_notation(self):
        """Test handling of scientific notation"""
        os.environ["SCI_INT"] = "1e6"
        os.environ["SCI_FLOAT"] = "1.5e-3"

        class TestSettings(AppSettings):
            SCI_INT: int = SettingsField(nullable=False)
            SCI_FLOAT: float = SettingsField(nullable=False)

        settings = TestSettings()
        assert settings.SCI_INT == 1000000
        assert settings.SCI_FLOAT == 0.0015

        # Clean up
        del os.environ["SCI_INT"]
        del os.environ["SCI_FLOAT"]

    def test_empty_annotations(self):
        """Test that settings without annotations are ignored"""

        class TestSettings(AppSettings):
            ANNOTATED_VAR: str = SettingsField(default="annotated")
            non_annotated_var = "not_annotated"

        settings = TestSettings()
        assert settings.ANNOTATED_VAR == "annotated"
        assert settings.non_annotated_var == "not_annotated"

    def test_logger_info_messages(self, caplog):
        """Test that appropriate log messages are generated"""

        class TestSettings(AppSettings):
            DEFAULT_VAR: str = SettingsField(default="default_value")
            NULLABLE_VAR: str = SettingsField(nullable=True)

        with caplog.at_level("INFO"):
            settings = TestSettings()

        assert "Successfully evaluated DEFAULT_VAR=default_value by default" in caplog.text
        assert "Nulled NULLABLE_VAR" in caplog.text

    def test_no_annotations_class(self):
        """Test class with no annotated fields"""

        class EmptySettings(AppSettings):
            pass

        settings = EmptySettings()
        # Should initialize without errors
        assert isinstance(settings, EmptySettings)

    def test_mixed_nullable_and_required(self):
        """Test mix of nullable and required fields"""
        os.environ["REQUIRED_VAR"] = "required_value"

        class TestSettings(AppSettings):
            REQUIRED_VAR: str = SettingsField(nullable=False)
            NULLABLE_VAR: str = SettingsField(nullable=True)
            OPTIONAL_VAR: str = SettingsField(default="optional_value")

        settings = TestSettings()
        assert settings.REQUIRED_VAR == "required_value"
        assert settings.NULLABLE_VAR is None
        assert settings.OPTIONAL_VAR == "optional_value"

        # Clean up
        del os.environ["REQUIRED_VAR"]

    def test_property_with_side_effects(self):
        """Test property factory with side effects"""
        call_count = 0

        class TestSettings(AppSettings):
            COMPUTED_VAR: str = SettingsField(factory="computed_prop")

            @property
            def computed_prop(self) -> str:
                nonlocal call_count
                call_count += 1
                return f"computed_{call_count}"

        settings = TestSettings()
        assert settings.COMPUTED_VAR == "computed_1"
        assert call_count == 1

    def test_immutable_assignment_after_init(self):
        """Test that values remain immutable after assignment"""

        class TestSettings(AppSettings):
            STR_VAR: str = SettingsField(default="initial")

        settings = TestSettings()
        initial_value = settings.STR_VAR

        # This should work since we're assigning the same type
        settings.STR_VAR = "new_value"
        assert settings.STR_VAR == "new_value"

        # But this should fail for mutable types
        with pytest.raises(TypeError):
            settings.STR_VAR = ["mutable"]

    def test_complex_factory_scenarios(self):
        """Test complex factory scenarios"""

        def complex_factory():
            return "complex_result"

        class TestSettings(AppSettings):
            COMPLEX_VAR: str = SettingsField(factory=complex_factory)

        settings = TestSettings()
        assert settings.COMPUTED_VAR == "complex_result"

    def test_environment_variable_override(self):
        """Test that environment variables override all other sources"""
        os.environ["OVERRIDE_VAR"] = "from_environment"

        class TestSettings(AppSettings):
            OVERRIDE_VAR: str = SettingsField(default="from_default", factory=lambda: "from_factory")

        settings = TestSettings()
        assert settings.OVERRIDE_VAR == "from_environment"

        # Clean up
        del os.environ["OVERRIDE_VAR"]

    def test_all_allowed_types(self):
        """Test all allowed primitive types"""
        os.environ["STR_VAR"] = "string_value"
        os.environ["INT_VAR"] = "42"
        os.environ["FLOAT_VAR"] = "3.14"
        os.environ["BOOL_VAR"] = "true"
        os.environ["COMPLEX_VAR"] = "1+2j"

        class TestSettings(AppSettings):
            STR_VAR: str = SettingsField(nullable=False)
            INT_VAR: int = SettingsField(nullable=False)
            FLOAT_VAR: float = SettingsField(nullable=False)
            BOOL_VAR: bool = SettingsField(nullable=False)
            COMPLEX_VAR: complex = SettingsField(nullable=False)
            NONE_VAR: None = SettingsField(nullable=True)

        settings = TestSettings()
        assert settings.STR_VAR == "string_value"
        assert settings.INT_VAR == 42
        assert settings.FLOAT_VAR == 3.14
        assert settings.BOOL_VAR is True
        assert settings.COMPLEX_VAR == 1 + 2j
        assert settings.NONE_VAR is None

        # Clean up
        for var in ["STR_VAR", "INT_VAR", "FLOAT_VAR", "BOOL_VAR", "COMPLEX_VAR"]:
            del os.environ[var]

    def test_error_on_invalid_union_type(self):
        """Test error when union contains invalid types"""
        with pytest.raises(TypeError, match="is not allowed for annotations as it is mutable"):

            class InvalidSettings(AppSettings):
                INVALID_UNION: str | list = SettingsField(nullable=True)

    def test_factory_callable_with_args(self):
        """Test factory callable that takes arguments"""

        def factory_with_args(prefix="test"):
            return f"{prefix}_value"

        class TestSettings(AppSettings):
            FACTORY_VAR: str = SettingsField(factory=lambda: factory_with_args("custom"))

        settings = TestSettings()
        assert settings.FACTORY_VAR == "custom_value"

    def test_immutable_setattr_validation(self):
        """Test validation when using setattr"""

        class TestSettings(AppSettings):
            TEST_VAR: str = SettingsField(default="initial")

        settings = TestSettings()

        # This should work
        settings.TEST_VAR = "new_value"
        assert settings.TEST_VAR == "new_value"

        # This should fail
        with pytest.raises(TypeError):
            settings.TEST_VAR = ["mutable_list"]

    def test_class_attribute_access(self):
        """Test accessing class attributes vs instance attributes"""

        class TestSettings(AppSettings):
            CLASS_VAR: str = SettingsField(default="class_value")

        # Access class attribute
        assert TestSettings.CLASS_VAR.default == "class_value"

        # Access instance attribute
        settings = TestSettings()
        assert settings.CLASS_VAR == "class_value"

    def test_no_side_effects_on_reinitialization(self):
        """Test that reinitialization doesn't cause side effects"""
        call_count = 0

        class TestSettings(AppSettings):
            FACTORY_VAR: str = SettingsField(factory="prop_factory")

            @property
            def prop_factory(self):
                nonlocal call_count
                call_count += 1
                return f"call_{call_count}"

        settings1 = TestSettings()
        assert settings1.FACTORY_VAR == "call_1"

        settings2 = TestSettings()
        assert settings2.FACTORY_VAR == "call_2"

        assert call_count == 2

    def test_environment_variable_case_sensitivity(self):
        """Test that environment variables are case-sensitive"""
        os.environ["CASE_SENSITIVE"] = "upper_case_value"
        os.environ["case_sensitive"] = "lower_case_value"

        class TestSettings(AppSettings):
            CASE_SENSITIVE: str = SettingsField(nullable=False)
            case_sensitive: str = SettingsField(nullable=False)

        settings = TestSettings(explicit_format=False)
        assert settings.CASE_SENSITIVE == "upper_case_value"
        assert settings.case_sensitive == "lower_case_value"

        # Clean up
        del os.environ["CASE_SENSITIVE"]
        del os.environ["case_sensitive"]

    def test_numeric_string_conversion(self):
        """Test conversion of numeric strings to appropriate types"""
        os.environ["STRING_NUM"] = "123"

        class TestSettings(AppSettings):
            STRING_NUM: str = SettingsField(nullable=False)
            INT_NUM: int = SettingsField(nullable=False)

        settings = TestSettings()
        assert settings.STRING_NUM == "123"
        assert settings.INT_NUM == 123

        # Clean up
        del os.environ["STRING_NUM"]

    def test_empty_default_factory(self):
        """Test empty/default factory behavior"""

        class TestSettings(AppSettings):
            NO_FACTORY: str = SettingsField(default="default_value")
            EMPTY_FACTORY: str = SettingsField(factory=None, default="default_value")

        settings = TestSettings()
        assert settings.NO_FACTORY == "default_value"
        assert settings.EMPTY_FACTORY == "default_value"

    def test_boolean_string_variations(self):
        """Test various boolean string representations"""
        boolean_true_values = ["yes", "YES", "true", "TRUE", "1", "Y", "y"]
        boolean_false_values = ["no", "NO", "false", "FALSE", "0", "N", "n"]

        for value in boolean_true_values:
            os.environ["BOOL_TEST"] = value

            class TestSettings(AppSettings):
                BOOL_TEST: bool = SettingsField(nullable=False)

            settings = TestSettings()
            assert settings.BOOL_TEST is True
            del os.environ["BOOL_TEST"]

        for value in boolean_false_values:
            os.environ["BOOL_TEST"] = value

            class TestSettings(AppSettings):
                BOOL_TEST: bool = SettingsField(nullable=False)

            settings = TestSettings()
            assert settings.BOOL_TEST is False
            del os.environ["BOOL_TEST"]

    def test_complex_environment_scenario(self):
        """Test complex real-world scenario with multiple field types"""
        os.environ["API_KEY"] = "secret_key_123"
        os.environ["API_TIMEOUT"] = "30"
        os.environ["DEBUG_MODE"] = "true"
        os.environ["MAX_RETRIES"] = "3"

        class ApiSettings(AppSettings):
            API_KEY: str = SettingsField(nullable=False)
            API_TIMEOUT: int = SettingsField(default=10)
            DEBUG_MODE: bool = SettingsField(default=False)
            MAX_RETRIES: int = SettingsField(factory=lambda: 5)
            API_VERSION: str = SettingsField(default="v1")
            CUSTOM_HEADER: str = SettingsField(factory="custom_header_prop")

            @property
            def custom_header_prop(self) -> str:
                return "X-Custom-Header"

        settings = ApiSettings()
        assert settings.API_KEY == "secret_key_123"
        assert settings.API_TIMEOUT == 30  # from env
        assert settings.DEBUG_MODE is True  # from env
        assert settings.MAX_RETRIES == 3  # from env (overrides factory)
        assert settings.API_VERSION == "v1"  # from default
        assert settings.CUSTOM_HEADER == "X-Custom-Header"  # from property

        # Clean up
        for var in ["API_KEY", "API_TIMEOUT", "DEBUG_MODE", "MAX_RETRIES"]:
            del os.environ[var]

    def test_error_handling_in_factory(self):
        """Test error handling in factory functions"""

        def failing_factory():
            raise ValueError("Factory failed")

        class TestSettings(AppSettings):
            FAILING_VAR: str = SettingsField(factory=failing_factory)

        with pytest.raises(ValueError, match="Factory failed"):
            TestSettings()

    def test_immutable_type_validation_in_setattr(self):
        """Test immutable type validation in _set_if_immutable method"""

        class TestSettings(AppSettings):
            TEST_VAR: str = SettingsField(default="initial")

        settings = TestSettings()

        # Valid immutable types should work
        settings.__set_if_immutable("TEST_VAR", "new_string")
        settings.__set_if_immutable("TEST_VAR", 42)
        settings.__set_if_immutable("TEST_VAR", 3.14)
        settings.__set_if_immutable("TEST_VAR", True)
        settings.__set_if_immutable("TEST_VAR", 1 + 2j)
        settings.__set_if_immutable("TEST_VAR", None)

        # Mutable types should fail
        with pytest.raises(TypeError):
            settings.__set_if_immutable("TEST_VAR", ["mutable"])

    def test_attribute_map_processing(self):
        """Test processing of attribute map for property-based factories"""

        class TestSettings(AppSettings):
            PROP_VAR1: str = SettingsField(factory="prop1")
            PROP_VAR2: str = SettingsField(factory="prop2")
            REGULAR_VAR: str = SettingsField(default="regular")

            @property
            def prop1(self) -> str:
                return "property1"

            @property
            def prop2(self) -> str:
                return "property2"

        settings = TestSettings()
        assert settings.PROP_VAR1 == "property1"
        assert settings.PROP_VAR2 == "property2"
        assert settings.REGULAR_VAR == "regular"

    def test_no_environment_no_default_no_factory_no_nullable(self):
        """Test error when no environment, default, factory, and not nullable"""

        class TestSettings(AppSettings):
            MISSING_VAR: str = SettingsField(nullable=False)

        with pytest.raises(ValueError, match="Required field MISSING_VAR was not found in .env"):
            TestSettings()

    def test_all_sources_priority_order(self):
        """Test priority order: environment > factory > default"""
        os.environ["PRIORITY_VAR"] = "from_environment"

        class TestSettings(AppSettings):
            PRIORITY_VAR: str = SettingsField(default="from_default", factory=lambda: "from_factory")

        settings = TestSettings()
        assert settings.PRIORITY_VAR == "from_environment"

        # Clean up
        del os.environ["PRIORITY_VAR"]

        # Now test factory > default
        settings2 = TestSettings()
        assert settings2.PRIORITY_VAR == "from_factory"

    def test_immutable_validation_with_union_types(self):
        """Test immutable validation with union types"""

        class TestSettings(AppSettings):
            UNION_VAR: str | int = SettingsField(default="string_value")

        settings = TestSettings()
        assert settings.UNION_VAR == "string_value"

        # Should be able to set to other immutable types
        settings.UNION_VAR = 42
        assert settings.UNION_VAR == 42

        # But not mutable types
        with pytest.raises(TypeError):
            settings.UNION_VAR = ["mutable"]

    def test_class_inheritance_with_different_settings(self):
        """Test class inheritance with different field configurations"""

        class BaseSettings(AppSettings):
            BASE_VAR: str = SettingsField(default="base_default")

        class DerivedSettings(BaseSettings):
            DERIVED_VAR: str = SettingsField(default="derived_default")

        base_settings = BaseSettings()
        derived_settings = DerivedSettings()

        assert base_settings.BASE_VAR == "base_default"
        assert derived_settings.BASE_VAR == "base_default"
        assert derived_settings.DERIVED_VAR == "derived_default"

    def test_multiple_settings_classes_in_same_process(self):
        """Test multiple different settings classes in same process"""

        class Settings1(AppSettings):
            VAR1: SettingsField[str] = SettingsField(default="settings1")

        class Settings2(AppSettings):
            VAR2: str = SettingsField(default="settings2")

        settings1 = Settings1()
        settings2 = Settings2()

        assert settings1.VAR1 == "settings1"
        assert settings2.VAR2 == "settings2"
