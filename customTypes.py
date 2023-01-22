from typing import TypedDict
from collections.abc import Iterable


# custom types

ID = str


class Node(TypedDict):
    """ Type for a node (file or folder) returned by Google Drive API. """
    id: ID
    name: str
    mimeType: str


class File(Node):
    pass


class Folder(TypedDict):
    id: ID
    name: str
    nrFolders: int
    nrFiles: int
    nodes: list[Node]


class CacheEntry(TypedDict):
    time: str
    folder: Folder
