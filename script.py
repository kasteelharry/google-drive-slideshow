#!/usr/bin/python3

import os
import random
from dotenv import load_dotenv

from customTypes import *
from fileSystem import FileSystem

# import tkinter
# from PIL import Image, ImageTk
# import time

import tkinter as tk
from pathlib import Path
from PIL import Image, ImageTk
from itertools import cycle


class Main:
    __env: env
    __fileSystem: FileSystem
    slideshow: tk.Tk
    current_slide: tk.Label
    next_image: tk.PhotoImage

    class __DirectoryEmptyException(Exception):
        pass

    def __readEnv(self) -> None:
        load_dotenv()
        env = {
            'DRIVE_ID': os.getenv('DRIVE_ID'),
            'ROOT_FOLDER_ID': os.getenv('ROOT_FOLDER_ID'),
            'CREDENTIALS_FILE': os.getenv('CREDENTIALS_FILE'),
            'TOKEN_FILE': os.getenv('TOKEN_FILE', 'token.json'),
            'CACHE_RETENTION': int(os.getenv('CACHE_RETENTION', 30)),
            'CACHE_FILE': os.getenv('CACHE_FILE', 'cache.json'),
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

    # def showPIL(self, pilImage):
    #     root = tkinter.Tk()
    #     w, h = root.winfo_screenwidth(), root.winfo_screenheight()
    #     root.overrideredirect(1)
    #     root.geometry("%dx%d+0+0" % (w, h))
    #     root.focus_set()
    #     root.bind("<Escape>", lambda e: (e.widget.withdraw(), e.widget.quit()))
    #     canvas = tkinter.Canvas(root, width=w, height=h)
    #     canvas.pack()
    #     canvas.configure(background='black')
    #     imgWidth, imgHeight = pilImage.size
    #     if imgWidth > w or imgHeight > h:
    #         ratio = min(w/imgWidth, h/imgHeight)
    #         imgWidth = int(imgWidth*ratio)
    #         imgHeight = int(imgHeight*ratio)
    #         pilImage = pilImage.resize((imgWidth, imgHeight), Image.ANTIALIAS)
    #     image = ImageTk.PhotoImage(pilImage)
    #     imagesprite = canvas.create_image(w/2, h/2, image=image)
    #     root.mainloop()

    # def init(self):
    #     root = tkinter.Tk()
    #     w, h = root.winfo_screenwidth(), root.winfo_screenheight()
    #     root.overrideredirect(1)
    #     root.geometry("%dx%d+0+0" % (w, h))
    #     root.focus_set()
    #     canvas = tkinter.Canvas(root, width=w, height=h)
    #     canvas.pack()
    #     canvas.configure(background='black')
    #     self.root = root

    # def showPIL(self, pilImage):
    #     imgWidth, imgHeight = pilImage.size
    #     # resize photo to full screen
    #     ratio = min(w/imgWidth, h/imgHeight)
    #     imgWidth = int(imgWidth*ratio)
    #     imgHeight = int(imgHeight*ratio)
    #     pilImage = pilImage.resize((imgWidth, imgHeight), Image.ANTIALIAS)
    #     image = ImageTk.PhotoImage(pilImage)
    #     imagesprite = canvas.create_image(w/2, h/2, image=image)
    #     self.root.update_idletasks()
    #     self.root.update()
    #     self.root.bind("<Escape>", lambda e: (
    #         e.widget.withdraw(), e.widget.quit()))

    def display_next_slide(self):
        print('Get next slide')
        file, path = self.__chooseRandomPicture()
        print('  remote:', path)
        pathLocal = self.__fileSystem.getFile(file)
        print('  local: ', pathLocal)

        pilImage = Image.open(pathLocal)
        imgWidth, imgHeight = pilImage.size
        pilImage = pilImage.resize((imgWidth, imgHeight), Image.ANTIALIAS)

        name = path
        self.next_image = ImageTk.PhotoImage(pilImage)

        self.current_slide.config(image=self.next_image)
        self.slideshow.title(name)
        self.slideshow.after(1000, self.display_next_slide)

    def run(self) -> None:
        # file, path = self.__chooseRandomPicture()
        # print(path)
        # pathLocal = self.__fileSystem.getFile(file)
        # print(pathLocal)

        image_paths = Path('temp').glob("*.jpg")
        self.images = cycle(zip(map(lambda p: p.name, image_paths), map(
            ImageTk.PhotoImage, map(Image.open, image_paths))))

        self.display_next_slide()
        self.slideshow.mainloop()

    def __init__(self) -> None:
        self.__readEnv()
        self.__fileSystem = FileSystem(self.__env)

        self.slideshow = tk.Tk()
        self.slideshow.title("EESTEC LC Zurich Slideshow")
        self.slideshow.geometry("300x300")
        self.slideshow.resizable(width=False, height=False)
        self.current_slide = tk.Label(self.slideshow)
        self.current_slide.pack()

        # self.slideshow.set_image_directory("temp")
        self.slideshow.bind("<Return>", lambda e: e.widget.quit())
        # self.slideshow.start()

        # sanity check
        # topLevelFolder = self.__fileSystem.getFolder(self.__env['ROOT_FOLDER_ID'])
        # print("sanity check Google Drive API")
        # print("top level name:      '{0}'".format(topLevelFolder['name']))
        # print("top level subfolders: {0:>3}".format(
        #     topLevelFolder['nrFolders']))
        # print("top level files:      {0:>3}".format(topLevelFolder['nrFiles']))


if __name__ == '__main__':
    instance = Main()
    instance.run()
