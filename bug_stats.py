#!/usr/bin/env python
# -------------------------------------------------------------------------
#                     The CodeChecker Infrastructure
#   This file is distributed under the University of Illinois Open Source
#   License. See LICENSE.TXT for details.
# -------------------------------------------------------------------------

import argparse
import json
import math
import os
import subprocess
import sys
from time import sleep


# ========================== UTILITY FUNCTIONS ===============================
def call_command(command):
    """ Call an external command and return with (output, return_code)."""

    try:
        out = subprocess.check_output(command,
                                      bufsize=-1,
                                      stderr=subprocess.STDOUT)
        return out, 0
    except subprocess.CalledProcessError as ex:
        return ex.output, ex.returncode


def cc_command_builder(cmds, extra_args=None):
    """
    Create a CodeChecker command from the given commands and extra arguments.
    """
    if not extra_args:
        extra_args = []

    return ["CodeChecker"] + cmds + extra_args + _CodeCheckerSharedArgs +\
           ["-o", "json"]


def print_table(lines, separate_head=True):
    """Prints a formatted table given a 2 dimensional array."""
    # Count the column width.

    widths = []
    for line in lines:
        for i, size in enumerate([len(x) for x in line]):
            while i >= len(widths):
                widths.append(0)
            if size > widths[i]:
                widths[i] = size

    # Generate the format string to pad the columns.
    print_string = ""
    for i, width in enumerate(widths):
        print_string += "{" + str(i) + ":" + str(width) + "} | "
    if len(print_string) == 0:
        return
    print_string = print_string[:-3]

    # Print the actual data.
    print("-" * (sum(widths) + 3 * (len(widths) - 1)))
    for i, line in enumerate(lines):
        print(print_string.format(*line))
        if i == 0 and separate_head:
            print("-" * (sum(widths) + 3 * (len(widths) - 1)))
    print("-" * (sum(widths) + 3 * (len(widths) - 1)))
    print('')


# ============================== ENTRY POINT =================================

# Check if CodeChecker exists.
try:
    with open(os.devnull, 'w') as nullfile:
        r = subprocess.call(["CodeChecker"], stderr=nullfile, stdout=nullfile)

    if r != 2:
        print("CodeChecker couldn't import some modules properly!")
        print("Check path please...")
        sys.exit(1)
except OSError:
    print("`CodeChecker` cannot be called!")
    print("Check path please...")
    sys.exit(1)


##############################################################################

parser = argparse.ArgumentParser(
    prog='BugStats',
    description='''BugStats can print BugPath statistics from CodeChecker
results. A CodeChecker must exist in the PATH environment variable to use this
tool.'''
)

parser.add_argument('--url', type=str, dest="url",
                    default='http://localhost:8001/Default',
                    help="Product URL where the results should be queried "
                         "from.")

mode_group = parser.add_argument_group('mode arguments')
mode_group = mode_group.add_mutually_exclusive_group(required=True)
mode_group.add_argument('-n', '--name', nargs='+', type=str, dest="names",
                        help='Runs to include in the output '
                             '(single full run names)')
mode_group.add_argument('-a', '--all', action='store_true',
                        dest="all",
                        help='Calculate statistics for ALL project found '
                             'on the server.')
mode_group.add_argument('-c', '--compare', '--diff',
                        action='store_true',
                        dest="diff",
                        help='Calculate statistics for a project diff.')

diff_group = parser.add_argument_group(
    'difference calculation arguments',
    "These arguments are used to set what kind of difference CodeChecker must "
    "generate. The meaning of these values are in line with `CodeChecker cmd "
    "diff`, see the help or user guide for that to understand. These options "
    "are only effective if '-c/--compare/--diff' is given!")
diff_group.add_argument('--basename', type=str, dest="DPbase",
                        required=False,
                        help='Base name.')
diff_group.add_argument('--newname', type=str, dest="DPnew",
                        required=False,
                        help='New name.')

diff_mgroup = diff_group.add_mutually_exclusive_group(required=False)
diff_mgroup.add_argument('--new', action="store_true", dest="DBnew",
                         help="Show new results.")
diff_mgroup.add_argument('--resolved', action="store_true", dest="DBresolved",
                         help="Show resolved results.")
diff_mgroup.add_argument('--unresolved', action="store_true",
                         dest="DBunresolved",
                         help="Show unresolved results.")

presentation = parser.add_argument_group('presentation arguments')
presentation.add_argument('--no-histogram',
                          action='store_false',
                          dest="histogram",
                          help='Disable histogram generation. '
                               'Histogram generation requires the '
                               '`data_hacks` pip module.')

presentation.add_argument('-d', '--deduplicate',
                          action='store_true',
                          dest="deduplicate",
                          help='Deduplicate bugs when counting. '
                               'Deduplication doesn\'t count the same bug '
                               '(based on the unique bug_id) multiple times '
                               'in ANY of the results shown.')

presentation.add_argument('-m', '--messages', '--verbose-duplicates',
                          action='store_true',
                          dest="verbose_duplicates",
                          help='When --deduplicate is enabled, the duplicate '
                               'bugs list will show more details: (file, '
                               'line, message).')

args = parser.parse_args()

if not args.deduplicate and args.verbose_duplicates:
    print("WARNING! -m/--verbose-duplicates/--messages has no effect if "
          "-d/--deduplicate is not enabled.")

if not args.diff and (args.DPbase or args.DPnew or args.DBnew or
                      args.DBresolved or args.DBunresolved):
    print("ERROR! Diff arguments such as --basename/--newname/--new/"
          "--resolved/--unresolved are only effective if -c/--compare/--diff "
          "is given.")
    sys.exit(2)

##############################################################################

# Check if histogram module exists.
Histogram = False
if args.histogram:
    try:
        with open(os.devnull, 'w') as nullfile:
            r = subprocess.call(["histogram.py"],
                                stderr=nullfile,
                                stdout=nullfile)

        if r == 1:
            Histogram = True
    except OSError:
        # Histogram generation remains disabled.
        pass

    if not Histogram:
        print("WARNING! `histogram.py` not found --- "
              "not generating histograms.")
        print("To enable, please `pip install data_hacks`.")
        print("To squelch this error, please specify '--no-histogram'.")
        print("\n\n")
        sleep(1)

##############################################################################

_CodeCheckerSharedArgs = ["--url", args.url]

# Check if the projects exist.
valid_projects_on_server, _ = call_command(
    cc_command_builder(["cmd", "runs"]))

if 'Connection refused' in valid_projects_on_server or \
        'Name or service not known' in valid_projects_on_server:
    print("ERROR! Couldn't connect to server.")
    sys.exit(1)

try:
    valid_projects_on_server = json.loads(valid_projects_on_server)
except ValueError:
    print("ERROR! CodeChecker didn't return proper JSON?! (valid projects)")
    sys.exit(1)

existing_runs = [p.keys()[0] for p in valid_projects_on_server]

##############################################################################

if not args.diff:
    # If we are not doing a diff, project results must be queried verbatim.

    def get_results(projects=[]):
        """Gets the results for the given list of projects naively from
        CodeChecker."""

        project_results = []
        for project in projects:
            print("Getting results for '" + project + "' from CodeChecker...")

            try:
                results, _ = call_command(cc_command_builder(
                    ["cmd", "results"], [project]
                ))
                results = json.loads(results)
                project_results.append((project, results))
            except ValueError:
                print("ERROR! CodeChecker didn't return proper JSON?! "
                      "(normal results)")
                print(results)
                continue

        return project_results
elif args.diff:
    def get_results(projects=None):
        if not projects or len(projects) != 3:
            print("ERROR! In diff mode, exactly THREE args must be "
                  "specified in [base, new, mode] order.")
            sys.exit(1)

        base = projects[0]
        new = projects[1]
        mode = projects[2]

        print("Getting {0} diff between '{1}' and '{2}'...".
              format(mode.upper(), base, new))

        try:
            results, _ = call_command(cc_command_builder(
                ["cmd", "diff"], ["--basename", base,
                                  "--newname", new,
                                  "--" + mode]
            ))
            results = '\n'.join([line for line in results.split('\n')
                                 if 'INFO' not in line
                                 and 'DEBUG' not in line])
            results = json.loads(results)
            return [(
                "diff({1}, {2}, {0})".format(mode.upper(), base, new),
                results
            )]
        except ValueError:
            print(results)
            print("ERROR! CodeChecker didn't return proper JSON?! "
                  "(diff results)")
            sys.exit(1)

##############################################################################

if args.names:
    print("Getting result metrics for " + ', '.join(args.names))

    project_names = [p for p in args.names if p in existing_runs]
    nonexistent = [p for p in args.names if p not in existing_runs]

    if len(nonexistent) > 0:
        print("WARNING! Ignoring specified but NON-EXISTENT runs: " +
              ', '.join(nonexistent))
elif args.all:
    print("Calculating for every project...")
    project_names = existing_runs
elif args.diff:
    if not args.DPbase or not args.DPnew:
        print("ERROR! With -c/--compare/--diff, you MUST also specify "
              "--basename and --newname, the projects to compare.")
        sys.exit(1)

    if args.DBnew:
        mode = "new"
    elif args.DBresolved:
        mode = "resolved"
    elif args.DBunresolved:
        mode = "unresolved"
    else:
        print("ERROR! With -c/--compare/--diff, you MUST also specify "
              "exactly ONE of the following:\n"
              "   --new                        Show NEW bugs in the diff.\n"
              "   --resolved                   Show the RESOLVED bugs.\n"
              "   --unresolved                 Show the UNRESOLVED bugs.")
        sys.exit(1)

    project_names = [args.DPbase, args.DPnew, mode]
else:
    project_names = []


##############################################################################

def calculate_metrics(bugPathLengths):
    bugPathLengths.sort()

    num_lengths = float(len(bugPathLengths))
    sum_lengths = float(sum(bugPathLengths))
    mean = sum_lengths / num_lengths

    percentiles_needed = [25, 50, 75, 90]
    percentile_values = []
    for perc in percentiles_needed:
        perc = float(perc) / 100
        idx = (perc * num_lengths) - 1
        middle_avg = not idx.is_integer()

        if middle_avg:
            # idx is NOT a whole number
            # we need to round it up
            idx = math.ceil(idx)

        # the percentile is the indexth element (if idx was rounded...)
        idx = int(idx)  # it is an index!
        percentile = float(bugPathLengths[idx])

        if not middle_avg:
            # if idx WAS a whole number, the percentile is the average
            # of the indexth element and the element after it
            percentile = float(bugPathLengths[idx] +
                               bugPathLengths[idx + 1]) / 2

        percentile_values.append((int(perc * 100), percentile))

    print("\n------------------- Metrics ------------------")
    print('Total # of bugs:             ' + str(int(num_lengths)))
    print('MIN BugPath length:          ' + str(bugPathLengths[0]))
    print('MAX BugPath length:          ' +
          str(bugPathLengths[len(bugPathLengths) - 1]))
    print('Mean length:                 ' + str(mean))

    print("")
    for percentile, value in percentile_values:
        print(" %:      {0}% percentile: {1}".format(percentile, value))


if Histogram:
    def make_histogram(bug_path_lengths):
        print("\n------------------- Histogram -------------------")
        p = subprocess.Popen(["histogram.py"],
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             bufsize=1)

        for length in bug_path_lengths:
            p.stdin.write(str(length) + "\n")
        p.stdin.flush()
        print(p.communicate("")[0])
else:
    def make_histogram(bug_path_lenghts):
        pass


for project, results in get_results(project_names):
    print("###############################################################")
    print("Generating BugPath metrics for '" + project + "'")

    # Get the entire BugPaths from the result.
    bug_paths = []

    # ---- Calculate grouped by checkers
    # (I know `CodeChecker cmd sum` can already do this, but we have the
    # data now here too.)
    checker_counts = {}

    # Handle deduplication

    duplicate_checker_counts = {}
    duplicate_bughashes = {}
    for res in results:
        # Calculate grouped by checkers
        if res['checkerId'] not in checker_counts:
            checker_counts[res['checkerId']] = 0

            # Set this here as dummy, even if deduplication is not enabled.
            duplicate_checker_counts[res['checkerId']] = 0

        checker_counts[res['checkerId']] += 1

        # Handle deduplication
        if args.deduplicate:
            # First, increase the count in the BugHash dict
            if res['bugHash'] not in duplicate_bughashes:
                duplicate_bughashes[res['bugHash']] = {
                    'count': 0,
                    'bug': res,
                    'shortest_path': None,
                    'shortest_length': None
                }

            # Indicate that the bugHash has been detected one more time
            duplicate_bughashes[res['bugHash']]['count'] += 1

            # If it is not the first detection of the given bugHash,
            # this is a duplicate. Thus, increase the count in the checker
            # group table.
            if duplicate_bughashes[res['bugHash']]['count'] != 1:
                duplicate_checker_counts[res['checkerId']] += 1

        # Get the entire BugPaths from the result.
        if not args.deduplicate:
            bug_paths.append(int(res['bugPathLength']))
        else:
            # Duplicated bugs must only be calculated ONCE if
            # deduplication is enabled.
            #
            # In this case, only the SHORTEST (as per discussed with @dkrupp)
            # BugPath length is calculated.
            bpl = int(res['bugPathLength'])
            if duplicate_bughashes[
                    res['bugHash']]['shortest_length'] is None \
                    or duplicate_bughashes[
                        res['bugHash']]['shortest_length'] > bpl:
                duplicate_bughashes[res['bugHash']]['shortest_length'] = bpl

    # If deduplication is enabled, we need to add the shortest paths to the
    # list... otherwise bug_paths already contains all data.
    if args.deduplicate:
        for _, data in duplicate_bughashes.items():
            bug_paths.append(data['shortest_path'])

    checker_ids = list(set(checker_counts.keys()))
    checker_ids.sort()

    if not args.deduplicate:
        rows = [("Checker ID", "Count")]
    else:
        rows = [("Checker ID",
                 "Total #",
                 "Duplicate # (without 'first' find)",
                 "Unique #")]

    for checker_id in checker_ids:
        if not args.deduplicate:
            rows.append((checker_id,
                         str(checker_counts[checker_id])))
        else:
            rows.append((checker_id,
                         str(checker_counts[checker_id]),
                         str(duplicate_checker_counts[checker_id])
                         if duplicate_checker_counts[checker_id] != 0
                         else "",
                         str(checker_counts[checker_id] -
                             duplicate_checker_counts[checker_id])))

    print("\n------------------- Bugs grouped by checker ------------------")
    print_table(rows)

    if args.deduplicate:
        total_duplicate_count = 0

        if not args.verbose_duplicates:
            rows = [("Bug hash", "Count (incl. 'first' find)", "Checker ID")]
        else:
            rows = [("Bug hash", "Count (incl. 'first' find)", "Checker ID",
                     "Bug location", "Message")]

        for _, data in duplicate_bughashes.items():
            # Disregard non-duplicate bugs (which only appeared once)
            if data['count'] == 1:
                continue

            total_duplicate_count += data['count'] - 1
            bug_obj = data['bug']

            if not args.verbose_duplicates:
                rows.append((
                    bug_obj['bugHash'],
                    str(data['count']),
                    bug_obj['checkerId']
                ))
            else:
                rows.append((
                    bug_obj['bugHash'],
                    str(data['count']),
                    bug_obj['checkerId'],
                    bug_obj['checkedFile'],
                    bug_obj['checkerMsg']
                ))

        print("\n------------------- Duplicate bugs ------------------")
        print("Total # of duplications (above 'first' find): " +
              str(total_duplicate_count))
        print_table(rows)

    # Calculate metrics based on the BugPath lengths
    if args.deduplicate:
        print("NOTICE: Metrics{0}will ONLY "
              "count DEDUPLICATED! bugs.".
              format((" and histogram " if Histogram else " "))
              )

    calculate_metrics(bug_paths)
    make_histogram(bug_paths)
