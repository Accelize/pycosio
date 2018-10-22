# coding=utf-8
"""Test pycosio._core.function_*"""

from io import BytesIO
from platform import platform
from sys import version_info

import pytest


def test_equivalent_to():
    """Tests pycosio._core.functions_core.equivalent_to"""
    from pycosio._core.functions_core import equivalent_to
    from pycosio._core.exceptions import ObjectNotFoundError
    from sys import version_info

    std = 'std'
    cos = 'cos'
    local_path = 'path'
    storage_path = 'http://path'
    dummy_args = (1, 2, 3)
    dummy_kwargs = {'args1': 1, 'args2': 2}
    raises_exception = False

    # Mocks a standard function and is storage equivalent

    def std_function(path, *args, **kwargs):
        """Checks arguments and returns fake result"""
        assert path == local_path
        assert args == dummy_args
        assert kwargs == dummy_kwargs
        return std

    @equivalent_to(std_function)
    def cos_function(path, *args, **kwargs):
        """Checks arguments and returns fake result"""
        assert path == storage_path
        assert args == dummy_args
        assert kwargs == dummy_kwargs
        if raises_exception:
            raise ObjectNotFoundError('Error')
        return cos

    # Tests storage function
    assert cos_function(
        storage_path, *dummy_args, **dummy_kwargs) == cos

    # Tests fall back to standard function
    assert cos_function(
        local_path, *dummy_args, **dummy_kwargs) == std

    # Tests path-like object compatibility
    if (version_info[0] == 3 and version_info[1] >= 6) or version_info[0] > 3:
        import pathlib

        assert cos_function(
            pathlib.Path(local_path), *dummy_args, **dummy_kwargs) == std

    # Tests exception conversion
    raises_exception = True
    with pytest.raises(OSError):
        cos_function(storage_path, *dummy_args, **dummy_kwargs)


def test_equivalent_functions():
    """Tests functions using pycosio._core.functions_core.equivalent_to"""
    from pycosio._core.storage_manager import MOUNTED
    import pycosio._core.functions_os_path as std_os_path
    import pycosio._core.functions_os as std_os
    from pycosio._core.io_system import SystemBase

    # Mock system

    root = 'dummy://'
    relative = 'dir1/dir2/dir3'
    dummy_path = root + relative
    excepted_path = dummy_path
    result = 'result'
    dirs_exists = set()
    dir_created = []
    check_ending_slash = True

    class System(SystemBase):
        """dummy system"""

        @staticmethod
        def relpath(path):
            """Checks arguments and returns fake result"""
            if excepted_path:
                assert path.startswith(excepted_path)
            return path.split(root)[1].strip('/')

        @staticmethod
        def isdir(path=None, *_, **__):
            """Checks arguments and returns fake result"""
            if check_ending_slash:
                assert path[-1] == '/'
            return path in dirs_exists

        @staticmethod
        def _make_dir(*_, **__):
            """Do nothing"""
            dir_created.append(1)

        @staticmethod
        def _remove(*_, **__):
            """Do nothing"""

        @staticmethod
        def _head(*_, **__):
            """Do nothing"""

        @staticmethod
        def _get_roots(*_, **__):
            """Do nothing"""
            return root,

        @staticmethod
        def _get_client(*_, **__):
            """Do nothing"""

        @staticmethod
        def get_client_kwargs(*_, **__):
            """Do nothing"""

    # Tests
    try:
        # Functions that only call "get_instance(path).function(path)

        def basic_function(path):
            """"Checks arguments and returns fake result"""
            assert path == excepted_path
            return result

        for name in ('exists', 'getsize', 'getmtime', 'isfile'):
            system = System()
            MOUNTED[root] = dict(system_cached=system)
            setattr(system, name, basic_function)
            assert getattr(std_os_path, name)(dummy_path) == result

        MOUNTED[root] = dict(system_cached=System())

        # relpath
        assert std_os_path.relpath(dummy_path) == relative
        assert std_os_path.relpath(dummy_path, start='dir1/') == 'dir2/dir3'

        # ismount
        assert std_os_path.ismount(dummy_path) is False
        excepted_path = root
        assert std_os_path.ismount(root) is True

        # isabs
        excepted_path = dummy_path
        assert std_os_path.isabs(dummy_path) is True
        excepted_path = relative
        assert std_os_path.isabs(excepted_path) is False

        # splitdrive
        excepted_path = dummy_path
        assert std_os_path.splitdrive(dummy_path) == (root, relative)
        old_root = root
        old_relative = relative
        relative = 'dir2/dir3'
        root += 'dir1'
        assert std_os_path.splitdrive(dummy_path) == (root, '/' + relative)
        root = old_root
        relative = old_relative

        # samefile
        if version_info[0] == 2 and platform().startswith('Windows'):
            with pytest.raises(NotImplementedError):
                std_os_path.samefile(__file__, __file__)
        else:
            assert std_os_path.samefile(__file__, __file__)

        assert std_os_path.samefile(dummy_path, dummy_path)
        assert not std_os_path.samefile(dummy_path, relative)
        assert not std_os_path.samefile(relative, dummy_path)
        assert std_os_path.samefile(dummy_path, dummy_path + '/')
        assert not std_os_path.samefile(dummy_path, dummy_path + '/dir4')

        root2 = 'dummy2://'
        MOUNTED[root2] = dict(system_cached=System())
        excepted_path = ''
        assert not std_os_path.samefile(root2 + relative, dummy_path)

        # isdir
        dirs_exists.add('dummy://locator/dir1/')
        assert std_os_path.isdir('dummy://locator/dir1/')
        assert std_os_path.isdir('dummy://locator/dir1')

        # makesdir
        assert not dir_created
        std_os.makedirs('dummy://locator/dir1', exist_ok=True)
        assert dir_created

        dir_created = []
        with pytest.raises(OSError):
            std_os.makedirs('dummy://locator/dir1', exist_ok=False)
        assert not dir_created

        # mkdir
        dirs_exists.add('dummy://locator/')
        dirs_exists.add('dummy://')

        with pytest.raises(OSError):
            std_os.mkdir('dummy://locator/dir_not_exists/dir1')
        assert not dir_created

        std_os.mkdir('dummy://locator/dir1/dir2')
        assert dir_created

        dir_created = []
        check_ending_slash = False
        with pytest.raises(OSError):
            std_os.mkdir('dummy://locator/dir1')
        assert not dir_created

        dir_created = []
        std_os.mkdir('dummy://locator2/')
        assert dir_created

    # Clean up
    finally:
        del MOUNTED[root]


def test_cos_open(tmpdir):
    """
    Tests  pycosio._core.functions_io.cos_open and
    pycosio._core.functions_shutil.copy
    """
    from pycosio import copy, copyfile
    from pycosio._core.functions_io import cos_open
    from pycosio._core.storage_manager import MOUNTED
    from pycosio._core.compat import same_file_error
    from pycosio._core.io_system import SystemBase
    from io import TextIOWrapper, UnsupportedOperation
    from os.path import isdir
    import pycosio._core.functions_shutil as pycosio_shutil

    root = 'dummy_read://'
    root2 = 'dummy_read2://'
    cos_path = root + 'file.txt'
    cos_path2 = root2 + 'file.txt'
    content = b'dummy_content'

    # Mock storage
    class DummySystem(SystemBase):
        """dummy system"""

        def __init__(self, *_, **__):
            self.copied = False
            self.raise_on_copy = False

        def copy(self, *_, **__):
            """Chacks called"""
            if self.raise_on_copy:
                raise UnsupportedOperation
            self.copied = True

        @staticmethod
        def relpath(path):
            """Returns fake result"""
            return path

        @staticmethod
        def _make_dir(*_, **__):
            """Do nothing"""

        @staticmethod
        def _remove(*_, **__):
            """Do nothing"""

        @staticmethod
        def _head(*_, **__):
            """Do nothing"""

        @staticmethod
        def _get_roots(*_, **__):
            """Do nothing"""
            return root,

        @staticmethod
        def _get_client(*_, **__):
            """Do nothing"""

        @staticmethod
        def get_client_kwargs(*_, **__):
            """Do nothing"""

    class DummyIO(BytesIO):
        """Dummy IO"""

        def __init__(self, *_, **__):
            BytesIO.__init__(self, content)

    class DummyRawIO(DummyIO):
        """Dummy raw IO"""

    class DummyBufferedIO(DummyIO):
        """Dummy buffered IO"""

    system = DummySystem()
    MOUNTED[root] = dict(
        raw=DummyRawIO, buffered=DummyBufferedIO,
        system_cached=system, storage_parameters={})
    MOUNTED[root2] = dict(
        raw=DummyRawIO, buffered=DummyBufferedIO,
        system_cached=DummySystem(), storage_parameters={})

    def dummy_isdir(path):
        """Returns fake result"""
        if path in ('dummy_read:', 'dummy_read2:'):
            return True
        if 'dummy_read://' in path:
            return False
        return isdir(path)

    pycosio_shutil_isdir = pycosio_shutil.isdir
    pycosio_shutil.isdir = dummy_isdir

    # Tests
    try:
        # open: Buffered Binary
        with cos_open(cos_path, 'rb') as file:
            assert isinstance(file, DummyBufferedIO)
            assert file.read() == content

        # open: Buffered Text
        with cos_open(cos_path, 'rt') as file:
            assert isinstance(file, TextIOWrapper)
            assert file.read() == content.decode()

        # open: Raw Binary
        with cos_open(cos_path, 'rb', buffering=0) as file:
            assert isinstance(file, DummyRawIO)
            assert file.read() == content

        # open: Raw Text
        with cos_open(cos_path, 'rt', buffering=0) as file:
            assert isinstance(file, TextIOWrapper)
            assert file.read() == content.decode()

        # open: Stream Binary
        with cos_open(BytesIO(content), 'rb') as file:
            assert isinstance(file, BytesIO)
            assert file.read() == content

        # open: Stream Text
        with cos_open(BytesIO(content), 'rt') as file:
            assert isinstance(file, TextIOWrapper)
            assert file.read() == content.decode()

        # open: Local file
        local_file = tmpdir.join('file.txt')
        local_file.write(content)
        with cos_open(str(local_file), 'rb') as file:
            assert file.read() == content

        # copy: Local file to local file
        local_dst = tmpdir.join('file_dst.txt')
        assert not local_dst.check()
        copy(str(local_file), str(local_dst))
        assert local_dst.read_binary() == content
        local_dst.remove()

        assert not local_dst.check()
        copyfile(str(local_file), str(local_dst))
        assert local_dst.read_binary() == content
        local_dst.remove()

        # copy: storage file to local file
        assert not local_dst.check()
        copy(cos_path, str(local_dst))
        assert local_dst.read_binary() == content
        local_dst.remove()

        assert not local_dst.check()
        copyfile(cos_path, str(local_dst))
        assert local_dst.read_binary() == content
        local_dst.remove()

        # copy: stream to local file
        assert not local_dst.check()
        copy(BytesIO(content), str(local_dst))
        assert local_dst.read_binary() == content
        local_dst.remove()

        # copy: local file to stream
        stream_dst = BytesIO()
        copy(str(local_file), stream_dst)
        stream_dst.seek(0)
        assert stream_dst.read() == content

        # copy: storage file to local directory
        local_dir = tmpdir.mkdir('sub_dir')
        copy(cos_path, str(local_dir))
        assert local_dir.join(
            cos_path.split('://')[1]).read_binary() == content

        # copy: destination directory not exits
        with pytest.raises(OSError):
            copy(cos_path, str(tmpdir.join('not_exist/file.txt')))

        with pytest.raises(OSError):
            copyfile(cos_path, str(tmpdir.join('not_exist/file.txt')))

        # copy: storage file to storage file
        assert not system.copied
        copy(cos_path, cos_path + '2')
        assert system.copied
        system.copied = False

        assert not system.copied
        copy(cos_path, cos_path2)
        assert not system.copied

        # copy: No special copy function
        system.raise_on_copy = True
        copy(cos_path, cos_path + '2')
        assert not system.copied

        # copy: Buffer size
        DummyIO._buffer_size = 1024
        assert not local_dst.check()
        copy(cos_path, str(local_dst))
        assert local_dst.read_binary() == content

        # copy: same file
        with pytest.raises(same_file_error):
            copy(cos_path, cos_path)

    # Clean up
    finally:
        del MOUNTED[root]
        pycosio_shutil.isdir = pycosio_shutil_isdir


def test_is_storage():
    """Tests pycosio._core.storage_manager.is_storage"""
    from pycosio._core.functions_core import is_storage

    # Remote paths
    assert is_storage('', storage='storage')
    assert is_storage('http://path')

    # Local paths
    assert not is_storage('path')
    assert not is_storage('file://path')
