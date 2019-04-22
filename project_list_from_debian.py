#!/usr/bin/env python2
from __future__ import print_function
import argparse as ap
import gzip
import json
import os

try:
    from urlparse import urljoin
    from urllib import urlretrieve
except ImportError:
    from urllib.parse import urljoin
    from urllib.request import urlretrieve

# TODO:
#   * Filter packages based on dependencies that are installed 
#     on the host system.
#   * Filter packages based on language/build system.
#   * Support building packages in a fake-root environment.
#   * Suggest apt command to install dependencies.


FOLDERS = '0123456789abcdefghijklmnopqrstuvwxyz'


def main():
    parser = ap.ArgumentParser(description="Create project list from debian " +
                                           "source packages.",
                               formatter_class=ap.RawTextHelpFormatter)
    parser.add_argument("--output", metavar="FILE",
                        help="JSON file holding a list of projects")
    parser.add_argument("-u", "--url", metavar="URL",
                        help="debian FTP mirror")
    args = parser.parse_args()

    path, _ = urlretrieve(urljoin(args.url, "ls-lR.gz"))
    with gzip.open(path, 'rb') as f:
        lines = f.readlines()
    os.remove(path)

    archives = []
    for folder in FOLDERS:
        filename = None
        for line in lines:
            if isinstance(line, bytes):
                line = line.decode('utf-8')
            line = line.strip()
            if len(line) < 4:
                if filename:
                    archives.append(path + '/' + filename)
                path = None
                filename = None
            elif line[:13 + len(folder)] == './pool/main/' + folder + '/':
                path = line[2:-1]
            elif path and line.find('.orig.tar.') > 0:
                filename = line[1 + line.rfind(' '):]

    result = {"projects": [],
              "configurations": {
                  "name": "baseline"
              },
              "CodeChecker": {
                  "url": "http://localhost:8001/Default"
              }
              }
    for a in archives:
        project = {
            "name": a.split("/")[-2],
            "url": urljoin(args.url, a)
        }
        result["projects"].append(project)

    with open(args.output, 'w') as outfile:
        json.dump(result, outfile, indent=2)


if __name__ == '__main__':
    main()
