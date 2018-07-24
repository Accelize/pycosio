# coding=utf-8
"""Test pycosio.s3"""
from datetime import datetime
import io
import time

import pytest


def test_handle_io_exceptions():
    """Test pycosio.s3._handle_io_exceptions"""
    from pycosio.s3 import _handle_io_exceptions
    from botocore.exceptions import ClientError

    response = {'Error': {'Code': 'ErrorCode', 'Message': 'Error'}}

    # Any error
    with pytest.raises(ClientError):
        with _handle_io_exceptions():
            raise ClientError(response, 'testing')

    # 404 error
    response['Error']['Code'] = '404'
    with pytest.raises(OSError):
        with _handle_io_exceptions():
            raise ClientError(response, 'testing')

    # 403 error
    response['Error']['Code'] = '403'
    with pytest.raises(OSError):
        with _handle_io_exceptions():
            raise ClientError(response, 'testing')


def test_s3_raw_io():
    """Tests pycosio.s3.S3RawIO"""
    from pycosio.s3 import S3RawIO
    from botocore.exceptions import ClientError
    import boto3

    # Initializes some variables
    bucket = 'bucket'
    key_value = 'key'
    client_args = dict(Bucket=bucket, Key=key_value)
    path = '%s/%s' % (bucket, key_value)
    url = 's3://' + path
    put_object_called = []
    size = 100
    m_time = time.time()
    s3object = None

    # Mocks boto3 client

    class Client:
        """Dummy client"""

        def __init__(self, *_, **__):
            """Do nothing"""

        @staticmethod
        def get_object(**kwargs):
            """Mock boto3 get_object
            Check arguments and returns fake value"""
            if raises_exception:
                client_error_response['Error']['Code'] = 'Error'
                raise ClientError(client_error_response, 'Error')

            for key, value in client_args.items():
                assert key in kwargs
                assert kwargs[key] == value

            data_range = kwargs.get('Range')
            if data_range is None:
                # Return full object
                content = one_byte * size

            else:
                # Return object part
                data_range = data_range.split('=')[1]
                start, end = data_range.split('-')
                start = int(start)
                try:
                    end = int(end) + 1
                except ValueError:
                    end = size

                if start >= size:
                    # EOF reached
                    client_error_response['Error']['Code'] = 'InvalidRange'
                    raise ClientError(client_error_response, 'EOF')
                if end > size:
                    end = size
                content = one_byte * (end - start)

            return dict(Body=io.BytesIO(content))

        @staticmethod
        def head_object(**kwargs):
            """Mock boto3 head_object
            Check arguments and returns fake value"""
            assert kwargs == client_args
            return dict(
                ContentLength=size,
                LastModified=datetime.fromtimestamp(m_time))

        @staticmethod
        def put_object(**kwargs):
            """Mock boto3 put_object
            Check arguments and returns fake value"""
            for key, value in client_args.items():
                assert key in kwargs
                assert kwargs[key] == value
            assert len(kwargs['Body']) == len(s3object._write_buffer)
            put_object_called.append(1)

    class Session:
        """Dummy Session"""
        client = Client

        def __init__(self, *_, **__):
            """Do nothing"""

    boto3_client = boto3.client
    boto3_session_session = boto3.session.Session
    boto3.client = Client
    boto3.session.Session = Session

    # Tests
    try:
        # Tests path and URL handling
        s3object = S3RawIO(url)
        assert s3object._client_kwargs == client_args
        assert s3object.name == url

        s3object = S3RawIO(path)
        assert s3object._client_kwargs == client_args
        assert s3object.name == url

        # Tests _get_metadata
        assert s3object.getmtime() == pytest.approx(m_time, 1e-3)
        assert s3object.getsize() == size

        # Mocks get_object
        one_byte = b'0'
        raises_exception = False
        client_error_response = {
            'Error': {'Code': 'Error', 'Message': 'Error'}}

        # Tests _read_all
        assert s3object.readall() == size * one_byte
        assert s3object.tell() == size

        assert s3object.seek(10) == 10
        assert s3object.readall() == (size - 10) * one_byte
        assert s3object.tell() == size

        # Tests _read_range
        assert s3object.seek(0) == 0
        buffer = bytearray(40)
        assert s3object.readinto(buffer) == 40
        assert bytes(buffer) == 40 * one_byte
        assert s3object.tell() == 40

        buffer = bytearray(40)
        assert s3object.readinto(buffer) == 40
        assert bytes(buffer) == 40 * one_byte
        assert s3object.tell() == 80

        buffer = bytearray(40)
        assert s3object.readinto(buffer) == 20
        assert bytes(buffer) == 20 * one_byte + b'\x00' * 20
        assert s3object.tell() == 100

        buffer = bytearray(40)
        assert s3object.readinto(buffer) == 0
        assert bytes(buffer) == b'\x00' * 40
        assert s3object.tell() == 100

        # Tests _read_range don't hide Boto exceptions
        raises_exception = True
        with pytest.raises(ClientError):
            assert s3object.read(10)

        s3object = S3RawIO(url, mode='w')

        # Tests _flush
        assert not put_object_called
        s3object.write(50 * one_byte)
        s3object.flush()
        assert put_object_called == [1]

    # Restore mocked class
    finally:
        boto3.client = boto3_client
        boto3.session.Session = boto3_session_session


def test_s3_buffered_io():
    """Tests pycosio.s3.S3BufferedIO"""
    from pycosio.s3 import S3BufferedIO, _upload_part
    import boto3

    # Mocks client
    one_byte = b'0'
    bucket = 'bucket'
    key_value = 'key'
    client_args = dict(Bucket=bucket, Key=key_value)
    path = '%s/%s' % (bucket, key_value)

    class Client:
        """Dummy client"""

        def __init__(self, *_, **__):
            """Do nothing"""

        @staticmethod
        def create_multipart_upload(**kwargs):
            """Checks arguments and returns fake result"""
            for key, value in client_args.items():
                assert key in kwargs
                assert kwargs[key] == value
            return dict(UploadId=123)

        @staticmethod
        def complete_multipart_upload(**kwargs):
            """Checks arguments and returns fake result"""
            for key, value in client_args.items():
                assert key in kwargs
                assert kwargs[key] == value
            uploaded_parts = kwargs['MultipartUpload']['Parts']
            assert 10 == len(uploaded_parts)
            for index, part in enumerate(uploaded_parts):
                assert part['PartNumber'] == index + 1
                assert part['ETag'] == 456

        @staticmethod
        def upload_part(**kwargs):
            """Checks arguments and returns fake result"""
            assert kwargs['PartNumber'] > 0
            assert kwargs['PartNumber'] <= 10
            assert kwargs['Body'] == one_byte * (
                5 if kwargs['PartNumber'] == 10 else 10)
            assert kwargs['UploadId'] == 123
            for key, value in client_args.items():
                assert key in kwargs
                assert kwargs[key] == value
            return dict(ETag=456)

        @staticmethod
        def put_object(**_):
            """Do nothing"""

        @staticmethod
        def get_object(**_):
            """Do nothing"""

        @staticmethod
        def head_object(**_):
            """Do nothing"""

    class Session:
        """Dummy Session"""
        client = Client

        def __init__(self, *_, **__):
            """Do nothing"""

    boto3_client = boto3.client
    boto3_session_session = boto3.session.Session
    boto3.client = Client
    boto3.session.Session = Session

    # Tests
    try:
        # Write and flush using multipart upload
        s3object = S3BufferedIO(path, mode='w')
        s3object._buffer_size = 10

        s3object.write(one_byte * 95)
        s3object.close()

        # upload_part for ProcessPoolExecutor
        assert _upload_part(
            Body=one_byte * 10, PartNumber=1, UploadId=123,
            **client_args) == dict(ETag=456)

    # Restore mocked class
    finally:
        boto3.client = boto3_client
        boto3.session.Session = boto3_session_session