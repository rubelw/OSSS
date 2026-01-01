from mkdocs_macros.plugin import MacrosPlugin

def define_env(env: MacrosPlugin):
    """
    Hook called by mkdocs-macros.

    This defines a dummy `repo_tree` macro so that index.md can call it
    without blowing up. You can later expand this to actually walk
    the filesystem if you want.
    """

    @env.macro
    def repo_tree(*args, **kwargs):
        # For now, return an empty list so loops over repo_tree() are harmless.
        # You can later implement real logic and return e.g. a list of dicts.
        return []
