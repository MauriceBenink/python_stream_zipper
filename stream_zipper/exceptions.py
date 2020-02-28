class NotStreamingBytesTypeError(TypeError):
    pass


class NotFileObject(TypeError):
    pass


class InvalidUseOfStream(AssertionError):
    pass


class WrongFileLengthException(Exception):
    status_code = 409
    code = 'CORRUPTED_FILE'
    message = "The expected file length was incorrect"
