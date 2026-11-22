"""searx.version_frozen — généré par prepare_src.py (build sans git : Android).

searx/version.py exécute `git show` au démarrage ; sans binaire git, l'import
échoue (FileNotFoundError) et le thread SearXNG meurt. Ce module figé est le
mécanisme amont qui court-circuite les appels git.
"""
VERSION_STRING = "1.0.0+a30b2d4"
VERSION_TAG = "1.0.0+a30b2d4"
DOCKER_TAG = "1.0.0-a30b2d4"
GIT_URL = "https://github.com/searxng/searxng"
GIT_BRANCH = "a30b2d47492ab46ae82ce25ee62a31626565cf67"
