def define_env(env):
    """
    mkdocs-macros hook. Called once at build time.
    """

    @env.macro
    def repo_tree(*args, **kwargs):
        """
        Stub implementation so index.md can call {{ repo_tree() }}
        without blowing up. Replace with real logic later.
        """
        return "repo_tree macro is wired up (stub)."
