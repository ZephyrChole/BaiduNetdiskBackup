import os
import re
import sys
import time
import subprocess
import logging


def get_logger(name, level, has_console=False, has_file=False):
    formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s')
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if has_console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    if has_file:
        count = 0
        while True:
            path = f'./log/{time.strftime("%Y-%m-%d", time.localtime())}-{count}.log'
            if os.path.exists(path):
                count += 1
            else:
                break
        fh = logging.FileHandler(path, encoding='utf-8')
        fh.setLevel(level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger


class Unit:
    def __init__(self, local_path, relative_path):
        self.local_path = local_path
        self.name = os.path.split(local_path)[1]
        self.relative_path = relative_path
        self.remote_path = self.join(DST, relative_path)

    def start_popen(self, parameters, timeout=None):
        count = 0
        while True:
            try:
                p = subprocess.Popen(parameters, stdout=subprocess.PIPE)
                if timeout is None:
                    p.wait()
                else:
                    p.wait(timeout)
                p.terminate()
                return list(map(lambda x: x.decode('utf-8').strip(), p.stdout.readlines()))
            except subprocess.TimeoutExpired:
                count += 1
                LOGGER.warning(self.relative_path, f'timeout {count}')
                if count >= 3:
                    # upload failure
                    LOGGER.warning(self.relative_path, '↑ ✖')
                    return False

    def get_meta(self, path=None):
        if path is None:
            path = self.remote_path
        return self.start_popen([SCRIPT_PATH, 'meta', path], 60)

    @staticmethod
    def join(a, *paths):
        s = '/'.join(paths)
        if len(a) == 0:
            a = s
        elif a[-1] != '/':
            a = f'{a}/{s}'
        else:
            if s[0] != '/':
                a = f'{a}{s}'
            else:
                if len(s) > 1:
                    a = f'{a}{s[1:]}'
                else:
                    pass
        return a

    @staticmethod
    def split(path):
        result = re.search('(.+)/([^/]+$)', path)
        return result.group(1), result.group(2)


class File(Unit):
    def __init__(self, local_path, relative_path):
        super(File, self).__init__(local_path, relative_path)
        self.size = os.path.getsize(local_path)
        LOGGER.info(self.relative_path, f'{self.name}  ~')

    def try_upload(self):
        if self.has_info():
            # skip
            LOGGER.info(self.relative_path, f'{self.name}  >>')
        else:
            # start upload
            LOGGER.info(self.relative_path, f'{self.name}  ↑')
            self.upload()

    def upload(self):
        # per sec
        least_speed = 1024 * 1024 * 0.8 * 0.8
        timeout = self.size / least_speed + 15 * 60
        if isinstance(
                self.start_popen([SCRIPT_PATH, 'upload', self.local_path, self.split(self.remote_path)[0]], timeout),
                list):
            # upload success
            LOGGER.info(self.relative_path, '↑ ✔')

    def has_info(self):
        result = self.get_meta()
        return len(result) != 0 and len(result) != 2


class Directory(Unit):
    def __init__(self, local_path, relative_path):
        super(Directory, self).__init__(local_path, relative_path)
        LOGGER.info(self.relative_path, f'{self.name}/  ~')
        self.sub_file = []
        self.sub_directory = []

    def sub_init(self):
        # noinspection PyUnresolvedReferences
        def is_ignore(n):
            return IGNORE_RE is not None and IGNORE_RE.search(n)

        # noinspection PyUnresolvedReferences
        def is_include(n):
            return INCLUDE_RE is None or INCLUDE_RE.search(n)

        LOGGER.info(self.relative_path, f'(✪ω✪) {self.relative_path}')
        if not self.make_ready():
            LOGGER.info(self.relative_path, 'not ready!')
        else:
            for name in os.listdir(self.local_path):
                local_path = self.join(self.local_path, name)
                relative_path = self.join(self.relative_path, name)
                if os.path.isfile(local_path):
                    if not is_include(name):
                        LOGGER.debug(self.relative_path, f'{name} (。-ω-)zzz not include')
                    else:
                        if is_ignore(name):
                            LOGGER.debug(self.relative_path, f'{name} ┗( ▔, ▔ )┛ ignore')
                        else:
                            self.sub_file.append(File(local_path, relative_path))
                else:
                    self.sub_directory.append(Directory(local_path, relative_path))
        self.sub_file.sort(key=lambda f: f.name)
        self.sub_directory.sort(key=lambda d: d.name)
        # sub init finished
        LOGGER.info(self.relative_path, '(ಥ_ಥ)')

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
            LOGGER.debug(self.relative_path, f'upper_meta: {upper_meta}')
            if need_login(upper_meta[1]):
                LOGGER.error(self.relative_path, 'not login!')
                return False
            else:
                self.make_ready(upper)
                self.mkdir(path)
        else:
            path_meta = self.get_meta(path)
            if is_error(path_meta):
                LOGGER.debug(self.relative_path, f'path_meta: {path_meta}')
                self.mkdir(path)
        return True

    def mkdir(self, path):
        LOGGER.info(self.relative_path, f'mkdir {path}')
        self.start_popen([SCRIPT_PATH, 'mkdir', path])


class Backup:
    def __init__(self, script_path, src, dst, has_console, has_file, ignore_regex=None, include_regex=None):
        def path2indent(p):
            return (p.count('/') - 1) * '\t'

        global SCRIPT_PATH
        global SRC
        global DST
        global LOGGER_
        global LOGGER
        global IGNORE_RE
        global INCLUDE_RE
        SCRIPT_PATH = script_path
        SRC = src
        DST = dst
        LOGGER_ = get_logger('backup', logging.DEBUG, has_console, has_file)
        LOGGER = logging.getLogger('backup_')
        LOGGER.debug = lambda path, msg: LOGGER_.debug(f"{path2indent(path)}{msg}")
        LOGGER.info = lambda path, msg: LOGGER_.info(f"{path2indent(path)}{msg}")
        LOGGER.warning = lambda path, msg: LOGGER_.warning(f"{path2indent(path)}{msg}")
        LOGGER.error = lambda path, msg: LOGGER_.error(f"{path2indent(path)}{msg}")
        if ignore_regex is not None:
            IGNORE_RE = re.compile(ignore_regex)
        if include_regex is not None:
            INCLUDE_RE = re.compile(include_regex)

    def main(self):
        LOGGER_.info(f'pid: {os.getpid()}')
        root = Directory(SRC, '/')
        self.handle_directory(root)
        LOGGER_.debug('exit')

    def handle_directory(self, node: Directory):
        node.sub_init()
        for f in node.sub_file:
            f.try_upload()
        for d in node.sub_directory:
            self.handle_directory(d)


class Examiner:
    un_uploaded = []

    def __init__(self, script_path, src, dst, has_console, has_file, ignore_regex=None, include_regex=None):
        global SCRIPT_PATH
        global SRC
        global DST
        global LOGGER_
        global LOGGER
        global IGNORE_RE
        global INCLUDE_RE
        SCRIPT_PATH = script_path
        SRC = src
        DST = dst
        LOGGER_ = get_logger('examine', logging.DEBUG, has_console, has_file)
        LOGGER = logging.getLogger('examine_')
        LOGGER.debug = lambda path, msg: LOGGER_.debug(f"{path.count('/') * '    '}{msg}")
        LOGGER.info = lambda path, msg: LOGGER_.info(f"{path.count('/') * '    '}{msg}")
        LOGGER.warning = lambda path, msg: LOGGER_.warning(f"{path.count('/') * '    '}{msg}")
        LOGGER.error = lambda path, msg: LOGGER_.error(f"{path.count('/') * '    '}{msg}")
        if ignore_regex is not None:
            IGNORE_RE = re.compile(ignore_regex)
        if include_regex is not None:
            INCLUDE_RE = re.compile(include_regex)

    def main(self):
        LOGGER_.info(f'pid: {os.getpid()}')
        root = Directory(SRC, '')
        self.handle_directory(root)
        LOGGER_.info('\n' * 10)
        self.display_un_loaded()
        LOGGER_.debug('exit')

    def handle_directory(self, node: Directory):
        node.sub_init()
        for f in node.sub_file:
            if f.has_info():
                LOGGER.info(f.relative_path, f'{f.name}  ✔')
            else:
                LOGGER.info(f.relative_path,f'error meta {self.get_meta()}')
                LOGGER.info(f.relative_path, f'{f.name}  ✖')
                self.un_uploaded.append([f.relative_path, f'{f.relative_path}  ✖'])
        for d in node.sub_directory:
            self.handle_directory(d)

    def display_un_loaded(self):
        for u in self.un_uploaded:
            LOGGER.info(*u)


SCRIPT_PATH = None
SRC = None
DST = None
LOGGER_ = logging
LOGGER = logging
INCLUDE_RE = None
IGNORE_RE = None
