import os
import re
import sys
import time
import hashlib
import subprocess
import logging


class LogSetting:
    def __init__(self, level: logging.INFO, hasConsole, hasFile):
        self.level = level
        self.hasConsole = hasConsole
        self.hasFile = hasFile


def get_logger(name, log_setting: LogSetting):
    level = log_setting.level
    hasConsole = log_setting.hasConsole
    hasFile = log_setting.hasFile

    formatter = logging.Formatter("%(asctime)s %(filename)s %(levelname)s: %(message)s")
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if hasConsole:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    if hasFile:
        fh = logging.FileHandler(f'./log/{time.strftime("%Y-%m-%d", time.localtime())}.log', encoding='utf-8')
        fh.setLevel(level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger


class Unit:
    def __init__(self, script_path, logger, dst, local_path, relative_path):
        self.script_path = script_path
        self.logger = logger
        self.local_path = local_path
        self.name = os.path.split(local_path)[1]
        self.relative_path = relative_path
        self.remote_path = f'{dst}/{relative_path}' if len(relative_path) else dst

    @staticmethod
    def startPopen(parameters):
        p = subprocess.Popen(parameters, stdout=subprocess.PIPE)
        p.wait()
        return list(map(lambda x: x.decode('utf-8').strip(), p.stdout.readlines()))

    def get_meta(self, path=None):
        if path == None:
            path = self.remote_path
        return self.startPopen([self.script_path, 'meta', path])


class File(Unit):
    def __init__(self, script_path, logger, dst, local_path, relative_path):
        super(File, self).__init__(script_path, logger, dst, local_path, relative_path)
        self.size = os.path.getsize(self.local_path)
        self.logger.debug(f'new file {local_path} --> {self.remote_path}')

    def upload(self):
        result = self.get_info()
        if result:
            size, md5 = result
            if md5 != self.get_local_md5():
                self.start_upload()
            else:
                self.logger.debug(f'skip {self.local_path} --> {self.remote_path}')
        else:
            self.start_upload()

    def start_upload(self):
        self.logger.info(f'start upload: {self.local_path} --> {self.remote_path}')
        self.startPopen([self.script_path, 'upload', self.local_path, os.path.split(self.remote_path)[0]])

    def get_local_md5(self):
        buffer_size = 1024 ** 2
        m = hashlib.md5()
        with open(self.local_path, 'rb') as file:
            while True:
                buffer = file.read(buffer_size)
                if not buffer:
                    break
                m.update(buffer)
        self.md5 = m.hexdigest()
        return self.md5

    def get_info(self):
        result = self.get_meta()
        if len(result) == 2:
            return False
        else:
            size = int(re.search('(\d+),', result[5]).group(1))
            if re.search('md5 \(可能不正确\)', result[6]):
                self.fix_md5()
                result = self.get_meta()
            md5 = re.search('md5 \(截图请打码\) {2}(.+)', result[6]).group(1)
            return size, md5

    def fix_md5(self):
        return self.startPopen([self.script_path, 'fixmd5', self.remote_path])


class Directory(Unit):
    def __init__(self, script_path, logger, dst, local_path, relative_path):
        super(Directory, self).__init__(script_path, logger, dst, local_path, relative_path)
        self.check_path(self.remote_path)
        self.logger.debug(f'new directory {local_path} --> {self.remote_path}')
        self.sub_file = []
        self.sub_directory = []
        for name in os.listdir(self.local_path):
            full_local_path = f'{self.local_path}/{name}'
            full_relative_path = f'{self.relative_path}/{name}' if len(self.relative_path) else name
            if os.path.isfile(full_local_path):
                self.sub_file.append(File(script_path, logger, dst, full_local_path, full_relative_path))
            else:
                self.sub_directory.append(Directory(script_path, logger, dst, full_local_path, full_relative_path))

    def check_path(self, path):
        upper = os.path.split(path)[0]
        if len(self.get_meta(upper)) == 2:
            self.check_path(upper)
            self.mkdir(path)
        elif len(self.get_meta(path)) == 2:
            self.mkdir(path)

    def mkdir(self, path):
        self.logger.info(f'mkdir {path}')
        self.startPopen([self.script_path, 'mkdir', path])


class Backup:
    logger = get_logger('backup', LogSetting(logging.DEBUG, True, False))

    def __init__(self, script_path, src, dst):
        self.script_path = script_path
        self.src = src
        self.dst = dst

    def main(self):
        root = Directory(self.script_path, self.logger, self.dst, self.src, '')
        self.loop(root)

    def loop(self, node: Directory):
        for f in node.sub_file:
            f.upload()
        for d in node.sub_directory:
            self.loop(d)
