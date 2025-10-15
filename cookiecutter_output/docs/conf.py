# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys

sys.path.insert(0, os.path.abspath(".."))

# -- Project information -----------------------------------------------------
project = "Pokedex"
author = "Raul Fonseca Poca, Juan Diego Zuniga Vargas"
copyright = "2025, Raul Fonseca Poca, Juan Diego Zuniga Vargas"

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "pydata_sphinx_theme"
html_logo = "_static/logo_supop.jpg"

html_theme_options = {
    "navbar_align": "left",
    "logo": {
        "text": "Pokedex documentation",
    },
    "external_links": [
        {
            "url": "https://www.institutoptique.fr/",
            "name": "SupOptique",
        }
    ],
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/raulfonsecapoca/Final-Project",
            "icon": "fa-brands fa-github",
            "type": "fontawesome",
        },
    ],
}


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx.ext.mathjax",
    "myst_parser",
    "nbsphinx",
    "sphinx_copybutton",
    "sphinx_favicon",
    "sphinxarg.ext",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]
autodoc_typehints = "signature"
autoclass_content = "both"
autodoc_typehints_format = "short"
python_use_unqualified_type_names = True
nbsphinx_allow_errors = True
nbsphinx_execute = "auto"
add_module_names = False
copybutton_prompt_text = r">>> |\.\.\. |\$ |In \[\d*\]: | {2,5}\.\.\.: | {5,8}: "
copybutton_prompt_is_regexp = True
# copybutton_exclude = ".linenos, .gp, .go"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
}
