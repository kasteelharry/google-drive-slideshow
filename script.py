#!/usr/bin/python3

from __future__ import print_function
import os
from typing import TypedDict
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class File(TypedDict):
    """
    File or folder returned by Google Drive API.
    """
    id: str
    name: str


def getEnv() -> dict:
    load_dotenv()
    return {
        'DRIVE_ID': os.getenv('DRIVE_ID'),
        'ROOT_FOLDER_ID': os.getenv('ROOT_FOLDER_ID'),
        # make sure to not check this into Git
        'CREDENTIALS_FILE': os.getenv('CREDENTIALS_FILE'),
        # make sure to not check this into Git
        'TOKEN_FILE': os.getenv('TOKEN_FILE', 'token.json')
    }


def googleAuthenticate(credentialsFile, tokenFile) -> Credentials:
    """
    The file token.json stores the user's access and refresh tokens, and is
    created automatically when the authorization flow completes for the first time.
    """
    # If modifying these scopes, delete the file token.json.
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(tokenFile):
        creds = Credentials.from_authorized_user_file(tokenFile, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentialsFile, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(tokenFile, 'w') as token:
            token.write(creds.to_json())
    return creds


def listFolders(service, rootFolder: str, queryParams: dict[any] = dict()) -> list[File]:
    try:
        files = []
        nextPageToken = None
        # iterate over pages
        while True:
            response = service.files().list(
                q=f"'{rootFolder}' in parents and mimeType='application/vnd.google-apps.folder' and not trashed",
                pageToken=nextPageToken,
                **queryParams
            ).execute()
            files.extend(response.get('files', []))
            nextPageToken = response.get('nextPageToken', None)
            if nextPageToken is None:
                break

    except HttpError as error:
        raise error

    return files


def main():
    env = getEnv()
    creds = googleAuthenticate(env['CREDENTIALS_FILE'], env['TOKEN_FILE'])
    # Standard params for Google Drive API file list.
    standardParams = {
        'fields': "nextPageToken, files(id, name)",
        'pageSize': 30,  # not guaranteed to be respected by API
        'supportsAllDrives': True,  # specify that we handle shared drives
        'includeItemsFromAllDrives': True,  # specify that we handle shared drives
        'corpora': 'drive',  # used for handling shared drives
        'driveId': env['DRIVE_ID']
    }
    try:
        service = build('drive', 'v3', credentials=creds)

        folders = listFolders(service, env['ROOT_FOLDER_ID'], standardParams)
        for folder in folders:
            print('id: {0}, name; {1}'.format(folder['id'], folder['name']))
        print(len(folders))
    except HttpError as error:
        raise error


if __name__ == '__main__':
    main()
