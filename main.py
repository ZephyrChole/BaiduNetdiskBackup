import hashlib
import os
import re
import subprocess


class Unit:
    def __init__(self, upper_path, name):
        self.path = os.path.join(upper_path, name)
        self.upper_path = upper_path
        self.name = name


class File(Unit):
    md5 = None

    def __init__(self, upper_path, name):
        super(File, self).__init__(upper_path, name)
        self.size = os.path.getsize(self.path)

    def getMd5(self):
        if self.md5 == None:
            buffer_size = 1024 ** 2
            m = hashlib.md5()
            with open(self.path, 'rb') as file:
                while True:
                    buffer = file.read(buffer_size)
                    if not buffer:
                        break
                    m.update(buffer)
            self.md5 = m.hexdigest()
        return self.md5


class Directory(Unit):
    sub_directory = None

    def getSubDirectory(self):
        if self.sub_directory == None:
            self.sub_directory = []
            for name in os.listdir(self.path):
                full_path = os.path.join(self.path, name)
                if os.path.isfile(full_path):
                    self.sub_directory.append(File(self.path, name))
                else:
                    self.sub_directory.append(Directory(self.path, name))
        return self.sub_directory


class BaiduNetDiskUnit:
    def __init__(self, upper_path, name, script_path):
        self.path = os.path.join(upper_path, name)
        self.upper_path = upper_path
        self.name = name
        self.script_path = script_path

    @staticmethod
    def getOutput(parameters):
        p = subprocess.Popen(parameters, stdout=subprocess.PIPE)
        p.wait()
        return list(map(lambda x: x.decode('utf-8').strip(), p.stdout.readlines()))


class BaiduNetDiskFile(BaiduNetDiskUnit):
    def __init__(self, upper_path, name, script_path):
        super(BaiduNetDiskFile, self).__init__(upper_path, name, script_path)
        result = self.getOutput([self.script_path, 'meta', self.path])
        self.size = int(re.search('(\d+),', result[5]).group(1))
        self.md5 = re.search('md5 \(可能不正确\) {2}(.+)', result[6]).group(1)


class BaiduNetDiskDirectory(BaiduNetDiskUnit):
    sub_directory = None

    def getSubDirectory(self):
        if self.sub_directory == None:
            self.sub_directory = []
            result = self.getOutput([self.script_path, 'ls', self.path])
            file_finder = re.compile('\d {11}- {2}\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} {2}([^/]+)')
            directory_finder = re.compile('\d {11}- {2}\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} {2}([^/]+)/')
            for s in result[4:-2]:
                r = file_finder.match(s)
                if r:
                    self.sub_directory.append(BaiduNetDiskFile(self.path, r.group(1),self.script_path))
                else:
                    r = directory_finder.match(s)
                    if r:
                        self.sub_directory.append(BaiduNetDiskDirectory(self.path, r.group(1),self.script_path))

        return self.sub_directory


class Backup:
    def __init__(self, src, dst):
        self.src = src
        self.dst = dst

    def main(self):
        pass
