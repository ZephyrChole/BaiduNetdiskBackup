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
        self.dst = dst
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
            if md5 == self.get_local_md5():
                self.logger.debug(f'skip {self.local_path} --> {self.remote_path}')
            else:
                self.start_upload()
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
        try:
            meta_result = self.get_meta()
            if len(meta_result) == 2:
                return False
            else:
                size = int(re.search('(\d+),', meta_result[5]).group(1))
                md5_result = re.search('md5 \(可能不正确\) {2}(.+)', meta_result[6])
                if md5_result:
                    if re.search('修复md5失败', self.fix_md5()[0]):
                        md5 = md5_result.group(1)
                    else:
                        meta_result = self.get_meta()
                        md5 = re.search('md5 \(截图请打码\) {2}(.+)', meta_result[6]).group(1)
                else:
                    md5 = re.search('md5 \(截图请打码\) {2}(.+)', meta_result[6]).group(1)
                return size, md5
        except Exception as e:
            self.logger.error(e)
            local = list(locals().keys())
            for k in local:
                if re.search('__.+__', k):
                    pass
                else:
                    self.logger.error(f'{k}: {locals().get(k)}')
            return False

    def fix_md5(self):
        return self.startPopen([self.script_path, 'fixmd5', self.remote_path])


class Directory(Unit):
    def __init__(self, script_path, logger, dst, local_path, relative_path, ignore_regex):
        super(Directory, self).__init__(script_path, logger, dst, local_path, relative_path)
        self.ignore_regex = ignore_regex

        self.flag = self.check_path(self.remote_path)
        self.logger.debug(f'new directory {local_path} --> {self.remote_path}')

    def sub_init(self):
        if self.flag:
            return 1
        self.sub_file = []
        self.sub_directory = []
        for name in os.listdir(self.local_path):
            full_local_path = f'{self.local_path}/{name}'
            full_relative_path = f'{self.relative_path}/{name}' if len(self.relative_path) else name
            if os.path.isfile(full_local_path):
                if self.ignore_regex and self.ignore_regex.search(name):
                    pass
                else:
                    self.sub_file.append(
                        File(self.script_path, self.logger, self.dst, full_local_path, full_relative_path))
            else:
                self.sub_directory.append(
                    Directory(self.script_path, self.logger, self.dst, full_local_path, full_relative_path,
                              self.ignore_regex))

    def check_path(self, path):
        upper = os.path.split(path)[0]
        upper_meta = self.get_meta(upper)
        if len(upper_meta) == 2:
            self.logger.debug(f'upper_meta: {upper_meta}')
            if re.search('重新登录', upper_meta[1]):
                return False
            return self.check_path(upper)
            self.mkdir(path)
        else:
            path_meta = self.get_meta(path)
            if len(path_meta) == 2:
                if re.search('重新登录', path_meta[1]):
                    return False
                self.logger.debug(f'path_meta: {path_meta}')
                self.mkdir(path)
            return True

    def mkdir(self, path):
        self.logger.info(f'mkdir {path}')
        self.startPopen([self.script_path, 'mkdir', path])


class Backup:
    def __init__(self, script_path, src, dst, hasConsole, hasFile, ignore_regex=None):
        self.script_path = script_path
        self.src = src
        self.dst = dst
        self.logger = get_logger('backup', LogSetting(logging.DEBUG, hasConsole, hasFile))
        self.ignore_regex = re.compile(ignore_regex) if ignore_regex else None

    def main(self):
        root = Directory(self.script_path, self.logger, self.dst, self.src, '', self.ignore_regex)
        self.loop(root)

    def loop(self, node: Directory):
        for f in node.sub_file:
            f.upload()
        for d in node.sub_directory:
            self.loop(d)
