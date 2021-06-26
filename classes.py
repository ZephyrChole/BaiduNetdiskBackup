import os
import re
import sys
import time
import subprocess
import logging


def get_logger(name, level, has_console, has_file):
    formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s')
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if has_console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    if has_file:
        fh = logging.FileHandler(f'./log/{time.strftime("%Y-%m-%d", time.localtime())}.log', encoding='utf-8')
        fh.setLevel(level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger


class Unit:
    def __init__(self, local_path, relative_path):
        self.local_path = local_path
        self.name = os.path.split(local_path)[1]
        self.relative_path = relative_path
        self.remote_path = f'{DST}/{relative_path}' if len(relative_path) else '/'

    @staticmethod
    def start_popen(parameters):
        p = subprocess.Popen(parameters, stdout=subprocess.PIPE)
        p.wait()
        p.terminate()
        return list(map(lambda x: x.decode('utf-8').strip(), p.stdout.readlines()))

    def get_meta(self, path=None):
        if path is None:
            path = self.remote_path
        else:
            pass
        return self.start_popen([SCRIPT_PATH, 'meta', path])

    def wrapped_logger(self, level, message):
        level2func = {logging.DEBUG: LOGGER.debug, logging.INFO: LOGGER.info, logging.WARNING: LOGGER.warning,
                      logging.ERROR: LOGGER.error, logging.FATAL: LOGGER.fatal}
        indent = self.relative_path.count('/') * '    '
        level2func.get(level, LOGGER.info)('{}{}'.format(indent, message))


class File(Unit):
    def __init__(self, local_path, relative_path):
        super(File, self).__init__(local_path, relative_path)
        self.wrapped_logger(logging.INFO, f'{self.relative_path}  linked')

    def upload(self):
        if self.has_info():
            self.wrapped_logger(logging.INFO, f'{self.relative_path} skip')
        else:
            self.wrapped_logger(logging.INFO, f'{self.relative_path} start upload')
            self.start_upload()

    def start_upload(self):
        self.start_popen([SCRIPT_PATH, 'upload', self.local_path, os.path.split(self.remote_path)[0]])

    def has_info(self):
        return len(self.get_meta()) != 2


class Directory(Unit):
    def __init__(self, local_path, relative_path):
        super(Directory, self).__init__(local_path, relative_path)
        self.wrapped_logger(logging.INFO, f'{self.relative_path}/ linked')
        self.sub_file = []
        self.sub_directory = []

    def sub_init(self):
        # noinspection PyUnresolvedReferences
        def is_ignore(n):
            return IGNORE_RE is not None and IGNORE_RE.search(n)

        self.wrapped_logger(logging.INFO, f'{self.relative_path} sub init start')
        if self.make_ready():
            for name in os.listdir(self.local_path):
                local_path = f'{self.local_path}/{name}'
                relative_path = f'{self.relative_path}/{name}' if len(self.relative_path) else name
                if os.path.isfile(local_path):
                    if is_ignore(name):
                        self.wrapped_logger(logging.DEBUG, 'ignore')
                    else:
                        self.sub_file.append(File(local_path, relative_path))
                else:
                    self.sub_directory.append(Directory(local_path, relative_path))
        else:
            self.wrapped_logger(logging.ERROR, 'not ready!')
        self.wrapped_logger(logging.INFO, 'sub init finished')

    def make_ready(self, path=None):
        def is_error(r):
            # not exist or not login
            return len(r) == 2

        def need_login(r):
            return re.search('重新登录', r)

        path = self.remote_path if path is None else path
        upper = os.path.split(path)[0]
        upper_meta = self.get_meta(upper)
        if is_error(upper_meta):
            self.wrapped_logger(logging.DEBUG, f'upper_meta: {upper_meta}')
            if need_login(upper_meta[1]):
                self.wrapped_logger(logging.ERROR, 'not login!')
                return False
            else:
                self.make_ready(upper)
                self.mkdir(path)
        else:
            path_meta = self.get_meta(path)
            if is_error(path_meta):
                self.wrapped_logger(logging.DEBUG, f'path_meta: {path_meta}')
                self.mkdir(path)
            else:
                pass
        return True

    def mkdir(self, path):
        self.wrapped_logger(logging.INFO, f'mkdir {path}')
        self.start_popen([SCRIPT_PATH, 'mkdir', path])


class Backup:
    def __init__(self, script_path, src, dst, has_console, has_file, ignore_regex=None):
        global SCRIPT_PATH
        global SRC
        global DST
        global LOGGER
        global IGNORE_RE
        SCRIPT_PATH = script_path
        SRC = src
        DST = dst
        LOGGER = get_logger('backup', logging.DEBUG, has_console, has_file)
        if ignore_regex is not None:
            IGNORE_RE = re.compile(ignore_regex)

    def main(self):
        root = Directory(SRC, '')
        self.handle_directory(root)
        LOGGER.debug('exit')

    def handle_directory(self, node: Directory):
        node.sub_init()
        for f in node.sub_file:
            f.upload()
        for d in node.sub_directory:
            self.handle_directory(d)


SCRIPT_PATH = None
SRC = None
DST = None
LOGGER = logging
IGNORE_RE = None
