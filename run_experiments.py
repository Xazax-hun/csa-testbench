#!/usr/bin/env python3
import argparse as ap
import json
import logging
import multiprocessing
import os
import re
import shlex
import shutil
import subprocess as sp
import sys
import tarfile
import tempfile
import zipfile
from collections import Counter
from datetime import datetime, timedelta
from distutils.dir_util import copy_tree
from pathlib import Path
from urllib.request import urlretrieve

from generate_stat_html import HTMLPrinter
from summarize_gcov import summarize_gcov
from summarize_sa_stats import summ_stats


def make_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def load_config(config_path):
    with open(config_path, "r", encoding="utf-8", errors="ignore") \
        as config_file:
        config_dict = json.loads(config_file.read())
    if not config_dict:
        logging.error("Empty config file.")
        sys.exit(1)
    return config_dict


def run_command(cmd, print_error=True, cwd=None, env=None, shell=False):
    args = shlex.split(cmd) if not shell else cmd
    try:
        proc = sp.Popen(args, stdin=sp.PIPE, stdout=sp.PIPE,
                        stderr=sp.PIPE, cwd=cwd, env=env, shell=shell,
                        encoding="utf-8", universal_newlines=True,
                        errors="ignore")
        stdout, stderr = proc.communicate()
        retcode = proc.returncode
    except FileNotFoundError:
        retcode = 2
        stdout, stderr = "", ""
    if retcode != 0 and print_error:
        output = stderr if stderr else stdout
        logging.error("%s\n", str(output))
    return retcode, stdout, stderr


def count_lines(project, project_dir):
    failed, stdout, _ = run_command(
        'cloc "%s" --json --not-match-d="cc_results"' % project_dir, False)
    if not failed:
        try:
            cloc_json_out = json.loads(stdout)
            project["LOC"] = cloc_json_out["SUM"]["code"]
        except:
            pass
    logging.info("[%s] LOC: %s.", project['name'], project.get('LOC', '?'))


def clone_project(project, project_dir, source_dir, is_subproject=False):
    """Clone a single project.

    Its version is specified by a version tag or a commit hash
    found in the config file.

    If a project already exists, we simply overwrite it.
    """
    if 'prepared' in project:
        count_lines(project, project_dir)
        return True

    if os.path.isdir(project_dir):
        shutil.rmtree(project_dir)

    project_str = "subproject" if is_subproject else "project"
    logging.info("[%s] Checking out %s... ", project['name'], project_str)

    # Check if tarball is provided.
    # TODO: support zip files.
    if project['url'].endswith((".tar.gz", ".tar.xz", ".tar.lz", ".tgz",
                                ".tbz", ".tlz", ".txz")):
        path, _ = urlretrieve(project['url'])
        with tarfile.open(path) as tar:
            tar.extractall(project_dir)
        content = os.listdir(project_dir)
        # If the tar contains a single directory, move contents up.
        if len(content) == 1:
            inner = os.path.join(project_dir, content[0])
            # shutil.copytree fails to copy to existing dir.
            copy_tree(inner, project_dir)
            shutil.rmtree(inner)
        count_lines(project, project_dir)
        return True

    # If there is no tag specified, we clone the master branch.
    # This presumes that a master branch exists.
    project['tag'] = project.get('tag', 'master')

    try:
        int(project['tag'], base=16)
        commit_hash = True
    except ValueError:
        commit_hash = False

    # If the 'tag' value is a version tag, we can use shallow cloning.
    # With a commit hash, we need to clone everything and then checkout
    # the specified commit.
    cmd = {'clone': 'git clone %s "%s"' % (project['url'], project_dir)}

    if commit_hash:
        cmd['checkout'] = 'git -C "%s" checkout %s' % (
            project_dir, project['tag'])
    else:
        cmd['clone'] += ' --depth 1 --branch %s --single-branch' % \
                        project['tag']

    sys.stdout.flush()
    clone_failed, _, clone_err = run_command(cmd['clone'], print_error=False)
    if clone_failed and 'master' in str(clone_err):
        clone_failed, _, _ = run_command(
            'git clone %s "%s"' % (project['url'], project_dir))
    if clone_failed:
        return False
    if 'checkout' in cmd:
        checkout_failed, _, _ = run_command(cmd['checkout'])
        if checkout_failed:
            return False

    for sub_project in project.get("subprojects", []):
        sub_dir = os.path.join(source_dir, sub_project["subdir"])
        if not clone_project(sub_project, sub_dir, sub_dir, True):
            return False

    if not is_subproject:
        count_lines(project, project_dir)

    return True


def identify_build_system(project_dir, configure):
    """Identifies the build system of a project.

    Used heuristics:
        - If there's a 'CMakeLists.txt' file at the project root: 'cmake'.
        - If there's an 'autogen.sh' script at the project root: run it.
        - If there's a 'configure' script at the project root: run it,
          then return 'makefile'.

    FIXME: If no build system found, should we apply the same
           heuristics for src subfolder if exists?
    """

    project_files = os.listdir(project_dir)
    if not project_files:
        logging.error("No files found in '%s'.\n", project_dir)
        return None

    if 'CMakeLists.txt' in project_files:
        return 'cmake'

    if 'Makefile' in project_files:
        return 'makefile'

    # When there is a custom configure command,
    # fall back to make files.
    if not configure:
        return 'makefile'

    if 'autogen.sh' in project_files:
        # Autogen needs to be executed in the project's root directory.
        autogen_failed, _, _ = run_command("sh autogen.sh", cwd=project_dir)
        if autogen_failed:
            return None

    # Need to re-list files, as autogen might have generated a config script.
    project_files = os.listdir(project_dir)

    if 'configure' in project_files:
        configure_failed, _, _ = run_command("./configure", cwd=project_dir)
        if configure_failed:
            return None
        return 'makefile'

    logging.error("Build system cannot be identified.")
    return None


def check_logged(projects_root, projects):
    """ Count successfully checked projects."""

    configured_projects = {project["name"] for project in projects}
    projects = os.listdir(projects_root)
    num = 0
    for project in projects:
        if os.path.isfile(os.path.join(projects_root, project)):
            continue
        if project not in configured_projects:
            continue
        num += 1
    return num


def get_compilation_database(project, project_dir):
    binary_dir = project_dir
    if "binary_dir" in project:
        binary_dir = os.path.join(binary_dir, project["binary_dir"])
        make_dir(binary_dir)
    json_path = os.path.join(binary_dir, "compile_commands.json")
    return json_path, binary_dir


def log_project(project, project_dir, num_jobs):
    if 'prepared' in project:
        return True
    configure = True
    if 'configure_command' in project:
        configure = False
        project['configure_command'] = \
            project['configure_command'].replace("$JOBS", str(num_jobs))
        _, _, _ = run_command(project['configure_command'],
                              True, project_dir, shell=True)
    if 'make_command' in project:
        build_sys = 'userprovided'
    else:
        build_sys = identify_build_system(project_dir, configure)
    failed = not build_sys

    logging.info("[%s] Generating build log... ", project['name'])
    json_path, binary_dir = get_compilation_database(project, project_dir)
    if build_sys == 'cmake':
        cmd = 'cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -B"%s" -H"%s"' \
              % (binary_dir, project_dir)
        failed, _, _ = run_command(cmd, True, binary_dir)
    elif build_sys == 'makefile':
        cmd = "CodeChecker log -b 'make -j%d' -o \"%s\"" \
              % (num_jobs, json_path)
        failed, _, _ = run_command(cmd, True, project_dir)
    elif build_sys == 'userprovided':
        project['make_command'] = \
            project['make_command'].replace("$JOBS", str(num_jobs))
        cmd = "CodeChecker log -b '%s' -o \"%s\"" \
              % (project['make_command'], json_path)
        failed, _, _ = run_command(cmd, True, project_dir, shell=True)
    if failed:
        shutil.rmtree(project_dir)
        return False

    return True


def collect_args(arg_name, configuration_sources):
    return " ".join([conf[arg_name] if arg_name in conf else ""
                     for conf in configuration_sources])


def update_path(path, env=None):
    if env is None:
        env = os.environ
    env["PATH"] = path + ":" + env["PATH"]
    return env


def build_package(project, project_dir, jobs):
    logging.info("[%s] Generating build log... ", project['name'])
    make_dir(project_dir)
    json_path, _ = get_compilation_database(project, project_dir)
    if project["package_type"] == "vcpkg":
        run_command("vcpkg remove %s" % project["package"], True, project_dir)
        cmd = "CodeChecker log -b 'vcpkg install %s' -o \"%s\"" \
            % (project["package"], json_path)
        failed, _, _ = run_command(cmd, True, project_dir)
        return not failed
    if project["package_type"] == "conan":
        run_command("conan install %s" % project["package"], True, project_dir)
        cmd = "CodeChecker log -b 'conan install %s --build' -o \"%s\"" \
            % (project["package"], json_path)
        failed, _, _ = run_command(cmd, True, project_dir)
        return not failed
    logging.info("[%s] Unsupported package.", project['name'])
    return False


def check_project(project, project_dir, config, num_jobs):
    """Analyze project and store the results with CodeChecker."""

    json_path, _ = get_compilation_database(project, project_dir)
    if "configurations" not in project:
        project["configurations"] = config.get("configurations",
                                               [{"name": ""}])
    _, skippath = tempfile.mkstemp()
    with open(skippath, 'w', encoding="utf-8", errors="ignore") \
        as skipfile:
        skipfile.write("\n".join(project.get("skip", [])))
    for run_config in project["configurations"]:
        result_dir = "cc_results"
        if run_config["name"]:
            result_dir += "_" + run_config["name"]
        result_path = os.path.join(project_dir, result_dir)
        run_config["result_path"] = result_path
        args_file, filename = tempfile.mkstemp(text=True)
        with open(args_file, 'w') as args:
            if run_config.get("coverage", False):
                coverage_dir = os.path.join(result_path, "coverage")
                run_config["coverage_dir"] = coverage_dir
                args.write(" -Xclang -analyzer-config "
                           "-Xclang record-coverage=%s " % coverage_dir)
            conf_sources = [config["CodeChecker"], project, run_config]
            args.write(collect_args("clang_sa_args", conf_sources))
        tag = project.get("tag")
        name = project["name"]
        if tag:
            name += "_" + tag
        if run_config["name"]:
            name += "_" + run_config["name"]
        run_config["full_name"] = name

        logging.info("[%s] Analyzing project... ", name)
        env = None
        if "clang_path" in run_config:
            env = update_path(run_config["clang_path"])
        _, version_string, _ = run_command("clang --version", env=env)
        run_config["analyzer_version"] = version_string
        analyzers = config["CodeChecker"].get("analyzers", "clangsa")
        cmd = ("CodeChecker analyze '%s' -j%d -o '%s' -q " +
               "--analyzers %s --capture-analysis-output") \
            % (json_path, num_jobs, result_path, analyzers)
        cmd += " --saargs %s " % filename
        cmd += " --skip %s " % skippath
        cmd += collect_args("analyze_args", conf_sources)
        run_command(cmd, print_error=True, env=env)

        logging.info("[%s] Done. Storing results...", name)
        cmd = "CodeChecker store '%s' --url '%s' -n %s " \
              % (result_path, config["CodeChecker"]["url"], name)
        if tag:
            cmd += " --tag %s " % tag
        cmd += collect_args("store_args", conf_sources)
        run_command(cmd, print_error=True, env=env)
        logging.info("[%s] Results stored.", name)

    os.remove(skippath)


class RegexStat:
    def __init__(self, regex):
        self.regex = re.compile(regex)
        self.counter = Counter()


def process_success(path, statistics=None):
    if statistics is None:
        statistics = dict()
    statistics.update({
        "warnings": RegexStat(r'warning: (.+)')
    })
    if not os.path.exists(path):
        return statistics
    for name in os.listdir(path):
        if not name.endswith(".txt"):
            continue
        with open(os.path.join(path, name), encoding="utf-8",
                  errors="ignore") as compiler_output:
            for line in compiler_output:
                for _, stat in statistics.items():
                    match = stat.regex.search(line)
                    if match:
                        stat.counter[match.group(1)] += 1
    return statistics


def process_failures(path, statistics=None):
    if statistics is None:
        statistics = dict()
    statistics.update({
        "warnings": RegexStat(r'warning: (.+)'),
        "compilation errors": RegexStat(r'error: (.+)'),
        "assertions": RegexStat(r'(Assertion.+failed\.)'),
        "unreachable": RegexStat(r'UNREACHABLE executed at (.+)')
    })
    if not os.path.exists(path):
        return 0, statistics
    failures = 0
    for name in os.listdir(path):
        if not name.endswith(".zip"):
            continue
        failures += 1
        full_path = os.path.join(path, name)
        with zipfile.ZipFile(full_path) as archive, \
                archive.open("stderr") as stderr:
            for line in stderr:
                for _, stat in statistics.items():
                    match = stat.regex.search(line)
                    if match:
                        stat.counter[match.group(1)] += 1

    return failures, statistics


def create_link(url, text):
    return '<a href="%s">%s</a>' % (url, text)


def post_process_project(project, project_dir, config, printer):
    _, stdout, _ = run_command(
        "CodeChecker cmd runs --url %s -o json" % config['CodeChecker']['url'])
    runs = json.loads(stdout)
    project_stats = {}
    fatal_errors = 0
    for run_config in project["configurations"]:
        cov_result_html = None
        if run_config.get("coverage", False) and \
           os.path.isdir(run_config["coverage_dir"]):
            cov_result_path = os.path.join(
                run_config["result_path"], "coverage_merged")
            try:
                run_command("MergeCoverage.py -i '%s' -o '%s'" %
                            (run_config["coverage_dir"], cov_result_path))
            except OSError:
                logging.warning("MergeCoverage.py is not found in path.")
            cov_result_html = os.path.join(
                run_config["result_path"], "coverage.html")
            try:
                run_command(
                    "gcovr -k -g '%s' --html --html-details -r '%s' -o '%s'" %
                    (cov_result_path, project_dir, cov_result_html))
            except OSError:
                logging.warning("gcovr is not found in path.")
            cov_summary = summarize_gcov(cov_result_path)
            cov_summary_path = os.path.join(
                run_config["result_path"], "coverage.txt")
            with open(cov_summary_path, "w", encoding="utf-8",
                      errors="ignore") as cov_file:
                cov_file.write(json.dumps(cov_summary, indent=2))

        stats_dir = os.path.join(run_config["result_path"], "success")
        failed_dir = os.path.join(run_config["result_path"], "failed")

        # Statistics from the Analyzer engine (if enabled).
        stats = summ_stats(stats_dir, False)

        # Additional statistics.
        stats["Analyzer version"] = run_config["analyzer_version"]
        if cov_result_html:
            stats["Detailed coverage link"] = create_link(
                cov_result_html, "coverage")
            stats["Coverage"] = cov_summary["overall"]["coverage"]
        for run in runs:
            if run_config['full_name'] in run:
                run = run[run_config['full_name']]
                break
        stats["Result count"] = run["resultCount"]
        stats["Duration"] = timedelta(seconds=run["duration"])
        stats["CodeChecker link"] = \
            create_link("%s/#run=%s&tab=%s" % (config['CodeChecker']['url'],
                                               run_config['full_name'],
                                               run_config['full_name']),
                        "CodeChecker")
        stats["Successfully analyzed"] = \
            len([name for name in os.listdir(run_config["result_path"])
                 if name.endswith(".plist")])
        success_stats = process_success(stats_dir)
        failure_num, failure_stats = process_failures(failed_dir)
        failure_stats["warnings"].counter += success_stats["warnings"].counter
        stats["Failed to analyze"] = failure_num
        for name, stat in failure_stats.items():
            stats["Number of %s" % name] = sum(stat.counter.values())
            if stats["Number of %s" % name] > 0:
                top = ["%s [%d]" % x for x in stat.counter.most_common(5)]
                stats["Top %s" % name] = "<br>\n".join(top)
        fatal_errors += sum(failure_stats["assertions"].counter.values()) + \
                        sum(failure_stats["unreachable"].counter.values())
        stats["Lines of code"] = project.get("LOC", '?')

        disk_usage = 0
        for path, _, files in os.walk(run_config['result_path']):
            for f in files:
                disk_usage += os.path.getsize(os.path.join(path, f))

        stats["Disk usage"] = disk_usage

        project_stats[run_config["name"]] = stats

    printer.extend_with_project(project["name"], project_stats)
    logging.info("[%s] Postprocessed.", project['name'])
    return fatal_errors


def main():
    logging.basicConfig(format='%(asctime)s (%(levelname)s) %(message)s',
                        datefmt='%H:%M:%S', level=logging.INFO)
    parser = ap.ArgumentParser(description="Run differential analysis "
                               "experiment on a set of projects.",
                               formatter_class=ap.RawTextHelpFormatter)
    parser.add_argument("--config", metavar="FILE",
                        default='test_config.json',
                        help="JSON file holding a list of projects")
    parser.add_argument("-j", "--jobs", metavar="JOBS", type=int,
                        default=multiprocessing.cpu_count(),
                        help="number of jobs")
    parser.add_argument("--fail-on-assert", dest='fail_on_assert',
                        action='store_true',
                        help="Return with non-zero error-code "
                             "when Clang asserts")
    parser.add_argument("-o", "--output", metavar="RESULT_DIR",
                        dest='output', default='projects',
                        help="Directory where results should be generated")
    args = parser.parse_args()

    try:
        _, cc_ver, _ = run_command("CodeChecker version")
    except OSError:
        logging.error("CodeChecker is not available as a command.")
        sys.exit(1)

    if args.jobs < 1:
        logging.error("Invalid number of jobs.")

    logging.info("Using configuration file '%s'.", args.config)
    config = load_config(args.config)
    config["CodeChecker version"] = cc_ver
    script_dir = os.path.dirname(os.path.realpath(__file__))
    _, out, _ = run_command("git rev-parse HEAD", False, cwd=script_dir)
    config["Script version"] = out
    config["Script args"] = " ".join(sys.argv)
    logging.info("Number of projects to process: %d.\n", len(config['projects']))

    projects_root = os.path.abspath(args.output)
    make_dir(projects_root)

    stats_html = os.path.join(projects_root, "stats.html")
    with HTMLPrinter(stats_html, config) as printer:

        for project in config['projects']:
            project_dir = os.path.join(projects_root, project['name'])
            source_dir = os.path.join(project_dir,
                                      project.get('source_dir', ''))
            package = project.get('package')
            if package:
                build_package(project, project_dir, args.jobs)
            else:
                if not clone_project(project, project_dir, source_dir):
                    try:
                        shutil.rmtree(project_dir)
                    except:
                        pass
                    continue
                if not log_project(project, source_dir, args.jobs):
                    continue
            check_project(project, source_dir, config, args.jobs)
            fatal_errors = post_process_project(project, source_dir, config,
                                                printer)
            if fatal_errors > 0 and args.fail_on_assert:
                logging.error('Stopping after assertion failure.')
                sys.exit(1)

    logged_projects = check_logged(projects_root, config['projects'])
    logging.info("\nNumber of analyzed projects: %d / %d\n"
                 "Results can be viewed at '%s'.\n"
                 "Stats can be viewed at 'file://%s'.",
                 logged_projects, len(config['projects']),
                 config['CodeChecker']['url'], stats_html)


if __name__ == '__main__':
    main()
