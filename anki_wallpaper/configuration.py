import os
import re
from contextlib import contextmanager
from dataclasses import dataclass

import aqt
import aqt.browser.previewer
import aqt.deckbrowser
import aqt.editor
import aqt.theme
import aqt.webview
from aqt.utils import showWarning


# configuration keys
FOLDER_WITH_WALLPAPERS = "folder_with_wallpapers"
ENABLED_FOR = "enabled_for"
LIGHT_WALLPAPER_INDEX = "light_wallpaper_index"
DARK_WALLPAPER_INDEX = "dark_wallpaper_index"

# enabled_for tags
MAIN_WINDOW = "main_window"
ADD_CARDS = "add_cards"
EDIT_CURRENT = "edit_current"
EDIT = "edit"
PREVIEWER = "previewer"


tag_to_dialog_class_name = {
    ADD_CARDS: "AddCards",
    EDIT_CURRENT: "EditCurrent",
    EDIT: "Edit",
}


def is_dark_mode():
    return aqt.theme.theme_manager.night_mode


def read_config():
    return aqt.mw.addonManager.getConfig(__name__)

def write_config(data):
    aqt.mw.addonManager.writeConfig(__name__, data)

@contextmanager
def editing_config():
    data = read_config()
    yield data
    write_config(data)


def run_on_configuration_change(function):
    aqt.mw.addonManager.setConfigUpdatedAction(__name__, lambda *_: function())


########################################################################################


@dataclass
class IsEnabled:
    for_main_window: bool
    for_previewer: bool
    for_dialog_class_names: "list[str]"

    def for_dialog(self, class_name):
        return class_name in self.for_dialog_class_names

    @classmethod
    def from_data(cls, data):
        result = cls(False, False, [])

        enabled_for_tags = data[ENABLED_FOR]

        result.for_main_window = MAIN_WINDOW in enabled_for_tags
        result.for_previewer = PREVIEWER in enabled_for_tags

        for tag in [ADD_CARDS, EDIT_CURRENT, EDIT]:
            if tag in enabled_for_tags:
                result.for_dialog_class_names.append(tag_to_dialog_class_name[tag])

        return result


########################################################################################


@dataclass
class Wallpaper:
    url: str
    position: str
    dark: bool

    @classmethod
    def from_file_path(cls, file_path):
        file_name = os.path.basename(file_path)
        file_name_without_extension = file_name.rsplit(".", 1)[0]
        file_name_parts = re.split(r"[-_. ]", file_name_without_extension)

        url = file_path.replace("\\", "/")

        positions = {"center", "left", "right", "top", "bottom"} & {*file_name_parts}
        position = list(positions)[0] if positions else "center"

        dark = "dark" in file_name_parts

        return cls(url, position, dark)

Wallpaper.missing = Wallpaper("", "center", False)


@dataclass
class Wallpapers:
    light: "list[Wallpaper]"
    dark: "list[Wallpaper]"
    errors: "list[str]"

    @classmethod
    def from_data(cls, data):
        result = cls([], [], [])

        folder_path = data[FOLDER_WITH_WALLPAPERS]

        try:
            file_names = os.listdir(folder_path)
        except Exception as e:
            result.errors.append(f"Error opening wallpaper folder '{folder_path}': {e}")
        else:
            file_paths = [os.path.join(folder_path, file_name) for file_name in file_names]
            files_paths_to_validate_via_opening = \
                file_paths if len(file_paths) < 10 else file_paths[:5] + file_paths[5:]

            for file_path in file_paths:
                if '"' in file_path:
                    result.errors.append(f"File path contains quotes: '{file_path}'")

                if file_path in files_paths_to_validate_via_opening:
                    try:
                        with open(file_path, "r"):
                            pass
                    except Exception as e:
                        result.errors.append(f"Error opening file '{file_path}': {e}")

                wallpaper = Wallpaper.from_file_path(file_path)
                (result.dark if wallpaper.dark else result.light).append(wallpaper)

            if not result.light:
                result.errors.append(
                    f"Folder does not contain light wallpapers: '{folder_path}'")
            if not result.dark:
                result.errors.append(
                    f"Folder does not contain dark wallpapers: '{folder_path}'")

        return result


def change_folder_with_wallpapers_setting_to_sample_folder():
    import os.path
    this_file_folder, _file = os.path.split(__file__)
    sample_wallpapers_folder = os.path.join(this_file_folder, "sample_wallpapers")

    with editing_config() as data:
        data[FOLDER_WITH_WALLPAPERS] = sample_wallpapers_folder


########################################################################################


@dataclass
class Indexes:
    light: int
    dark: int

    @classmethod
    def from_data(cls, data):
        return cls(data[LIGHT_WALLPAPER_INDEX], data[DARK_WALLPAPER_INDEX])


########################################################################################


def show_warning_about_wallpaper_folder_config_errors(errors):
    errors_str = '\n'.join(errors)

    showWarning(
        title="Wallpaper",
        text="Hello, this is the Wallpaper add-on! "
             "I have some issues with the wallpaper folder setting. "
             "Things will probably break. Sorry! "
             "(It's probably your fault, though.)"
             "\n\n"
             f"{errors_str}",
        help=None,  # noqa
    )


class Config:
    def __init__(self):
        self.is_enabled = IsEnabled(False, False, [])
        self.wallpapers = Wallpapers([], [], [])
        self.indexes = Indexes(0, 0)

    def load(self):
        data = read_config()

        if data[FOLDER_WITH_WALLPAPERS] == "change_me":
            change_folder_with_wallpapers_setting_to_sample_folder()
            data = read_config()

        self.is_enabled = IsEnabled.from_data(data)
        self.wallpapers = Wallpapers.from_data(data)
        self.indexes = Indexes.from_data(data)

        if self.wallpapers.errors:
            show_warning_about_wallpaper_folder_config_errors(self.wallpapers.errors)

    def next_wallpaper(self):
        with editing_config() as data:
            data[DARK_WALLPAPER_INDEX if is_dark_mode() else LIGHT_WALLPAPER_INDEX] += 1
        self.indexes = Indexes.from_data(data)

    @property
    def current_wallpaper(self):
        wallpapers = self.wallpapers.dark if is_dark_mode() else self.wallpapers.light
        index = self.indexes.dark if is_dark_mode() else self.indexes.light
        return wallpapers[index % len(wallpapers)] if wallpapers else Wallpaper.missing
