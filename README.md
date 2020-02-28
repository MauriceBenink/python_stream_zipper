[![Downloads](https://img.shields.io/pypi/dm/stream_zipper.svg?color=orange)](https://pypi.python.org/pypi/stream_zipper)
[![Latest Version](https://img.shields.io/pypi/v/stream_zipper.svg)](https://pypi.python.org/pypi/stream_zipper)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/stream_zipper.svg)](https://pypi.python.org/pypi/stream_zipper)
## StreamZipper
This package allows you to collect several streams of files and then turn several streams into one single zipped stream

This can be usefull if you want to serve multiple files from a file server as a single zip file. but you dont to load all files in memory

## installation
```
pip install stream-zipper
```

## Usage

```python
from stream_zipper import ZipStream

zip_stream = ZipStream()
zip_stream.prepare_stream(file_stream_1)
zip_stream.prepare_stream(file_stream_2)
zip_stream.prepare_stream(file_stream_3)
zipped_stream = zip_stream.stream()
```

the first argument is always the stream of the file. all other arguments must be passed as keyword argument (key=val)

in the method prepare_stream you can also specify the following kwargs : 
 - file_name: the name of the file (in the zip)
 - zip_info: Can be used to pass a ZipInfo object. (makes other variables useless)
 - file_size: size of the file, if set to 0 or not set then it will find the file_length for you
 - crc: crc code of the file,  if set to 0 or not set then it will find the crc for you
 
When you provide the crc or file_size it will check the provided value against the data it processed in the stream of that file
If these values do not match then an exception will be thrown.
 
#### Notes
If you do not know the file_size or crc code then that file will have to be streamed twice to get these variables

if you do know the crc code of the files and you know the file_size then it will only call the stream once

it will check per file if it needs to get these values. so it is possible that only some files/streams have the crc and file_size variables. 

```python
from stream_zipper import ZipStream

zip_stream = ZipStream()
zip_stream.prepare_stream(file_stream_1)                                # no crc or file_size. calls the stream 2 times
zip_stream.prepare_stream(file_stream_2, file_size=100)                 # no crc calls the stream 2 times
zip_stream.prepare_stream(file_stream_3, crc="CRC-CODE")                # no file_size calls the stream 2 times
zip_stream.prepare_stream(file_stream_4, file_size=100, crc="CRC-CODE") # both file_size and crc present will call stream 1 time
zipped_stream = zip_stream.stream()                                     # total streams called 7
```
