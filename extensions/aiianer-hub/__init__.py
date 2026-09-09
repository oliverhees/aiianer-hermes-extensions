"""AIIANER Marktplatz agent-plugin entry point.

The dashboard and desktop surfaces are registered by their own manifests.
Hermes still requires every directory plugin to expose ``register`` so it can
load the plugin package successfully.
"""


def register(ctx):
    """Load the plugin package without adding agent tools or hooks."""
    del ctx
