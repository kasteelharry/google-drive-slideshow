# Slide Show

Presents random pictures from a given Google Drive folder.

The application requires read access to your Google Drive. It will ask for it during first run or if it expired.

This does work with shared Drives.

## Setup

You need to create a Google Cloud project, enable the API `drive.readonly`, Configure OAuth, and create access credentials. Make sure the Google account you are using has access to the files you want for the slideshow.

[Quick Start by Google](https://developers.google.com/workspace/guides/get-started). You need to enable `drive.readonly` API and provide the application with a credentials `credentials.json` file.

Furthermore, setup a `.env` file containing at least the following parameters:

- DRIVE_ID='your-drive-id'
- ROOT_FOLDER_ID='your-folder-id' (folder needs to be on that drive)
- CREDENTIALS_FILE='credentials.json'
- SLIDESHOW_SPEED: How fast the slideshow is going in seconds. More precisely, it will be this time plus the time to find and download a new image.

Optional parameters:

- MAX_FILE_SIZE: Maximum allowable file size in MB. Larger files are skipped.
- PICTURE_KEEP_NR: How many pictures are kept before they are deleted again. This can be useful, if you want to have another look at a past but recent picture.

There are a few more technical options, which you can find in the `Slideshow` class in the `__readEnv` method. (advanced users)

## Usage

Run with `./slideshow.py`.

## Dependencies

Install dependencies from `requirements.txt`.

## License

Copyright (C) 2023 Michael Heider michael@heider.org

This software is licensed under GPL 3.0 or any later version, see license file.

## Trivia

This project was created to show off pictures of [EESTEC LC Zurich](https://www.eestec.ch) by Michael Heider in January 2023, then chairman of EESTEC LC Zurich.

## Developper

Help for the developer of this software and his random notes.

[Michael's Google Cloud Console Project](https://console.cloud.google.com/home/dashboard?authuser=1&project=eestec-lc-zurich-slideshow&supportedpurview=project)

Tkinter: `pip install tk-tools` should be enough? Else `apt install python3-tk`.

`apt install python3-pil python3-pil.imagetk`

check supported image formats of Pillow: `python3 -m PIL`
