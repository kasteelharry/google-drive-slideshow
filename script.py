#!/usr/bin/python3

import os
import random
from dotenv import load_dotenv
import tkinter as tk
from PIL import Image, ImageTk

from customTypes import *
from fileSystem import FileSystem


class Main:
    __env: env
    __fileSystem: FileSystem
    slideshow: tk.Tk
    currentSlide: tk.Label
    # need to store this here to not have it garbage collected
    nextImage: tk.PhotoImage
    WIDTH_DISPLAY_HALF: float
    HEIGHT_DISPLAY_HALF: float

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
            # SLIDESHOW_SPEED seconds
            'SLIDESHOW_SPEED': int(os.getenv('SLIDESHOW_SPEED', 5))*1000,
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

        ###########################################################################################
        ###########################################################################################
        ###########################################################################################
        # TODO
        # make sure the file is an image (else rejection sampling)
        # download the file
        # display the file
        # find a way to still display the file while we are downloading the next one in the background
        # deal with cache entry of files and folders that don't exist anymore

        SUUPORTED_IMAGE_MIME_TYPES = [
            'image/cr2', 'image/gif', 'image/heif', 'image/jpeg', 'image/png', 'image/x-photoshop', ]
        VIEO_MIME_TYPES = ['video/avi', 'video/mp4', 'video/mpeg',
                           'video/quicktime', 'video/x-m4v', 'video/x-ms-wmv', 'video/x-msvideo', ]

        errors = 0
        while errors < 5:
            try:
                file, path = self.__chooseRandomFileFirstLevel()
                if file['mimeType'] in SUUPORTED_IMAGE_MIME_TYPES:
                    return file, path
                else:
                    print(f"choose: unsupported file type, retrying: '{path}'")
            except self.__DirectoryEmptyException:
                # try again, rejection sampling
                print('choose: empty directory, retrying')
            errors += 1
        raise RuntimeError('Choosing a random picture failed too many times.')

    def display_next_slide(self):
        print('Get next slide')
        file, path = self.__chooseRandomPicture()
        pathLocal = self.__fileSystem.getFile(file)
        print(f"Got next slide: '{path}'")

        pilImage: Image = Image.open(pathLocal)

        # resize image to full screen size
        imgWidth, imgHeight = pilImage.size
        ratio = min(self.WIDTH_DISPLAY_HALF/imgWidth,
                    self.HEIGHT_DISPLAY_HALF/imgHeight)
        imgWidthFull = int(imgWidth*ratio)
        imgHeightFull = int(imgHeight*ratio)
        pilImage = pilImage.resize(
            (imgWidthFull, imgHeightFull), Image.ANTIALIAS)

        # need to store iamge to not have it garbage collected immediately
        self.nextImage = ImageTk.PhotoImage(pilImage)

        # self.current_slide.config(image=self.next_image) # for label instead of canvas
        self.currentSlide.create_image(
            self.WIDTH_DISPLAY_HALF/2, self.HEIGHT_DISPLAY_HALF/2, image=self.nextImage)
        self.slideshow.title(path)

        self.slideshow.after(1000, self.display_next_slide)

    def run(self) -> None:
        self.display_next_slide()
        self.slideshow.mainloop()

    def __init__(self) -> None:
        self.__readEnv()
        self.__fileSystem = FileSystem(self.__env)

        self.slideshow = tk.Tk()
        self.WIDTH_DISPLAY_HALF = self.slideshow.winfo_screenwidth()
        self.HEIGHT_DISPLAY_HALF = self.slideshow.winfo_screenheight()
        # Override window size for testing
        # self.WIDTH_DISPLAY_HALF = 300
        # self.HEIGHT_DISPLAY_HALF = 300

        self.slideshow.title("EESTEC LC Zurich Slideshow")
        self.slideshow.geometry(
            "%dx%d+0+0" % (self.WIDTH_DISPLAY_HALF, self.HEIGHT_DISPLAY_HALF))
        self.slideshow.resizable(width=False, height=False)
        self.slideshow.focus_set()
        self.slideshow.bind("<Return>", lambda e: e.widget.quit())

        # for label instead of canvas
        # self.current_slide = tk.Label(self.slideshow)
        # self.current_slide.pack()

        self.currentSlide = tk.Canvas(
            self.slideshow, width=self.WIDTH_DISPLAY_HALF, height=self.HEIGHT_DISPLAY_HALF)
        self.currentSlide.pack()
        self.currentSlide.configure(background='black')

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
