"""This module serves as a basis for your project if you use NiceGUI.

The project assumes that your "main_ng" entrypoint is the function run() of this file
(see pyproject.toml scripts)
"""

import numpy as np
from nicegui import ui

from pokedex.my_module import typed_function


def run(reload: bool = False):
    """This is the main function that gets run"""
    ui.label(f"Hello world {typed_function(np.zeros(10), '')}")
    ui.slider(min=0, max=100)
    ui.run(reload=reload)


if __name__ in {"__main__", "__mp_main__"}:
    run(True)
