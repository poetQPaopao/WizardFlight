"""Controller package exports.

Re-export the primary controller class with a conventional name so imports like:

    from .controller import Controller

work from within the game package.
"""

# Expose `Controller` alias for the lowercase implementation class
from .controller import controller as Controller  # noqa: F401
