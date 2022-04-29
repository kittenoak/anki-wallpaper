import aqt
import aqt.browser.previewer
import aqt.deckbrowser
import aqt.editor
import aqt.theme
import aqt.webview
from aqt import gui_hooks
from aqt.qt import Qt, QColor, QAction

from .anki_tools import get_dialog_instance_or_none
from .config import Config, on_configuration_changed_run
from .tools import append_to_method, replace_method, exception_to_string


anki_version = tuple(int(segment) for segment in aqt.appVersion.split("."))


def set_main_window_wallpaper():
    aqt.mw.setStyleSheet(rf"""
        QMainWindow {{
            background-image: url("{config.current_wallpaper.url}"); 
            background-position: {config.current_wallpaper.position};
        }}
        
        QMenuBar {{ background: transparent; }}
        #centralwidget {{  background: transparent; }}
    """)


def set_dialog_wallpaper(dialog):
    class_name = dialog.__class__.__name__
    dialog.setStyleSheet(rf"""
        {class_name} {{
            background-image: url("{config.current_wallpaper.url}"); 
            background-position: {config.current_wallpaper.position};
        }}
    """)


def set_previewer_wallpaper(previewer):
    previewer.setStyleSheet(rf"""
        QDialog {{
            background-image: url("{config.current_wallpaper.url}"); 
            background-position: {config.current_wallpaper.position};
        }}
    """)


# todo also change wallpaper for the previewer?
#   previewer is not registered with the dialog manager
#   so we can't just grab the instance as easily as with the other dialogs
def set_wallpapers_now():
    set_main_window_wallpaper()

    for dialog_tag in config.enabled_for.dialog_tags:
        if dialog := get_dialog_instance_or_none(dialog_tag):
            set_dialog_wallpaper(dialog)


############################################################################## web views


# Anki misuses `QColor` in python, and also in css, by calling its `name()`.
# The problem is, the return value of `name()` does not contain the alpha.
class MonstrousTransparentColor(QColor):
    def __init__(self):
        super().__init__()
        self.setAlpha(0)

    def name(self, *args, **kwargs):
        return "transparent"

monstrous_transparent_color = MonstrousTransparentColor()


@replace_method(aqt.editor.EditorWebView, "__init__")
def editor_webview_init(self, parent, editor):
    if editor.parentWindow.__class__.__name__ in config.enabled_for.dialog_class_names:
        self._transparent = True
    editor_webview_init.original_method(self, parent, editor)


@replace_method(aqt.webview.AnkiWebView, "get_window_bg_color")
def webview_get_window_bg_color(self, *args, **kwargs):
    transparent = getattr(self, "_transparent", False) or self.title in config.enabled_for.webview_titles

    if transparent:
        self.page().setBackgroundColor(Qt.GlobalColor.transparent)
        return monstrous_transparent_color
    else:
        return webview_get_window_bg_color.original_method(self, *args, **kwargs)


############################################################################## previewer


@append_to_method(aqt.browser.previewer.Previewer, "__init__")
def previewer_init(self, *_args, **_kwargs):
    set_previewer_wallpaper(self)


@append_to_method(aqt.browser.previewer.Previewer, "show")
def previewer_show(self, *_args, **_kwargs):
    self._web.setStyleSheet(r"""
        #_web { background: transparent }
    """)

############################################################# add cards and edit current


@append_to_method(aqt.addcards.AddCards, "__init__")
def add_cards_init(self, *_args, **_kwargs):
    self.form.fieldsArea.setStyleSheet(r"""
       #fieldsArea { background: transparent }
    """)


@append_to_method(aqt.editor.Editor, "setupWeb")
def editor_init(self, *_args, **_kwargs):
    dialog = self.parentWindow

    if dialog.__class__.__name__ in config.enabled_for.dialog_class_names:
        set_dialog_wallpaper(dialog)

        self.widget.setStyleSheet(r"""
            EditorWebView { background: transparent }
        """)


############################################################# web view css manipulations


# * `current`: the class for the currently selected deck; solid color by default
# * `zero-count`:  the class for zeros in the due cards table; barely visible by default
# * `sticky-container`: the class for a div behind the button bars and the tag bar
#    in the Editor. in night mode, these seem to have background color
# * `container-fluid`: the same but in Anki 2.1.49.
def webview_will_set_content(web_content: aqt.webview.WebContent, context):
    if isinstance(context, aqt.deckbrowser.DeckBrowser):  # noqa
        web_content.head += """<style>
            .current { background-color: #fff3 !important }
            .zero-count { color: #0005 !important }
            .night-mode .zero-count { color: #fff5 !important }
        </style>"""

    if isinstance(context, aqt.editor.Editor):
        if context.parentWindow.__class__.__name__ in config.enabled_for.dialog_class_names:
            web_content.head += """<style>
                body {background: none !important }
                .sticky-container, .container-fluid { background: none !important }
            </style>"""


########################################################################################


def setup_next_wallpaper_menu():
    def next_wallpaper():
        config.next_wallpaper()
        set_wallpapers_now()

    menu_next_wallpaper = QAction("Next wallpaper", aqt.mw, shortcut="Ctrl+Shift+W")  # noqa
    menu_next_wallpaper.triggered.connect(next_wallpaper)  # noqa
    menu_next_wallpaper.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)

    aqt.mw.form.menuTools.addSeparator()
    aqt.mw.form.menuTools.addAction(menu_next_wallpaper)


config = Config()
config.load()


def on_configuration_changed(*_args):
    config.load()
    set_wallpapers_now()

on_configuration_changed_run(on_configuration_changed)


if anki_version >= (2, 1, 50):
    gui_hooks.theme_did_change.append(set_wallpapers_now)

gui_hooks.webview_will_set_content.append(webview_will_set_content)


setup_next_wallpaper_menu()
set_wallpapers_now()
