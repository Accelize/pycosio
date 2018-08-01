# coding=utf-8
"""Cloud storage abstract IO Base class"""
from io import IOBase, UnsupportedOperation
from threading import Lock


class ObjectIOBase(IOBase):
    """
    Base class to handle cloud object.

    Args:
        name (str): URL or path to the file which will be opened.
        mode (str): The mode can be 'r', 'w', 'a'
            for reading (default), writing or appending
    """

    def __init__(self, name, mode='r'):
        IOBase.__init__(self)

        self._name = name
        self._mode = mode

        # Cache for values
        self._cache = {}

        # Thread safe stream position
        self._seek = 0
        self._seek_lock = Lock()

        # Select supported features based on mode
        self._writable = False
        self._readable = False
        self._seekable = True

        if 'w' in mode or 'a' in mode:
            self._writable = True

        elif 'r' in mode:
            self._readable = True

        else:
            raise ValueError('Invalid mode "%s"' % mode)

    @staticmethod
    def _memoize(method):
        """"""
        method_name = method.__name__

        def patched(self, *args, **kwargs):
            """Patched method"""
            try:
                return self._cache[method_name]
            except KeyError:
                result = self._cache[method_name] = method(
                    self, *args, **kwargs)
                return result

        return patched

    @property
    def mode(self):
        """
        The mode.

        Returns:
            str: Mode.
        """
        return self._mode

    @property
    def name(self):
        """
        The file name.

        Returns:
            str: Name.
        """
        return self._name

    def readable(self):
        """
        Return True if the stream can be read from.
        If False, read() will raise OSError.

        Returns:
            bool: Supports reading.
        """
        return self._readable

    def seekable(self):
        """
        Return True if the stream supports random access.
        If False, seek(), tell() and truncate() will raise OSError.

        Returns:
            bool: Supports random access.
        """
        return self._seekable

    def tell(self):
        """Return the current stream position.

        Returns:
            int: Stream position."""
        if not self._seekable:
            raise UnsupportedOperation('tell')

        with self._seek_lock:
            return self._seek

    def writable(self):
        """
        Return True if the stream supports writing.
        If False, write() and truncate() will raise OSError.

        Returns:
            bool: Supports writing.
        """
        return self._writable