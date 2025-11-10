"""JN context for passing state between commands."""

import click


class JNContext:
    def __init__(self):
        self.home = None
        self.plugin_dir = None
        self.cache_path = None


pass_context = click.make_pass_decorator(JNContext, ensure=True)
