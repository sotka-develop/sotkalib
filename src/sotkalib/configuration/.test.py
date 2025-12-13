import os

from sotkalib.configuration import AppSettings, SettingsField


class _Test(AppSettings):
    FIELD_1: str = SettingsField()
    FIELD_2: int = SettingsField()
    FIELD_3: float = SettingsField()
    CRINGE: list = SettingsField()


os.environ["FIELD_1"] = "1"
os.environ["FIELD_2"] = "2"
os.environ["FIELD_3"] = "3"
os.environ["CRINGE"] = "[1,2,3]"

print(_Test())
