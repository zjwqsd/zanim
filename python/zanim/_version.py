from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("zanim")
except PackageNotFoundError:  # direct PYTHONPATH use from an uninstalled source tree
    __version__ = "unknown"
