#!/usr/bin/env python2
from __future__ import print_function

import argparse as ap
import json
import sys

import requests

LANG_CODES = {'c': 28, 'c++': 16, 'objectivec': 21, 'objectivec++': 35}


def create_query_dict(pattern, langs, page):
    call_dict = {'q': pattern, 'src': 2, 'per_page': 100, 'p': page}
    langs = [LANG_CODES[item.replace('-', '').lower()]
             for item in langs.split()]
    call_dict.update({'lan': langs})
    return call_dict


def get_unique_sorted_projects(matches):
    projects = {}
    for match in matches:
        if match['url'] not in projects:
            projects[match['url']] = [match['name'], match['lines']]
        else:
            projects[match['url']][1] += match['lines']
    sorted_projects = sorted(
        projects.items(), key=lambda e: e[1][1], reverse=True)
    unique_sorted_projects = []
    for item in sorted_projects:
        unique_sorted_projects.append(
            {'name': item[1][0], 'url': item[0]})
    return unique_sorted_projects


def main():
    parser = ap.ArgumentParser(description="Project list generator.")
    parser.add_argument('pattern', metavar='PATTERN',
                        help="code search pattern")
    parser.add_argument('langs', metavar='LANGUAGES',
                        help="search for projects written in these languages "
                             "(e.g. 'C C++')")
    parser.add_argument('n', metavar='N', type=int,
                        help="desired number of projects")
    parser.add_argument('--output', metavar='FILE',
                        default='config.json', help="output JSON file")
    args = parser.parse_args()

    print("Using search pattern '%s'." % args.pattern)
    print("Searching for projects written in '%s'." % args.langs)

    if args.n < 1:
        sys.stderr.write("[ERROR] Invalid number of projects: %s.\n"
                         % str(args.n))
        sys.exit(1)

    print("Number of projects to fetch: %d." % args.n)

    matches = []
    # The SearchCode API limits the number of result pages to 0-49.
    for page in range(50):
        try:
            params = create_query_dict(args.pattern, args.langs, page)
            result_json = requests.get(
                'https://searchcode.com/api/codesearch_I/', params).json()
        except Exception as err:
            sys.stderr.write("[ERROR] %s\n" % str(err))
        if not result_json['results']:
            break
        for item in result_json['results']:
            matches.append(
                {'name': item['name'], 'url': item['repo'],
                 'lines': len(item['lines'])})

    projects = get_unique_sorted_projects(matches)[:args.n]

    output = {'projects': projects,
              'configurations': {
                  'name': 'baseline'
              },
              'CodeChecker': {
                  'url': 'http://localhost:8001/Default'
              }
             }
    with open(args.output, 'w+') as config_file:
        json.dump(output, config_file, indent=2)

    print("Done.")


if __name__ == "__main__":
    main()
