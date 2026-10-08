"""Spec to Inspector: a customer's PCB specification becomes a visual inspector.

The inspector learns what a good board looks like from good boards, measures
what it finds in millimetres, and cites the specification's clause behind
every reject.
"""

from importlib.metadata import version

__version__ = version("spec-to-inspector")
