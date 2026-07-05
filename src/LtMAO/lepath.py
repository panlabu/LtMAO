import os, os.path

from operator import methodcaller
force_posix = methodcaller('replace', '\\', '/')

from posixpath import (
    join as join, 
    relpath as rel,
    getsize as getsize,
    exists as exists,
    expanduser as expanduser,
    split as split
)

def abs(path):
    return force_posix(os.path.abspath(path))

def prefix(prefix, path):
    dirname, basename = split(path)
    return join(dirname, prefix + basename)

def ensure_ext(path, ext):
    return path if path.endswith(ext) else path + ext

def ext(path, old, new):
    return path.removesuffix(old) + new

def walk(path, filter_func=None, topdown=True):
    return [
        force_posix(join(root, file))
        for root, dirs, files in os.walk(path, topdown)
        for file in files
        if filter_func is None or filter_func(file)
    ]
