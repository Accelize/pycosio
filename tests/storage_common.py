# coding=utf-8
"""Test pycosio.storage"""
from os import urandom as _urandom
from time import time as _time
from uuid import uuid4 as _uuid

import pytest as _pytest


class StorageTester:
    """
    Class that contain common set of tests for storage.

    Args:
        system (pycosio._core.io_system.SystemBase instance):
            System to test.
        raw_io (pycosio._core.io_raw.ObjectRawIOBase subclass):
            Raw IO class.
        buffered_io (pycosio._core.io_buffered.ObjectBufferedIOBase subclass):
            Buffered IO class.
        storage_mock (tests.storage_mock.ObjectStorageMock instance):
            Storage mock in use, if any.
    """

    def __init__(self, system, raw_io, buffered_io, storage_mock=None):
        self._system = system
        self._raw_io = raw_io
        self._buffered_io = buffered_io
        self._storage_mock = storage_mock

        # Get storage root
        root = system.roots[0]

        # Defines randomized names for locator and objects
        self.locator = self._get_id()
        self.locator_url = '/'.join((root, self.locator))
        self.base_dir_path = '%s/%s/' % (self.locator, self._get_id())
        self.base_dir_url = '/'.join((root, self.base_dir_path))

        # Run test sequence
        self._objects = set()
        self._to_clean = self._objects.add

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.__del__()

    def __del__(self):
        for obj in list(self._objects) + [self.locator]:
            try:
                self._system.remove(obj, relative=True)
                self._objects.discard(obj)
            except Exception:
                continue

    def test_common(self):
        """
        Common set of tests
        """
        self._test_system_locator()
        self._test_system_objects()
        self._test_raw_io()
        self._test_buffered_io()

        # Only if mocked
        if self._storage_mock is not None:
            self._test_mock_only()

    @staticmethod
    def _get_id():
        """
        Return an unique ID.

        Returns:
            str: id
        """
        return 'pytest_pycosio_%s' % (str(_uuid()).replace('-', ''))

    def _test_raw_io(self):
        """
        Tests raw IO.
        """
        size = 100
        file_path = self.base_dir_path + 'sample_100B.dat'
        self._to_clean(file_path)
        content = _urandom(size)

        # Open file in write mode
        file = self._raw_io(file_path, 'wb')
        try:
            # Test: Write
            file.write(content)

            # Test: tell
            assert file.tell() == size

            # Test: _flush
            file.flush()

        finally:
            file.close()

        # Open file in read mode
        file = self._raw_io(file_path)
        try:
            # Test: _read_all
            assert file.readall() == content
            assert file.tell() == size

            assert file.seek(10) == 10
            assert file.readall() == content[10:]
            assert file.tell() == size

            # Test: _read_range
            assert file.seek(0) == 0
            buffer = bytearray(40)
            assert file.readinto(buffer) == 40
            assert bytes(buffer) == content[:40]
            assert file.tell() == 40

            buffer = bytearray(40)
            assert file.readinto(buffer) == 40
            assert bytes(buffer) == content[40:80]
            assert file.tell() == 80

            buffer = bytearray(40)
            assert file.readinto(buffer) == 20
            assert bytes(buffer) == content[80:] + b'\x00' * 20
            assert file.tell() == size

            buffer = bytearray(40)
            assert file.readinto(buffer) == 0
            assert bytes(buffer) == b'\x00' * 40
            assert file.tell() == size

        finally:
            file.close()

    def _test_buffered_io(self):
        """
        Tests buffered IO.
        """
        # Set buffer size
        minimum_buffer_zize = 16 * 1024
        buffer_size = self._buffered_io.MINIMUM_BUFFER_SIZE
        if buffer_size < minimum_buffer_zize:
            buffer_size = minimum_buffer_zize

        # Define data to write
        file_path = self.base_dir_path + 'buffered_file.dat'
        size = int(4.5 * buffer_size)
        data = _urandom(size)

        # Test: write data
        with self._buffered_io(
                file_path, 'wb', buffer_size=buffer_size) as file:
            file.write(data)

        # Test: Read data
        with self._buffered_io(
                file_path, 'rb', buffer_size=buffer_size) as file:
            assert data == file.read()

    def _test_system_locator(self):
        """
        Test system internals related to locators.
        """
        system = self._system

        # Test: Create locator
        system.make_dir(self.locator_url)

        # Test: Check locator listed
        for name, header in system._list_locators():
            if name == self.locator and isinstance(header, dict):
                break
        else:
            _pytest.fail('Locator "%s" not found' % self.locator)

        # Test: Check locator header
        assert isinstance(system.head(path=self.locator), dict)

        # Test: remove locator
        tmp_locator = self._get_id()
        self._to_clean(tmp_locator)
        system.make_dir(tmp_locator)
        assert tmp_locator in [name for name, _ in system._list_locators()]

        system.remove(tmp_locator)
        assert tmp_locator not in [name for name, _ in system._list_locators()]

    def _test_system_objects(self):
        """
        Test system internals related to objects.
        """
        from pycosio._core.exceptions import ObjectNotFoundError

        system = self._system

        # Write a sample file
        file_name = 'sample_16B.dat'
        file_path = self.base_dir_path + file_name
        self._to_clean(file_path)
        file_url = self.base_dir_url + file_name
        size = 16
        content = _urandom(size)

        with self._raw_io(file_path, mode='w') as file:
            # Write content
            file.write(content)

            # Estimate creation time
            create_time = _time()

        # Test: Check file header
        assert isinstance(system.head(path=file_path), dict)

        # Test: Check file size
        assert system.getsize(file_path) == size

        # Test: Check file modification time
        if system._MTIME_KEYS:
            assert system.getmtime(file_path) == _pytest.approx(create_time, 2)

        # Test: Check file creation time
        if system._CTIME_KEYS:
            assert system.getctime(file_path) == _pytest.approx(create_time, 2)

        # Test: Check path and URL handling
        with self._raw_io(file_path) as file:
            assert file.name == file_path

        with self._raw_io(file_url) as file:
            assert file.name == file_url

        # Write some files
        files = set()
        files.add(file_path)
        for i in range(10):
            path = self.base_dir_path + 'file%d.dat' % i
            files.add(path)
            self._to_clean(path)
            with self._raw_io(path, mode='w') as file:
                file.flush()

        # Test: List objects
        objects = tuple(system.list_objects(self.locator))
        assert files == set(
            '%s/%s' % (self.locator, name) for name, _ in objects)
        for _, header in objects:
            assert isinstance(header, dict)

        # Test: List objects, with limited output
        max_request_entries = 5
        entries = len(tuple(system.list_objects(
            max_request_entries=max_request_entries)))
        assert entries == max_request_entries

        # Test: List objects, no objects found
        with _pytest.raises(ObjectNotFoundError):
            list(system.list_objects(self.base_dir_path + 'dir_not_exists/'))

        # Test: List objects, locator not found
        with _pytest.raises(ObjectNotFoundError):
            list(system.list_objects(self._get_id()))

        # Test: copy
        copy_path = file_path + '.copy'
        self._to_clean(copy_path)
        system.copy(file_path, copy_path)
        assert system.getsize(copy_path) == size

        # Test: Make a directory (With trailing /)
        dir_path0 = self.base_dir_path + 'directory0/'
        system.make_dir(dir_path0)
        self._to_clean(dir_path0)
        assert dir_path0 in self._list_objects_names()

        # Test: Make a directory (Without trailing /)
        dir_path1 = self.base_dir_path + 'directory1'
        system.make_dir(dir_path1)
        dir_path1 += '/'
        self._to_clean(dir_path1)
        assert dir_path1 in self._list_objects_names()

        # Test: Remove file
        assert file_path in self._list_objects_names()
        system.remove(file_path)
        assert file_path not in self._list_objects_names()

    def _test_mock_only(self):
        """
        Tests that can only be performed on mocks
        """
        # Create a file
        file_path = self.base_dir_path + 'mocked.dat'

        self._to_clean(file_path)
        with self._raw_io(file_path, mode='w') as file:
            file.flush()

        # Test: Read not block other exceptions
        with self._storage_mock.raise_server_error():
            with _pytest.raises(self._storage_mock.base_exception):
                self._raw_io(file_path).read(10)

    def _list_objects_names(self):
        """
        List objects names.

        Returns:
            set of str: objects names.
        """
        return set(name for name, _ in self._system.list_objects(''))