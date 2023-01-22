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


class Folder(TypedDict):
    id: ID
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

    def googleListNodes(self, folderId: str, queryParams: dict[any] = dict()) -> list[Node]:
        files = []
        pageToken = None
        # iterate over pages
        while True:
            try:
                response = self.service.files().list(
                    # and mimeType='application/vnd.google-apps.folder'
                    q=f"'{folderId}' in parents and not trashed",
                    pageToken=pageToken,
                    **queryParams
                ).execute()
            except HttpError as error:
                raise error
            files.extend(response.get('files', []))

            pageToken = response.get('nextPageToken', None)
            if pageToken is None:
                break

        return files

    def getFolder(self, folderId: ID, forceUpdate: bool = False) -> Folder:
        """
        Implementation note:
        If the cache misses, this gets the whole folder content from Google and
        caches it. This allows us to compute folder statistics.

        @param folderId: Google folder ID.
        @param forceUpdate: Force update cache.
        """
        # Standard params for Google Drive API file list.
        STANDARD_PARAMS: dict[str: any] = {
            'fields': "nextPageToken, files(id, name, mimeType)",
            'pageSize': 30,  # not guaranteed to be respected by API
            'supportsAllDrives': True,  # specify that we handle shared drives
            'includeItemsFromAllDrives': True,  # specify that we handle shared drives
            'corpora': 'drive',  # used for handling shared drives
            'driveId': self.env['DRIVE_ID']
        }

        folder = None
        # check cache
        item = self.cache.get(folderId, None)
        # no force update, no miss, not stale
        if not forceUpdate and item is not None and datetime.datetime.utcnow() - datetime.datetime.fromisoformat(item['time']) < datetime.timedelta(days=30):
            # cache hit
            print("  cache: hit")
            return self.cache[folderId]['folder']
        else:
            # cache miss, stale value or forced update
            print("  cache: query Google")
            nodes = self.googleListNodes(folderId, STANDARD_PARAMS)
            folder = Folder(
                id=folderId,
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

    def getFolderContent(self, folderId: ID, files: bool = True, folders: bool = True, forceUpdate: bool = False) -> list[Node]:
        """
        Returns files and/or folders from given folder.

        @param folderId: Google folder ID.
        @param files: Include files.
        @param folders: Include folders.
        @param forceUpdate: Force update cache.
        """
        nodes = self.getFolder(folderId, forceUpdate)['nodes']

        # filter result
        if folders and not files:
            return [node for node in nodes if node['mimeType'] == self.MIME_TYPE_FOLDER]
            # return filter(lambda node: node['mimeType'] == self.MIME_TYPE_FOLDER, nodes)
        elif files and not folders:
            return [node for node in nodes if node['mimeType'] != self.MIME_TYPE_FOLDER]
            # return filter(lambda node: node['mimeType'] != self.MIME_TYPE_FOLDER, nodes)
        elif files and folders:
            return nodes
        else:
            # Programmer fucked up.
            raise ValueError("Cannot return neither files nor folders.")

    # def getFolder(self, folderId: str, forceUpdate: bool = False) -> Folder:
    #     """ Get a folder. Ensures that statistics in node exist. """
    #     # make sure cache entry exists
    #     self.getFolderContent(folderId, True, True, forceUpdate)
    #     return self.cache[folderId]['folder']

    # def recursivePictureFinding(self, folderId: ID):
    #     folders = self.getFolderContent(folderId, False, True)
    #     for folder in folders:
    #         self.recursivePictureFinding(folder)
    #     files = self.getFolderContent(folderId, True, False)
    #     pictureDB[folderId] = files

    def chooseRandomPictureRecursive(self, folder: Folder) -> Node:
        folderId = folder['id']
        hasFiles = folder['nrFiles'] > 0
        n = folder['nrFolders']
        if hasFiles > 0:
            n += 1
        rFolder = random.randint(0, n-1)
        if hasFiles and rFolder == n-1:
            # pick file from current folder
            rFile = random.randint(0, folder['nrFiles']-1)
            return self.getFolderContent(folderId, True, False)[rFile]
        else:
            # descend one layer
            nextNode = self.getFolderContent(folderId, False, True)[rFolder]
            nextFolder = self.getFolder(nextNode['id'])
            return self.chooseRandomPictureRecursive(nextFolder)

    def chooseRandomPicture(self) -> Node:
        topLevelFolder = self.getFolder(self.env['ROOT_FOLDER_ID'])
        nrFolders = topLevelFolder['nrFolders']
        topLevelFolders = self.getFolderContent(
            self.env['ROOT_FOLDER_ID'], False, True)
        r = random.randint(0, nrFolders-1)
        nextFolder = self.getFolder(topLevelFolders[r]['id'])
        return self.chooseRandomPictureRecursive(nextFolder)

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
