from __future__ import print_function
import os
import json
import datetime

from customTypes import *
from googleDriveApi import GoogleDriveApi


class FileSystem:
    """
    Providesw basic methods to interact with the filesystem.
    The actual files are on Google Drive.
    This class provides a caching system to avoid repeated long query times
    or hitting the request limit.
    """
    
    __env: env
    __googleDriveApi: GoogleDriveApi

    __cache: dict[ID, CacheEntry]

    def __writeBackCache(self):
        """Write back cache."""
        with open(self.__env['CACHE_FILE'], 'w') as f:
            json.dump(self.__cache, f, indent=4, check_circular=False)

    def getFolder(self, folderId: ID, forceUpdate: bool = False) -> Folder:
        """
        Get a folder from ID. No full files are downloaded.

        Implementation note:
        Results are cached from last time. If the cache misses or it is too old,
        the data is fetched from Google Drive API.

        If the cache misses, this gets the folder attributes as well as all direct
        children and their attributes from Google and caches them. This allows us
        to compute folder statistics.

        @param folderId: Google folder ID.
        @param forceUpdate: Force update cache.
        """

        # check cache
        item = self.__cache.get(folderId, None)
        # no force update, no miss, not stale
        if not forceUpdate and item is not None and datetime.datetime.utcnow() - datetime.datetime.fromisoformat(item['time']) < datetime.timedelta(days=30):
            # cache hit
            folder = self.__cache[folderId]['folder']
            print("  cache: hit  '{0}'".format(folder['name']))
            return folder
        else:
            # cache miss, stale value or forced update
            print("  cache: miss '{0}'".format(folderId), end='')
            name = self.__googleDriveApi.googleGetNode(folderId)['name']
            print(f" -> '{name}'")
            nodes = self.__googleDriveApi.googleGetFolderContent(folderId)
            folder = Folder(
                id=folderId,
                name=name,
                nrFolders=sum(
                    1 for node in nodes if node['mimeType'] == GoogleDriveApi.MIME_TYPE_FOLDER),
                nrFiles=sum(
                    1 for node in nodes if node['mimeType'] != GoogleDriveApi.MIME_TYPE_FOLDER),
                nodes=nodes
            )
            self.__cache[folderId] = CacheEntry(
                time=datetime.datetime.utcnow().isoformat(timespec='seconds'),
                folder=folder
            )
            self.__writeBackCache()
            return folder

    @staticmethod
    def filterNodes(nodes: list[Node], folders: bool = True, files: bool = True) -> list[Node]:
        """
        Returns files and/or folders from given folder.

        @param nodes: List of nodes.
        @param files: Include files.
        @param folders: Include folders.
        """

        # filter result
        if folders and not files:
            return [node for node in nodes if node['mimeType'] == GoogleDriveApi.MIME_TYPE_FOLDER]
        elif files and not folders:
            return [node for node in nodes if node['mimeType'] != GoogleDriveApi.MIME_TYPE_FOLDER]
        elif files and folders:
            return nodes
        else:
            # Programmer fucked up.
            raise ValueError("Cannot return neither files nor folders.")

    def __init__(self, env: env) -> None:
        self.__env = env
        self.__googleDriveApi = GoogleDriveApi(self.__env)

        self.__cache = {}
        if os.path.exists(self.__env['CACHE_FILE']):
            with open(self.__env['CACHE_FILE'], 'r') as f:
                try:
                    self.__cache = json.load(f)
                except json.decoder.JSONDecodeError:
                    print('Cache file invalid. Delete.')
                    with open(self.__env['CACHE_FILE'], 'w') as f:
                        f.truncate(0)
        else:
            # create empty file
            open(self.__env['CACHE_FILE'], 'a').close()
        # delete super stale cache entries, probably these folders don't exist anymore
        for key in list(self.__cache.keys()):
            time = self.__cache[key]['time']
            if datetime.datetime.utcnow() - datetime.datetime.fromisoformat(time) > datetime.timedelta(days=60):
                print(f"cache: delete stale entry: '{key}'")
                del self.__cache[key]
        self.__writeBackCache()
