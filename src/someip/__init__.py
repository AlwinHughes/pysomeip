from importlib.metadata import PackageNotFoundError
from importlib.metadata import version

try:
    __version__ = version(__name__)
except PackageNotFoundError:  # pragma: nocover
    # package is not installed
    pass
