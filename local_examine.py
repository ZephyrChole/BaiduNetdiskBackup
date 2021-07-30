#!/usr/bin/python
# -*- coding: UTF-8 -*-

# @author:ZephyrChole
# @file:local_examine.py
# @time:2021/07/30
import os
import re

SRC = ''
TAR = ''
un_sync = []
INCLUDE = None
IGNORE = None


def count_path_layer(p):
    c = 0
    while True:
        p, b = os.path.split(p)
        if len(b) == 0:
            break
        else:
            c += 1
    return c


def directory_loop(rel_p):
    # noinspection PyUnresolvedReferences
    def is_ignore(n):
        return IGNORE is not None and IGNORE.search(n)

    # noinspection PyUnresolvedReferences
    def is_include(n):
        return INCLUDE is None or INCLUDE.search(n)

    print('\t' * count_path_layer(rel_p) + rel_p)
    src_p = os.path.join(SRC, rel_p)
    for u in os.listdir(src_p):
        rel_p1 = os.path.join(rel_p, u)
        src_p1 = os.path.join(src_p, u)
        if os.path.isdir(src_p1):
            directory_loop(rel_p1)
        elif is_include(u) and not is_ignore(u):
            tar_p = os.path.join(TAR, rel_p)
            tar_p1 = os.path.join(tar_p, u)
            if not os.path.exists(tar_p1):
                un_sync.append(rel_p1)


def main(src, tar, include=None, ignore=None):
    global SRC
    global TAR
    global un_sync
    global INCLUDE
    global IGNORE
    SRC = src
    TAR = tar
    INCLUDE = re.compile(include) if include is not None else INCLUDE
    IGNORE = re.compile(ignore) if ignore is not None else IGNORE
    directory_loop('')
    print('\n' * 10)
    for i in un_sync:
        print(i)


if __name__ == '__main__':
    main()
