import os
import zipfile
from io import BytesIO

import pytest
from pympler import classtracker
from pympler.asizeof import asizeof

from stream_zipper.exceptions import (NotFileObject,
                                      NotStreamingBytesTypeError,
                                      WrongFileLengthException)
from stream_zipper.zipstream import (StreamingBytes, StreamZipInfo, ZipStream,
                                     ZipWriteStream, _ReadFromStreamingBytes)


class TestZipStream:

    def stream_file(self, file):
        last_data = "Starting"
        while last_data:
            last_data = file.read(256)
            yield last_data

    def default_testing_zipfile(self, zip_stream):
        with open('zip_file.zip', 'wb') as zip_file:
            for chunk in zip_stream.stream():
                zip_file.write(chunk)

        with pytest.raises(Exception):
            zip_stream.stream()

        open_zip = zipfile.ZipFile('zip_file.zip', 'r')

        assert open_zip.testzip() is None
        for file_name in self.file_names:
            assert file_name in open_zip.namelist()
            file = open_zip.open(file_name)
            assert file.read() == open(os.path.dirname(os.path.realpath(__file__)) + f"/test_files/{file_name}",
                                       'rb').read()
            file.close()

    file_names = ['big_file.pdf', 'Invoice.zip', 'Magic_methods.txt', 'random.csv']

    def test__zip_success_without_all_info(self):
        zip_stream = ZipStream()
        for name in self.file_names:
            file = open(os.path.dirname(os.path.realpath(__file__)) + f"/test_files/{name}", 'rb')
            zip_stream.prepare_stream(self.stream_file(file), file_name=name)
        self.default_testing_zipfile(zip_stream)

    def test__zip_success_while_profiling(self):
        tr = classtracker.ClassTracker()
        for track in (StreamingBytes, StreamZipInfo, ZipStream, ZipWriteStream):
            tr.track_class(track)
        zip_stream = ZipStream()
        tr.create_snapshot()

        memory = tr.stats.snapshots[-1].tracked_total + tr.stats.snapshots[-1].overhead + asizeof(zip_stream)
        for name in self.file_names:
            file = open(os.path.dirname(os.path.realpath(__file__)) + f"/test_files/{name}", 'rb')
            zip_stream.prepare_stream(self.stream_file(file), file_name=name)

        stream_bytes = StreamingBytes()
        for chunk in zip_stream.stream():
            stream_bytes.write(chunk)
        tr.create_snapshot()

        assert tr.stats.snapshots[-1].tracked_total + tr.stats.snapshots[
            -1].overhead - memory + asizeof(zip_stream) < zip_stream.fp.tell() * 0.1

    def test__zip_success_without_all_info_in_stream_info_class(self):
        zip_stream = ZipStream()
        for name in self.file_names:
            file = open(os.path.dirname(os.path.realpath(__file__)) + f"/test_files/{name}", 'rb')
            zip_stream.prepare_stream(self.stream_file(file), zip_info=StreamZipInfo(file_name=name))
        self.default_testing_zipfile(zip_stream)

    def test__zip_success_with_all_info(self):
        zip_stream = ZipStream()
        for name in self.file_names:
            file = open(os.path.dirname(os.path.realpath(__file__)) + f"/test_files/{name}", 'rb')
            file_len = file.seek(0, 2)
            file.seek(0)
            crc = zipfile.crc32(file.read())
            file.seek(0)
            zip_stream.prepare_stream(self.stream_file(file), file_name=name, file_size=file_len, crc=crc)
        self.default_testing_zipfile(zip_stream)

    def test_zip_incorrect_size(self):
        zip_stream = ZipStream()
        name = self.file_names[1]
        file = open(os.path.dirname(os.path.realpath(__file__)) + f"/test_files/{name}", 'rb')
        zip_stream.prepare_stream(self.stream_file(file), file_name=name, file_size=15)

        with pytest.raises(WrongFileLengthException):
            for chunk in zip_stream.stream():
                pass

    def test__give_wrong_class_to__ReadFromStreamingBytes(self):
        with pytest.raises(NotStreamingBytesTypeError):
            _ReadFromStreamingBytes(BytesIO)

    def test__extended_class_to__ReadFromStreamingBytes(self):
        class ReadFromStreamingExtended(StreamingBytes):
            pass

        _ReadFromStreamingBytes(ReadFromStreamingExtended())
        assert True

    def test__incorrect_class_for_streaming_bytes(self):
        StreamingBytes._io_writer = object
        with pytest.raises(NotFileObject):
            StreamingBytes()
