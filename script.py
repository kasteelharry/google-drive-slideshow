#!/usr/bin/python3

from __future__ import print_function
import os
import json
import datetime
import random
from collections.abc import Iterable
from typing import TypedDict
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import MutualTLSChannelError

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


class Main:
    """ Main class. """

    # constant after initialization
    env: dict
    credentials: Credentials
    service: any

    cache: dict[ID, CacheEntry]

    MIME_TYPE_FOLDER: str = 'application/vnd.google-apps.folder'

    class DirectoryEmptyException(Exception):
        pass

    def readEnv(self) -> dict[str, any]:
        load_dotenv()
        self.env = {
            'DRIVE_ID': os.getenv('DRIVE_ID'),
            'ROOT_FOLDER_ID': os.getenv('ROOT_FOLDER_ID'),
            'CREDENTIALS_FILE': os.getenv('CREDENTIALS_FILE'),
            'TOKEN_FILE': os.getenv('TOKEN_FILE', 'token.json'),
            'CACHE_FILE': os.getenv('CACHE_FILE', 'cache.json'),
        }

    def authenticate(self) -> Credentials:
        """
        `token.json` stores the user's access and refresh tokens, and is created
        automatically when the authorization flow completes for the first time.
        """
        # If modifying these scopes, delete `token.json`.
        SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
        credentials = None
        # `token.json` stores the user's access and refresh tokens, and is created
        # automatically when the authorization flow completes for the first time.
        if os.path.exists(self.env['TOKEN_FILE']):
            try:
                credentials = Credentials.from_authorized_user_file(
                    self.env['TOKEN_FILE'], SCOPES)
            except ValueError:
                # credentials will be recreated
                pass
        # If there are no (valid) credentials available, let the user log in.
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.env['CREDENTIALS_FILE'], SCOPES)
                credentials = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(self.env['TOKEN_FILE'], 'w') as f:
                f.write(credentials.to_json())
        self.credentials = credentials

    def writeBackCache(self):
        """Write back cache."""
        with open(self.env['CACHE_FILE'], 'w') as f:
            json.dump(self.cache, f, indent=4, check_circular=False)

    def googleGetNode(self, nodeId: ID) -> Node:
        QUERY_PARAMS: dict[str: any] = {
            'fields': "id, name, mimeType",
            'supportsAllDrives': True,  # specify that we handle shared drives
        }

        try:
            response = self.service.files().get(
                fileId=nodeId,
                **QUERY_PARAMS
            ).execute()
            return response
        except HttpError as error:
            raise error

    def googleGetFolderContent(self, folderId: ID) -> list[Node]:
        QUERY_PARAMS: dict[str: any] = {
            'fields': "nextPageToken, files(id, name, mimeType)",
            'pageSize': 30,  # not guaranteed to be respected by API
            'supportsAllDrives': True,  # specify that we handle shared drives
            'includeItemsFromAllDrives': True,  # specify that we handle shared drives
            'corpora': 'drive',  # used for handling shared drives
            'driveId': self.env['DRIVE_ID']
        }

        files = []
        pageToken = None
        # iterate over pages
        while True:
            try:
                response = self.service.files().list(
                    q=f"'{folderId}' in parents and not trashed",
                    pageToken=pageToken,
                    **QUERY_PARAMS
                ).execute()
            except HttpError as error:
                raise error

            if response.get('incompleteSearch'):
                print("incomplete search, continuing")

            files.extend(response.get('files', []))

            pageToken = response.get('nextPageToken', None)
            if pageToken is None:
                break

        return files

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
        item = self.cache.get(folderId, None)
        # no force update, no miss, not stale
        if not forceUpdate and item is not None and datetime.datetime.utcnow() - datetime.datetime.fromisoformat(item['time']) < datetime.timedelta(days=30):
            # cache hit
            folder = self.cache[folderId]['folder']
            print("  cache: hit '{0}'".format(folder['name']))
            return folder
        else:
            # cache miss, stale value or forced update
            print("  cache: query Google '{0}'".format(folderId), end='')
            name = self.googleGetNode(folderId)['name']
            print(f" -> '{name}'")
            nodes = self.googleGetFolderContent(folderId)
            folder = Folder(
                id=folderId,
                name=name,
                nrFolders=sum(
                    1 for node in nodes if node['mimeType'] == self.MIME_TYPE_FOLDER),
                nrFiles=sum(
                    1 for node in nodes if node['mimeType'] != self.MIME_TYPE_FOLDER),
                nodes=nodes
            )
            self.cache[folderId] = CacheEntry(
                time=datetime.datetime.utcnow().isoformat(timespec='seconds'),
                folder=folder
            )
            self.writeBackCache()
            return folder
        
    def filterNodes(self, nodes: list[Node], folders: bool = True, files: bool = True) -> list[Node]:
        """
        Returns files and/or folders from given folder.

        @param nodes: List of nodes.
        @param files: Include files.
        @param folders: Include folders.
        """

        # filter result
        if folders and not files:
            return [node for node in nodes if node['mimeType'] == self.MIME_TYPE_FOLDER]
        elif files and not folders:
            return [node for node in nodes if node['mimeType'] != self.MIME_TYPE_FOLDER]
        elif files and folders:
            return nodes
        else:
            # Programmer fucked up.
            raise ValueError("Cannot return neither files nor folders.")

    def chooseRandomPictureRecursive(self, folder: Folder) -> File:
        hasFiles = folder['nrFiles'] > 0
        n = folder['nrFolders']
        if hasFiles > 0:
            n += 1
        if n == 0:
            raise self.DirectoryEmptyException(
                "Directory '{0}' is empty.".format(folder['id']))
        rFolder = random.randint(0, n-1)
        if hasFiles and rFolder == n-1:
            # pick file from current folder
            rFile = random.randint(0, folder['nrFiles']-1)
            return self.filterNodes(folder['nodes'], False, True)[rFile]
        else:
            # descend one layer
            nextNode = self.filterNodes(folder['nodes'], True, False)[rFolder]
            nextFolder = self.getFolder(nextNode['id'])
            return self.chooseRandomPictureRecursive(nextFolder)

    def chooseRandomPictureFirstLevel(self) -> File:
        topLevelFolder = self.getFolder(self.env['ROOT_FOLDER_ID'])
        nrFolders = topLevelFolder['nrFolders']
        topLevelFolders = self.filterNodes(
            topLevelFolder['nodes'], True, False)
        r = random.randint(0, nrFolders-1)
        nextFolder = self.getFolder(topLevelFolders[r]['id'])
        return self.chooseRandomPictureRecursive(nextFolder)

    def chooseRandomPicture(self) -> File:
        while True:
            try:
                return self.chooseRandomPictureFirstLevel()
            except self.DirectoryEmptyException:
                # try again, rejection sampling
                pass

    def run(self):
        # topLevelFolders = self.getFolderContent(
        #     self.env['ROOT_FOLDER_ID'], False, True)

        # for folder in topLevelFolders:
        #     print('id: {0}, name: {1}, mimeType: {2}'.format(
        #         folder['id'], folder['name'], folder['mimeType']))
        # print(len(topLevelFolders))

        # for folder in topLevelFolders:
        #     print(f"query folder: '{folder['name']}'")
        #     folderId = folder['id']
        #     folders = self.getFolderContent(folderId, True, True)

        picture = self.chooseRandomPicture()
        print(picture)

    def __init__(self):
        self.readEnv()
        self.authenticate()
        try:
            self.service = build('drive', 'v3', credentials=self.credentials)
        except MutualTLSChannelError as error:
            raise error
        self.cache = {}
        # cache
        if os.path.exists(self.env['CACHE_FILE']):
            with open(self.env['CACHE_FILE'], 'r') as f:
                try:
                    self.cache = json.load(f)
                except json.decoder.JSONDecodeError as error:
                    # cache file invalid
                    print('Cache file invalid. Delete.')
                    with open(self.env['CACHE_FILE'], 'w') as f:
                        f.truncate(0)
        else:
            # create empty file
            open(self.env['CACHE_FILE'], 'a').close()
        # delete super stale cache entries, probably these folders don't exist anymore
        for key in list(self.cache.keys()):
            time = self.cache[key]['time']
            if datetime.datetime.utcnow() - datetime.datetime.fromisoformat(time) > datetime.timedelta(days=60):
                print(f"cache: delete stale entry: '{key}'")
                del self.cache[key]
        self.writeBackCache()


if __name__ == '__main__':
    instance = Main()
    instance.run()
