#!/usr/bin/python3

import os
import pathlib
import random
import collections
import shutil
import json
import cv2
from colorama import Fore, Back, Style
from dotenv import load_dotenv
import tkinter as tk
from PIL import Image, ImageTk, UnidentifiedImageError, ImageFile
from pillow_heif import register_heif_opener
from googleapiclient.errors import HttpError
from fileSystem import FileSystem, Folder, File
from envType import Env

class Slideshow:
    __env: Env
    __rootFolder: Folder
    __fileSystem: FileSystem

    __log: collections.deque[File]

    # slideshow
    __slideshow: tk.Tk
    __currentSlide: tk.Label
    # need to store this here to not have it garbage collected
    __nextImage: tk.PhotoImage
    __WIDTH_DISPLAY_HALF: float
    __HEIGHT_DISPLAY_HALF: float

    __photoDistribution: dict
    __sum: int

    SUPPORTED_IMAGE_MIME_TYPES = [
        'image/jpeg',
        'image/png',
        'image/heif',
        'image/x-photoshop',
        'image/cr2',
        'video/mp4',
        'video/mpeg',
        'video/quicktime',
        'video/x-ms-wmv',
        'video/x-msvideo',
    ]

    VIDEO_TYPES = [
        'video/mp4',
        'video/mpeg',
        'video/quicktime',
        'video/x-msvideo',
    ]


    class __DirectoryEmptyException(Exception):
        pass

    def __createPhotoDistribution(self) -> dict:
        '''
        Builds a dictionary of every top level folder in the root folder
        This distribution is then used to select a photo or video where
        folders with more files is selected more often.
        '''
        dist = dict()
        graph = dict()
        for i in range(0, self.__rootFolder['nrFolders']):
            nextNode = self.__fileSystem.filterNodes(
                self.__rootFolder['nodes'], True, False)[i]
            nextFolder = self.__fileSystem.getFolder(nextNode)
            dist[nextFolder['id']] = self.__getPhotoCount(nextFolder)
            graph[nextFolder['name']] = dist[nextFolder['id']]
        print(graph)
        return dict(sorted(dist.items(), key=lambda item: item[1]))

    def __getPhotoCount(self, folder: Folder) -> int:
        if (folder['nrFolders'] <= 0):
            return folder['nrFiles']
        sum = folder['nrFiles']
        for i in range(0, folder['nrFolders']):
            nextNode = self.__fileSystem.filterNodes(
                folder['nodes'], True, False)[i]
            nextFolder = self.__fileSystem.getFolder(nextNode)
            sum += self.__getPhotoCount(nextFolder)
        return sum
    
    def __getRandomPhotoDict(self) -> tuple[str, int]:
        # Generate a random number between 0 and total_sum
        random_number = random.randint(0, self.__sum - 1)
        # Iterate through the dictionary and find where the random number lies
        cumulative_sum = 0
        for key, value in self.__photoDistribution.items():
            cumulative_sum += value
            if random_number < cumulative_sum:
                return (key, random_number)
        pass

    def __readEnv(self) -> None:
        load_dotenv()
        env = {
            'DRIVE_ID': os.getenv('DRIVE_ID'),
            'ROOT_FOLDER_ID': os.getenv('ROOT_FOLDER_ID'),
            'CREDENTIALS_FILE': os.getenv('CREDENTIALS_FILE'),
            'TOKEN_FILE': os.getenv('TOKEN_FILE', 'token.json'),
            # SLIDESHOW_SPEED seconds
            'SLIDESHOW_SPEED': int(os.getenv('SLIDESHOW_SPEED'))*1000,
            # CACHE_RETENTION hours
            'CACHE_RETENTION': int(os.getenv('CACHE_RETENTION', 30)),
            'CACHE_FILE': os.getenv('CACHE_FILE', 'cache.json'),
            'PICTURE_TEMP_FOLDER': os.path.realpath(os.getenv('PICTURE_TEMP_FOLDER', 'temp')),
            'PICTURE_KEEP_NR': int(os.getenv('PICTURE_KEEP_NR', 10)),
            # MAX_FILE_SIZE in MB, -1 to disable
            'MAX_FILE_SIZE': int(os.getenv('MAX_FILE_SIZE', -1))*1_000_000,
            # MAX_VIDEO_LENGTH in minutes, -1 to disable all videos
            'MAX_VIDEO_LENGTH': int(os.getenv('MAX_VIDEO_LENGTH', -1)) * 60
        }

        # validate tempFolder
        programPath = os.path.realpath(os.path.dirname(__file__))
        if not pathlib.Path(env['PICTURE_TEMP_FOLDER']).is_relative_to(programPath):
            # Tempfolder is outside of program directory.
            # Since we erase its contents, this is dangerous.
            # Abort.
            print(
                Fore.RED + 'PICTURE_TEMP_FOLDER must be inside program directory.' + Style.RESET_ALL)
            exit(1)

        # ensure mandatory args are present
        if env['DRIVE_ID'] and env['ROOT_FOLDER_ID'] and env['CREDENTIALS_FILE']:
            self.__env = env
        else:
            raise ValueError(
                'Environment variables are invalid. Check your `.env`.')

    def __chooseRandomFileRec(self, folder: Folder) -> tuple[File, str]:
        n = folder['nrFolders']
        if n == 0:
            raise self.__DirectoryEmptyException(
                "Directory '{0}' is empty.".format(folder['id']))

        hasFiles = folder['nrFiles'] > 0
        if hasFiles > 0:
            n += 1
        
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
            nextFolder = self.__fileSystem.getFolder(nextNode)
            file, path = self.__chooseRandomFileRec(nextFolder)
            return file, nextFolder['name'] + "/" + path

    def __chooseRandomFileFirstLevel(self) -> tuple[File, str]:
        topLevelFolder = self.__fileSystem.getFolder(self.__rootFolder)
        topLevelFolders = self.__fileSystem.filterNodes(
            topLevelFolder['nodes'], True, False)
        # Show folders with more pictures more often
        r = self.__getRandomPhotoDict()
        nextFolderObject = next(filter(lambda obj: obj['id'] == r[0], topLevelFolders), None)
        nextFolder = self.__fileSystem.getFolder(nextFolderObject)
        file, path = self.__chooseRandomFileRec(nextFolder)
        return file, nextFolder['name'] + "/" + path

    def __getRandomPicture(self) -> tuple[File, str]:
        """
        Choose a random picture.
        Retry in case of errors.

        @return File and path to file.
        """
        errors = 0
        while errors < 10:
            try:
                file, path = self.__chooseRandomFileFirstLevel()
                if file['mimeType'] in self.SUPPORTED_IMAGE_MIME_TYPES:
                    if self.__env['MAX_FILE_SIZE'] == -1 or self.__env['MAX_FILE_SIZE'] > file['size']:
                        pathLocal = self.__fileSystem.getFile(file)
                        return file, path, pathLocal
                    else:
                        print(f"choose: file too large, retrying ('{path}')")
                else:
                    print(f"choose: unsupported file type, retrying ('{path}', '{file['mimeType']}')")
            except self.__DirectoryEmptyException:
                # try again, rejection sampling
                print('choose: empty directory, retrying')
            except HttpError as e:
                if e.status_code != 404:
                    raise e
                # some node along the way not found, probably stale cache
                print('404 error, probably a stale cache entry?')
            errors += 1
        raise RuntimeError('Choosing a random picture failed too many times.')

    def __logToFile(self, file: File, path: str) -> None:
        with open(os.path.join(self.__env['PICTURE_TEMP_FOLDER'], 'log.txt'), 'a') as f:
            f.write(json.dumps({
                'id': file['id'],
                'path': path,
            }, check_circular=False))
            f.write(f',{os.linesep}')

    def __resize(self, pilImage):
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
        return pilImage.resize(
            (imgWidthFull, imgHeightFull), Image.LANCZOS)


    def __display_next_slide(self) -> None:
        print('Get next slide')
        file, path, pathLocal = self.__getRandomPicture()
        print(f"Got next slide: '{path}'")

        self.__log.append(file)
        if len(self.__log) == self.__log.maxlen:
            oldFile = self.__log.popleft()
            self.__fileSystem.deleteFile(oldFile)
        self.__logToFile(file, path)
        
        self.__slideshow.title(path)


        if file['mimeType'] in self.VIDEO_TYPES:
            self.__currentSlide.delete('all')
        
            video = cv2.VideoCapture(pathLocal)
            fps = video.get(cv2.CAP_PROP_FPS)
            frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count/fps
            max_duration = self.__env['MAX_VIDEO_LENGTH']

            if duration > max_duration:
                print(f'Video length was too long, expected {max_duration}, received {duration}')
                self.__slideshow.after(0, self.__display_next_slide)
                return
            self.__displayVideo(video, fps)
            return
        try:
            pilImage: Image = Image.open(pathLocal)
        except (UnidentifiedImageError, OSError):
            # image is unsupported or corrupted
            # try again
            self.__slideshow.after(0, self.__display_next_slide)
            return

        pilImage = self.__resize(pilImage)
        # need to store iamge to not have it garbage collected immediately
        self.__nextImage = ImageTk.PhotoImage(pilImage)
        
        self.__currentSlide.create_image(
            self.__WIDTH_DISPLAY_HALF/2, self.__HEIGHT_DISPLAY_HALF/2, image=self.__nextImage, )

        text_string = str(path).split('/')[:-1]
        text = self.__currentSlide.create_text(self.__WIDTH_DISPLAY_HALF/2, 50, text=" ".join(text_string), fill="orange", font=('Helvetica 25 bold'))

        self.__slideshow.after(
            self.__env['SLIDESHOW_SPEED'], self.__display_next_slide)
        self.__slideshow.after(
            self.__env['SLIDESHOW_SPEED'], self.__currentSlide.delete, text)

    def __onWindowResize(self, event) -> None:
        """ Adapt values such that the next rendered image is again maximum size. """
        if (event.widget == self.__slideshow and (self.__WIDTH_DISPLAY_HALF != event.width or self.__HEIGHT_DISPLAY_HALF != event.height)):
            self.__WIDTH_DISPLAY_HALF = event.width
            self.__HEIGHT_DISPLAY_HALF = event.height
            self.__currentSlide.configure(
                width=self.__WIDTH_DISPLAY_HALF, height=self.__HEIGHT_DISPLAY_HALF)

    def __resize_frame(self, frame, target_width, target_height):
        original_height, original_width = frame.shape[:2]

        # Calculate the scaling factor
        scaling_factor = min(target_width / original_width, target_height / original_height)

        # Resize the frame while preserving aspect ratio
        new_width = int(original_width * scaling_factor)
        new_height = int(original_height * scaling_factor)
        
        # Resize the frame using OpenCV
        resized_frame = cv2.resize(frame, (new_width, new_height))
        return resized_frame


    def __displayVideo(self, video, fps) -> None:
        ret, frame = video.read()

        if not ret:
            video.release()
            self.__currentSlide.delete('all')
            self.__currentSlide.after(1, self.__display_next_slide) 
            return
        frame = self.__resize_frame(frame, 1920, 1080)
        cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(cv2image)

        imgtk = ImageTk.PhotoImage(img)
        self.__currentSlide.imgtk = imgtk
        self.__currentSlide.create_image(
            self.__WIDTH_DISPLAY_HALF/2, self.__HEIGHT_DISPLAY_HALF/2, image=imgtk, )
        self.__currentSlide.configure(background='black')

        if fps > 0:
            frame_delay_ms = int(500 / fps)
        else:
            frame_delay_ms = 33 
        self.__currentSlide.after(frame_delay_ms, self.__displayVideo, video, fps) 
        pass

    def __toggle_fullscreen(self, event=None):
        # Toggle fullscreen mode
        current = self.__slideshow.attributes("-fullscreen")
        self.__slideshow.attributes("-fullscreen", 1 - current)

    def run(self) -> None:
        self.__display_next_slide()
        self.__slideshow.mainloop()

        # cleanup
        # temp folder is not cleaned, in case we want to check one of the recent pictures.
        print('User closed window. Slideshow terminated.')
        exit(0)

    def __init__(self) -> None:
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        self.__readEnv()
        register_heif_opener()
        self.__fileSystem = FileSystem(self.__env)

        # HACK: Get root folder from ID only.
        self.__rootFolder = self.__fileSystem.getFolder(
            Folder(id=self.__env['ROOT_FOLDER_ID'], name="", nrFolders=-1, nrFiles=-1, nodes=[]))
        self.__log = collections.deque(maxlen=self.__env['PICTURE_KEEP_NR'])

        self.__photoDistribution = self.__createPhotoDistribution()
        # Calculate the total sum of the valid values
        self.__sum = sum(self.__photoDistribution.values())


        # force initialize cache
        # self.__fileSystem.forceInitialize(self.__rootFolder)

        # clear and generate temp folder
        tempFolder = self.__env['PICTURE_TEMP_FOLDER']
        if os.path.exists(tempFolder):
            shutil.rmtree(tempFolder)
        os.makedirs(tempFolder)

        # initialize GUI
        self.__slideshow = tk.Tk()
        self.__WIDTH_DISPLAY_HALF = self.__slideshow.winfo_screenwidth()
        self.__HEIGHT_DISPLAY_HALF = self.__slideshow.winfo_screenheight()
        # Override window size for testing
        # self.__WIDTH_DISPLAY_HALF = 300
        # self.__HEIGHT_DISPLAY_HALF = 300

        self.__slideshow.title("Slideshow")
        self.__slideshow.geometry(
            "%dx%d+0+0" % (self.__WIDTH_DISPLAY_HALF, self.__HEIGHT_DISPLAY_HALF))
        self.__slideshow.resizable(width=True, height=True)
        self.__slideshow.bind("<Configure>", self.__onWindowResize)
        self.__slideshow.bind("<Escape>", lambda e: e.widget.quit())
        self.__slideshow.bind("<F11>", self.__toggle_fullscreen)
        self.__slideshow.focus_set()

        self.__currentSlide = tk.Canvas(
            self.__slideshow, width=self.__WIDTH_DISPLAY_HALF, height=self.__HEIGHT_DISPLAY_HALF)
        self.__currentSlide.pack()
        self.__currentSlide.configure(background='black')


if __name__ == '__main__':
    instance = Slideshow()
    instance.run()
