from __future__ import print_function
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import MutualTLSChannelError
from googleapiclient.http import MediaIoBaseDownload
from typing import TypedDict
from envType import Env


ID = str


class Node(TypedDict):
    """ Type for a node (file or folder) returned by Google Drive API. """
    id: ID
    name: str
    mimeType: str
    size: int # size in bytes, absent for folders


class GoogleDriveApi:
    """
    A high level abstraction to the Google Drive API.
    Provides exactly the functionality this project needs.
    """

    __env: Env
    __credentials: Credentials
    __service: any

    MIME_TYPE_FOLDER: str = 'application/vnd.google-apps.folder'

    def __authenticate(self) -> None:
        """
        `token.json` stores the user's access and refresh tokens, and is created
        automatically when the authorization flow completes for the first time.
        """
        # If modifying these scopes, delete `token.json`.
        SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
        credentials = None
        # `token.json` stores the user's access and refresh tokens, and is created
        # automatically when the authorization flow completes for the first time.
        if os.path.exists(self.__env['TOKEN_FILE']):
            try:
                credentials = Credentials.from_authorized_user_file(
                    self.__env['TOKEN_FILE'], SCOPES)
            except ValueError:
                # credentials will be recreated
                pass
        # If there are no (valid) credentials available, let the user log in.
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.__env['CREDENTIALS_FILE'], SCOPES)
                credentials = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(self.__env['TOKEN_FILE'], 'w') as f:
                f.write(credentials.to_json())
        self.__credentials = credentials

    def downloadFile(self, fileId: ID, path: str) -> None:
        """
        Download a file.

        @param fileID Google Drive ID of file.
        @param path Path to target location incl. file name on disk. Path must exist completely.
        """
        try:
            request = self.__service.files().get_media(fileId=fileId)
            with open(path, 'w') as f:
                downloader = MediaIoBaseDownload(f.buffer, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    print(f'  download {int(status.progress() * 100)}%')
        except HttpError as error:
            raise error

    def getNode(self, nodeId: ID) -> Node:
        QUERY_PARAMS: dict[str: any] = {
            'fields': "id, name, mimeType",
            'supportsAllDrives': True,  # specify that we handle shared drives
        }

        try:
            response = self.__service.files().get(
                fileId=nodeId,
                **QUERY_PARAMS
            ).execute()
            return response
        except HttpError as error:
            raise error

    def getFolderContent(self, folderId: ID) -> list[Node]:
        QUERY_PARAMS: dict[str: any] = {
            'fields': "nextPageToken, files(id, name, mimeType, size)",
            'pageSize': 40,  # not guaranteed to be respected by API
            'supportsAllDrives': True,  # specify that we handle shared drives
            'includeItemsFromAllDrives': True,  # specify that we handle shared drives
            'corpora': 'drive',  # used for handling shared drives
            'driveId': self.__env['DRIVE_ID']
        }

        nodes: list[Node] = []
        pageToken = None
        # iterate over pages
        while True:
            try:
                response = self.__service.files().list(
                    q=f"'{folderId}' in parents and not trashed",
                    pageToken=pageToken,
                    **QUERY_PARAMS
                ).execute()
            except HttpError as error:
                raise error

            # API request may be incomplete in case of very large requests.
            # It's unlikely that we hit the limit.
            # Even if, for this application it is irrelevant if we miss a few
            # files or folders.
            if response.get('incompleteSearch'):
                print("incomplete search, continuing")

            responses = response.get('files', [])

            def m(x):
                if x['mimeType'] != self.MIME_TYPE_FOLDER:
                    x['size'] = int(x['size'])
                return x
            l = map(lambda x: m(x), responses)
            nodes.extend(l)

            pageToken = response.get('nextPageToken', None)
            if pageToken is None:
                break

        return nodes

    def __init__(self, env: Env) -> None:
        self.__env = env

        self.__authenticate()
        try:
            self.__service = build(
                'drive', 'v3', credentials=self.__credentials)
        except MutualTLSChannelError as error:
            raise error
