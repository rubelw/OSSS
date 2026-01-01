def define_env(env):
    """
    mkdocs-macros hook. This is called once at build time.
    """

    @env.macro
    def repo_tree(*args, **kwargs):
        """
        Temporary stub macro so MkDocs stops complaining.
        Replace with real implementation later.
        """
        return "repo_tree macro is wired up (stub)."
