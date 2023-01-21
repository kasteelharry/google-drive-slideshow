#!/usr/bin/python3

from __future__ import print_function
import os
import json
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
    mimeType: str


def getEnv() -> dict:
    load_dotenv()
    return {
        'DRIVE_ID': os.getenv('DRIVE_ID'),
        'ROOT_FOLDER_ID': os.getenv('ROOT_FOLDER_ID'),
        # make sure to not check this into Git
        'CREDENTIALS_FILE': os.getenv('CREDENTIALS_FILE'),
        # make sure to not check this into Git
        'TOKEN_FILE': os.getenv('TOKEN_FILE', 'token.json'),
        'CACHE_FILE': os.getenv('CACHE_FILE', 'cache.json'),
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
        with open(tokenFile, 'w') as f:
            f.write(creds.to_json())
    return creds


def googleListFiles(service, folder: str, queryParams: dict[any] = dict(), mimeType: str = None, mimeTypeExclude: bool = False) -> list[File]:
    """
    mime type for folders: application/vnd.google-apps.folder
    """
    mimeTypeExcludeStr = '!' if mimeTypeExclude else ""
    mimeTypeFilter = f" and mimeType{mimeTypeExcludeStr}='{mimeType}'" if mimeType else ""
    files = []
    pageToken = None
    # iterate over pages
    while True:
        try:
            response = service.files().list(
                # and mimeType='application/vnd.google-apps.folder'
                q=f"'{folder}' in parents and not trashed" + mimeTypeFilter,
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


def getFolderContent(env: dict, service, folder: str, files: bool = True, folders: bool = True) -> list[File]:
    # Standard params for Google Drive API file list.
    standardParams = {
        'fields': "nextPageToken, files(id, name, mimeType)",
        'pageSize': 30,  # not guaranteed to be respected by API
        'supportsAllDrives': True,  # specify that we handle shared drives
        'includeItemsFromAllDrives': True,  # specify that we handle shared drives
        'corpora': 'drive',  # used for handling shared drives
        'driveId': env['DRIVE_ID']
    }
    MIME_TYPE_FOLDER = 'application/vnd.google-apps.folder'
    mimeType = None
    invert = False
    if files and folders:
        mimeType = None
        invert = False
    elif files and not folders:
        mimeType = MIME_TYPE_FOLDER
        invert = True
    elif not files and folders:
        mimeType = MIME_TYPE_FOLDER
        invert = False
    elif not files and not folders:
        raise ValueError("Cannot return neither files nor folders.")
    return googleListFiles(service, folder, standardParams, mimeType, invert)


def main():
    env = getEnv()
    creds = googleAuthenticate(env['CREDENTIALS_FILE'], env['TOKEN_FILE'])

    try:
        service = build('drive', 'v3', credentials=creds)

        print("query top level folder")
        topLevelFolders = getFolderContent(
            env, service, env['ROOT_FOLDER_ID'], False, True)
        # for folder in topLevelFolders:
        #     print('id: {0}, name: {1}, mimeType: {2}'.format(
        #         folder['id'], folder['name'], folder['mimeType']))
        # print(len(topLevelFolders))

        data = {
            'topLevel': {
                'nrOfFolders': len(topLevelFolders),
                'folders': topLevelFolders,
            },
        }

        for folder in topLevelFolders:
            print(f"query folder: '{folder['name']}'")
            id = folder['id']
            folders = getFolderContent(env, service, id, False, True)
            files = getFolderContent(env, service, id, True, False)
            data[id] = {
                'nrOfFolders': len(folders),
                'nrOfFiles': len(files),
                'folders': folders,
                'files': files,
            }

        with open(env['CACHE_FILE'], 'w') as f:
            json.dump(data, f, indent=4, check_circular=False)
    except HttpError as error:
        raise error


if __name__ == '__main__':
    main()
