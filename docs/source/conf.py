import os
import sys

sys.path.insert(0, os.path.abspath('../../src/codi'))

project = 'CoDI'
copyright = '2026, Matthew de Lannoy'
author = 'Matthew de Lannoy'
release = '0.1.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
]

templates_path = ['_templates']
exclude_patterns = []

html_theme = 'sphinx_rtd_theme'
# html_static_path = ['_static']