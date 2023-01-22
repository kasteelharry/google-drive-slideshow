# Slide Show

Presents random pictures from a given Google Drive folder.

The application requires read access to your Google Drive. It will ask for it during first run or if it expired.

## Setup

You need to create a Google Cloud project, enable the API `drive.readonly`, Configure OAuth, and create access credentials. Make sure the Google account you are using has access to the files you want for the slideshow.

[Quick Start by Google](https://developers.google.com/workspace/guides/get-started). You need to enable `drive.readonly` API and provide the application with a credentials `credentials.json` file.

## Dependencies

Install dependencies from `requirements.txt`.

## License

Copyright (C) 2023 Michael Heider michael@heider.org

This software is licensed under GPL 3.0 or any later version, see license file.

## Developper

[Michael's Google Cloud Console Project](https://console.cloud.google.com/home/dashboard?authuser=1&project=eestec-lc-zurich-slideshow&supportedpurview=project)

Tkinter: `pip install tk-tools` should be enough? Else `apt install python3-tk`.

`apt install python3-pil python3-pil.imagetk`

check supported image formats of Pillow: `python3 -m PIL`
