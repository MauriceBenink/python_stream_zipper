import io
from itertools import tee
from zipfile import ZipFile, ZipInfo, _ZipWriteFile

from _io import _IOBase

from .exceptions import (InvalidUseOfStream, NotFileObject,
                         NotStreamingBytesTypeError, WrongFileLengthException)


class _ReadFromStreamingBytes:
    """
    Class to temporarly disable instantly throwing away the data it writes
    """

    def __init__(self, my_bytes_instance):
        if not isinstance(my_bytes_instance, StreamingBytes):
            raise NotStreamingBytesTypeError("my_bytes_instance is not instance of StreamingBytes")
        self.mem_bytes = my_bytes_instance

    def __enter__(self):
        """
        Prepare class when it gets used in a "when"
        :return:
        """
        self.mem_bytes.clean_memory()
        self.mem_bytes.instantly_dump_memory_after_write = False
        return self

    def read(self):
        """
        return the data that got collected so far and then wipe all data in memory
        :return:
        """
        self.mem_bytes.seek(0)
        data = self.mem_bytes.read()
        self.mem_bytes.clean_memory()
        return data

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def close(self):
        """
        Set variables back to delete on writing mode and wipe all data in memory
        :return:
        """
        self.mem_bytes.instantly_dump_memory_after_write = True
        self.mem_bytes.clean_memory()


class StreamingBytes:
    """
    A writer that clears everything from itself directly after writing, while instantly_dump_memory_after_write = True
    """

    _my_tell = 0
    _io_writer = io.BytesIO

    def __init__(self):
        if _IOBase not in self._io_writer.__mro__:
            raise NotFileObject(f"Make sure that {self._io_writer} is file object")
        self._in_memory_writer = self._io_writer()
        self.instantly_dump_memory_after_write = True

    def write(self, data):
        """
        count the data that gets passed, pass it on to an underlying file like object and then remove all the data
        :param data:
        :return:
        """
        self._my_tell += len(data)
        self._in_memory_writer.write(data)
        if self.instantly_dump_memory_after_write:
            self.clean_memory()

    def tell(self):
        """
        Returns the amount of bytes that have passed trough the write function
        :return:
        """
        return self._my_tell

    def collect_write_input(self):
        """
        Function which can be used with the "with" allowing you to read data that gets written to this file like object
        After calling the read memory will be cleared. on exiting the with memory will be cleared
        :return:
        """
        return _ReadFromStreamingBytes(self)

    def clean_memory(self):
        """
        Fully removes all bytes it had in memory
        :return:
        """
        self._in_memory_writer.truncate(0)
        self._in_memory_writer.seek(0)
        self._in_memory_writer.close()
        del self._in_memory_writer
        self._in_memory_writer = self._io_writer()

    def __getattr__(self, item):
        return getattr(self._in_memory_writer, item)


class ZipWriteStream(_ZipWriteFile):
    """
    Class that controls the creating of a part of the zipfile stream using the file stream
    """

    def stream(self):
        """
        Function that streams current stream_generator and zip_info to a zipfile stream
        :return:
        """
        self._fileobj.write(self._zinfo.FileHeader())

        wrote_chunks_in_io = self._zinfo.CRC == 0 or self._zinfo.file_size == 0 or self._zinfo.compress_size == 0
        if wrote_chunks_in_io:
            self._get_missing_zip_info_data()

        yield self._zinfo.FileHeader()
        for chunk in self.stream_generator:
            if not wrote_chunks_in_io:
                self.write(chunk)
            yield chunk

    def _get_missing_zip_info_data(self):
        """
        Adds crc , file_length and compress_size to the info object, these variables are necessary to properly
        open the zip
        :return:
        """
        self.stream_generator, stream_data = tee(self.stream_generator)
        with ZipWriteStream(self._zipfile, self._zinfo, self._zip64) as writing:
            for chunk in stream_data:
                writing.write(chunk)

        self._file_size = self._zinfo.file_size
        self._crc = self._zinfo.CRC

    def __init__(self, zf, zinfo, zip64, stream_generator=None):
        self.stream_generator = stream_generator
        super().__init__(zf, zinfo, zip64)

    def close(self):
        """
        Set the variables of the info object with the info it got from the data that passed trough
        :return:
        """
        self._zinfo.compress_size = self._file_size
        self._zinfo.file_size = self._file_size
        self._zinfo.CRC = self._crc

        # Parent class tries to write to the file_obj, this will break the zipfile offset,
        # to prevent this a call is made  directly to the GrandParent skipping Parent his close
        super(self.__class__.__mro__[1], self).close()


class StreamZipInfo(ZipInfo):
    """
    ZipInfo to make sure all variables are properly initiated.
    """

    def __init__(self, starting_offset=0, *, file_name="NoName", date_time=(1980, 1, 1, 0, 0, 0), file_size=0, CRC=0):
        """
        Normally zipfile.ZipFile handles setting these variables, however these methods which handle this cannot be
        used for the zipfile streaming case
        :param starting_offset:
        :param file_name:
        :param date_time:
        :param file_size:
        :param CRC:
        """
        super().__init__(file_name, date_time)

        self.compress_size = self.file_size = file_size
        self.CRC = CRC
        self.external_attr = 0o600 << 16
        self.header_offset = starting_offset


class ZipStream(ZipFile):
    """
    Class you approach for zipping a file stream while returning parts of a zipfile stream
    """

    def __init__(self):
        """
        Initialization with an file like objects that forgets all data directly after calling write function
        """
        super().__init__(StreamingBytes(), mode='w', compression=0)
        self._prepare_collection = []

    def prepare_stream(self, stream_generator, *, file_name=None, zip_info=None, file_size=0, crc=0):
        """
        give the data which should be processed into a zipfile stream
        :param stream_generator: generator
        :param file_name:
        :param zip_info:
        :param file_size:
        :param crc:
        :return:
        """
        self._prepare_collection += [dict(
            stream_generator=stream_generator, file_name=file_name, zip_info=zip_info, file_size=file_size, crc=crc
        )]

    def _stream_generator(self):
        """
        method that creates the stream generator
        :return:
        """
        for prep in self._prepare_collection:
            yield from self.stream_file_stream(**prep)
        del self._prepare_collection
        self._prepare_collection = []
        yield self.closing_record()

    def stream(self):
        """
        After preparing the stream allows you to create a stream of the prepared data
        :return:
        """
        if len(self._prepare_collection) == 0:
            raise InvalidUseOfStream("Use prepare_stream before calling the function")
        # return is necessary, if done with yield it has to be called before it will raise an exception
        return self._stream_generator()

    def _stream_while_zipping_file_stream(self, zip_info, stream_generator):
        """
        Method that adds file to the zip_file / zip_info information list and returns the stream for the zip
        of that file
        :param zip_info:
        :param stream_generator: generator
        :return:
        """
        zipping_stream = ZipWriteStream(self, zip_info, False, stream_generator).stream()

        self.filelist.append(zip_info)
        self.NameToInfo[zip_info.filename] = zip_info.filename

        return zipping_stream

    def stream_file_stream(self, stream_generator, *, file_name=None, zip_info=None, file_size=0, crc=0):
        """
        method that processes the data so it always has a ZipStreamInfo object for the next method
        :param stream_generator: generator
        :param file_name:
        :param zip_info:
        :param file_size:
        :param crc:
        :return: generator
        """
        if zip_info is None:
            file_name = file_name or "Unnamed file: {}".format(len(self.filelist))
            info = StreamZipInfo(self.fp.tell(), file_name=file_name, file_size=file_size, CRC=crc)
        else:
            info = zip_info
            info.header_offset = self.fp.tell()
        self._writecheck(info)

        yield from self._stream_while_zipping_file_stream(info, stream_generator)

        if file_size != info.file_size and file_size != 0:
            raise WrongFileLengthException("Incorrect file size")

    def closing_record(self):
        """
        finalize any streaming zipfile by yielding this function to properly close the zipfile
        :return: bytes
        """
        self.start_dir = self.fp.tell()
        with self.fp.collect_write_input() as read_from_me:
            self._write_end_record()
            return read_from_me.read()

    def close(self):
        """
        Prevent ZipFile class from closing with his own method since this writes data to the file like objects
        breaking the zipfile
        :return:
        """
        fp = self.fp
        self.fp = None
        self._fpclose(fp)
