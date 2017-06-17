import errno
import os


def makedirs(dir_path):
    '''
    Create a directory and all the intermediate parent directories.

    The behaviour is like `os.makedirs` but doesn't raise an exception if the
    directory already exists.
    This is the same os `os.makedirs(..., exist_ok=True)`, but `exist_ok` was
    added only in Python 3.2.
    '''
    try:
        os.makedirs(dir_path)
    except OSError as exc:
        if exc.errno != errno.EEXIST or not os.path.isdir(dir_path):
            raise
