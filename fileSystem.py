import os
import json
import datetime
from colorama import Fore, Back, Style

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

    def __writeBackCache(self) -> None:
        """Write back cache."""
        with open(self.__env['CACHE_FILE'], 'w') as f:
            # there are no circular references by design
            json.dump(self.__cache, f, check_circular=False)
    
    def getFile(self, file: File) -> str:
        FOLDER = 'temp'
        path = self.__googleDriveApi.downloadFile(file['id'], file['name'], FOLDER)
        return path

    def getFolder(self, folderId: ID, forceUpdate=False, skipStore=False) -> Folder:
        """
        Get a folder from ID. No full files are downloaded.

        Implementation note:
        Results are cached from last time. If the cache misses or is stale,
        the data is fetched from the Google Drive API.

        If the cache misses, this gets the folder attributes as well as all direct
        children and their attributes from Google and caches them. This allows us
        to compute folder statistics.

        @param folderId: Google folder ID.
        @param forceUpdate: Force update cache.
        @param skipStore: Don't write to cache. (May still read form cache.) Mainly used for internal purposes.
        """

        # query cache
        item = self.__cache.get(folderId, None)
        # no miss, no force update, not stale
        if item is not None and not forceUpdate and datetime.datetime.utcnow() - datetime.datetime.fromisoformat(item['time']) < datetime.timedelta(days=self.__env['CACHE_RETENTION']):
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
            if not skipStore:
                self.__writeBackCache()
            return folder

    @staticmethod
    def filterNodes(nodes: list[Node], folders=True, files=True) -> list[Node]:
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

    def __forceInitializeRec(self, currentFolder: Folder, forceUpdate: bool) -> None:
        for i, folderNode in enumerate(FileSystem.filterNodes(currentFolder['nodes'], True, False)):
            # Skip store in most cases.
            # This is a balance of not wasting a lot of time on continuously
            # writing back cache vs. not losing a lot of progress in the event
            # of a crash.
            skipStore = i % 5 != 0
            folder = self.getFolder(folderNode['id'], forceUpdate, skipStore)
            self.__forceInitializeRec(folder, forceUpdate)

    def __forceInitialize(self, forceUpdate=False) -> None:
        """ Recursively access all folders to put everything into cache. """
        print(Fore.RED + "cache: FORCE INITIALIZE" + Style.RESET_ALL)
        topLevelFolder = self.getFolder(self.__env['ROOT_FOLDER_ID'])
        self.__forceInitializeRec(topLevelFolder, forceUpdate)
        # Explicit write back, since we are skipping it sometimes in the
        # recursive function.
        self.__writeBackCache()
        print(Fore.RED + "cache: force initialize completed" + Style.RESET_ALL)

    def __init__(self, env: env, forceInitialize=False) -> None:
        self.__env = env
        self.__googleDriveApi = GoogleDriveApi(self.__env)

        self.__cache = {}
        if os.path.exists(self.__env['CACHE_FILE']):
            with open(self.__env['CACHE_FILE'], 'r') as f:
                try:
                    self.__cache = json.load(f)
                except json.decoder.JSONDecodeError:
                    print('cache: cache file invalid, deleting')
                    with open(self.__env['CACHE_FILE'], 'w') as f:
                        f.truncate(0)
        else:
            # create empty file
            open(self.__env['CACHE_FILE'], 'a').close()
        # delete super stale cache entries, probably these folders don't exist anymore
        for key in list(self.__cache.keys()):
            entry = self.__cache[key]
            time = entry['time']
            if datetime.datetime.utcnow() - datetime.datetime.fromisoformat(time) > datetime.timedelta(days=self.__env['CACHE_RETENTION']):
                print("cache: delete stale entry '{0}', '{1}'".format(
                    key, entry['folder']['name']))
                del self.__cache[key]
        self.__writeBackCache()

        if forceInitialize:
            self.__forceInitialize()
