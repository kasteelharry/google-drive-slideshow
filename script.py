#!/usr/bin/python3

import os
import random
from dotenv import load_dotenv
import tkinter as tk
from PIL import Image, ImageTk, UnidentifiedImageError
from pillow_heif import register_heif_opener

from customTypes import *
from fileSystem import FileSystem


class Main:
    __env: env
    __fileSystem: FileSystem

    SUUPORTED_IMAGE_MIME_TYPES = [
        'image/jpeg',
        'image/png',
        'image/heif',
        'image/x-photoshop',
        'image/cr2',
    ]
    # SUUPORTED_IMAGE_MIME_TYPES = [
    #     'image/jpeg',
    #     'image/png',
    #     'image/heif',
    #     'image/cr2',
    #     'image/x-photoshop', # .psd
    # ]
    # SUUPORTED_VIDEO_MIME_TYPES = ['image/gif', 'video/avi', 'video/mp4', 'video/mpeg', 'video/quicktime', 'video/x-m4v', 'video/x-ms-wmv', 'video/x-msvideo', ]

    # slideshow
    __slideshow: tk.Tk
    __currentSlide: tk.Label
    # need to store this here to not have it garbage collected
    __nextImage: tk.PhotoImage
    __WIDTH_DISPLAY_HALF: float
    __HEIGHT_DISPLAY_HALF: float

    class __DirectoryEmptyException(Exception):
        pass

    def __readEnv(self) -> None:
        load_dotenv()
        env = {
            'DRIVE_ID': os.getenv('DRIVE_ID'),
            'ROOT_FOLDER_ID': os.getenv('ROOT_FOLDER_ID'),
            'CREDENTIALS_FILE': os.getenv('CREDENTIALS_FILE'),
            'TOKEN_FILE': os.getenv('TOKEN_FILE', 'token.json'),
            # CACHE_RETENTION days
            'CACHE_RETENTION': int(os.getenv('CACHE_RETENTION', 30)),
            'CACHE_FILE': os.getenv('CACHE_FILE', 'cache.json'),
            'PICTURE_TEMP_FOLDER': os.getenv('PICTURE_TEMP_FOLDER', 'temp'),
            # SLIDESHOW_SPEED seconds
            'SLIDESHOW_SPEED': int(os.getenv('SLIDESHOW_SPEED', 30))*1000,
        }
        if env['DRIVE_ID'] and env['ROOT_FOLDER_ID'] and env['CREDENTIALS_FILE']:
            self.__env = env
        else:
            raise ValueError(
                'Environment variables are invalid. Check your `.env`.')

    def __chooseRandomFileRec(self, folder: Folder) -> tuple[File, str]:
        hasFiles = folder['nrFiles'] > 0
        n = folder['nrFolders']
        if hasFiles > 0:
            n += 1
        if n == 0:
            raise self.__DirectoryEmptyException(
                "Directory '{0}' is empty.".format(folder['id']))
        rFolder = random.randint(0, n-1)
        if hasFiles and rFolder == n-1:
            # pick file from current folder
            rFile = random.randint(0, folder['nrFiles']-1)
            file: File = self.__fileSystem.filterNodes(
                folder['nodes'], False, True)[rFile]
            return file, file['name']
        else:
            # descend one layer
            nextNode = self.__fileSystem.filterNodes(
                folder['nodes'], True, False)[rFolder]
            nextFolder = self.__fileSystem.getFolder(nextNode['id'])
            file, path = self.__chooseRandomFileRec(nextFolder)
            return file, nextFolder['name'] + "/" + path

    def __chooseRandomFileFirstLevel(self) -> tuple[File, str]:
        topLevelFolder = self.__fileSystem.getFolder(
            self.__env['ROOT_FOLDER_ID'])
        nrFolders = topLevelFolder['nrFolders']
        topLevelFolders = self.__fileSystem.filterNodes(
            topLevelFolder['nodes'], True, False)
        r = random.randint(0, nrFolders-1)
        nextFolder = self.__fileSystem.getFolder(topLevelFolders[r]['id'])
        file, path = self.__chooseRandomFileRec(nextFolder)
        return file, nextFolder['name'] + "/" + path

    def __chooseRandomPicture(self) -> tuple[File, str]:
        """
        Choose a random picture.
        Retry in case of errors.

        @return File and path to file.
        """
        errors = 0
        while errors < 5:
            try:
                file, path = self.__chooseRandomFileFirstLevel()
                if file['mimeType'] in self.SUUPORTED_IMAGE_MIME_TYPES:
                    return file, path
                else:
                    print(f"choose: unsupported file type, retrying: '{path}'")
            except self.__DirectoryEmptyException:
                # try again, rejection sampling
                print('choose: empty directory, retrying')
            errors += 1
        raise RuntimeError('Choosing a random picture failed too many times.')

    def __display_next_slide(self):
        print('Get next slide')
        file, path = self.__chooseRandomPicture()
        pathLocal = self.__fileSystem.getFile(file)
        print(f"Got next slide: '{path}'")

        try:
            pilImage: Image = Image.open(pathLocal)
        except (UnidentifiedImageError, OSError):
            # image is unsupported or corrupted
            # try again
            self.__slideshow.after(0, self.__display_next_slide)
            return

        # resize image to full screen size
        imgWidth, imgHeight = pilImage.size
        # The .load() call is not necessary, but a workaround for
        # Pillow bug #6185 which causes issues during resizing.
        # error caused: ValueError: box can't exceed original image size
        # https://github.com/python-pillow/Pillow/issues/6185
        pilImage.load()
        ratio = min(self.__WIDTH_DISPLAY_HALF/imgWidth,
                    self.__HEIGHT_DISPLAY_HALF/imgHeight)
        imgWidthFull = int(imgWidth*ratio)
        imgHeightFull = int(imgHeight*ratio)
        pilImage = pilImage.resize(
            (imgWidthFull, imgHeightFull), Image.ANTIALIAS)

        # need to store iamge to not have it garbage collected immediately
        self.__nextImage = ImageTk.PhotoImage(pilImage)

        self.__currentSlide.create_image(
            self.__WIDTH_DISPLAY_HALF/2, self.__HEIGHT_DISPLAY_HALF/2, image=self.__nextImage)
        self.__slideshow.title(path)

        self.__slideshow.after(
            self.__env['SLIDESHOW_SPEED'], self.__display_next_slide)

    def __onWindowResize(self, event):
        if (event.widget == self.__slideshow and (self.__WIDTH_DISPLAY_HALF != event.width or self.__HEIGHT_DISPLAY_HALF != event.height)):
            print(f'{event.widget=}: {event.height=}, {event.width=}\n')
            self.__WIDTH_DISPLAY_HALF = event.width
            self.__HEIGHT_DISPLAY_HALF = event.height
            self.__currentSlide.configure(
                width=self.__WIDTH_DISPLAY_HALF, height=self.__HEIGHT_DISPLAY_HALF)

    def run(self) -> None:
        self.__display_next_slide()
        self.__slideshow.mainloop()

    def __init__(self) -> None:
        self.__readEnv()
        register_heif_opener()
        self.__fileSystem = FileSystem(self.__env)

        self.__slideshow = tk.Tk()
        self.__WIDTH_DISPLAY_HALF = self.__slideshow.winfo_screenwidth()
        self.__HEIGHT_DISPLAY_HALF = self.__slideshow.winfo_screenheight()
        # Override window size for testing
        self.__WIDTH_DISPLAY_HALF = 300
        self.__HEIGHT_DISPLAY_HALF = 300

        self.__slideshow.title("EESTEC LC Zurich Slideshow")
        self.__slideshow.geometry(
            "%dx%d+0+0" % (self.__WIDTH_DISPLAY_HALF, self.__HEIGHT_DISPLAY_HALF))
        self.__slideshow.resizable(width=True, height=True)
        self.__slideshow.bind("<Configure>", self.__onWindowResize)
        self.__slideshow.bind("<Escape>", lambda e: e.widget.quit())
        self.__slideshow.focus_set()

        self.__currentSlide = tk.Canvas(
            self.__slideshow, width=self.__WIDTH_DISPLAY_HALF, height=self.__HEIGHT_DISPLAY_HALF)
        self.__currentSlide.pack()
        self.__currentSlide.configure(background='black')

        # force overlay over everything in fullscreen
        # unfortunately, this also blocks closing why key press
        # may not work on other platforms than Linux (?)
        # self.slideshow.overrideredirect(1)

        # sanity check Google Drive API
        # topLevelFolder = self.__fileSystem.getFolder(self.__env['ROOT_FOLDER_ID'])
        # print("sanity check Google Drive API")
        # print("top level name:      '{0}'".format(topLevelFolder['name']))
        # print("top level subfolders: {0:>3}".format(
        #     topLevelFolder['nrFolders']))
        # print("top level files:      {0:>3}".format(topLevelFolder['nrFiles']))


if __name__ == '__main__':
    instance = Main()
    instance.run()
