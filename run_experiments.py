import argparse as ap
import json
import multiprocessing
import os
import shlex
import shutil
import subprocess as sp
import sys
import tempfile

TESTBENCH_ROOT = os.path.dirname(os.path.abspath(__file__))


def load_config(filename):
    """Load all information from the specified config file."""

    config_path = os.path.join(TESTBENCH_ROOT, filename)

    with open(config_path, 'r') as config_file:
        config_dict = json.loads(config_file.read())

    if not config_dict:
        sys.stderr.write("[Error] Empty config file.\n")
        sys.exit(1)

    return config_dict


def run_command(cmd):
    """Wrapper function to handle running system commands."""

    proc = sp.Popen(shlex.split(cmd), stdin=sp.PIPE, stdout=sp.PIPE,
                    stderr=sp.PIPE)

    stdout, err = proc.communicate()

    if proc.returncode is not 0:
        sys.stderr.write("[ERROR] %s\n" % str(err))

    return proc.returncode, stdout, err


def clone_project(project, project_dir):
    """Clone a single project.

    Its version is specified by a version tag or a commit hash
    found in the config file.

    If a project already exists, we simply overwrite it.
    """

    # If the project folder already exists, remove it.
    if os.path.isdir(project_dir):
        shutil.rmtree(project_dir)

    # If there is no tag specified, we clone the master branch.
    # This presumes that a master branch exists.
    if 'tag' not in project:
        project['tag'] = 'master'

    # Check whether the project config contains a version tag or a commit hash.
    try:
        int(project['tag'], base=16)
        commit_hash = True
    except:
        commit_hash = False

    # If the 'tag' value is a version tag, we can use shallow cloning.
    # With a commit hash, we need to clone everything and then checkout
    # the specified commit.
    cmd = {
        'clone': 'git clone %s --depth 1 %s' % (project['url'], project_dir)}

    if commit_hash:
        cmd['checkout'] = 'git --git-dir=%s/.git --work-tree=%s checkout %s' \
                          % (project_dir, project_dir, project['tag'])
    else:
        cmd['clone'] += ' --branch %s --single-branch' % project['tag']

    # Clone project.
    sys.stderr.write("Checking out '%s'...\n" % project['name'])
    clone_failed, _, _ = run_command(cmd['clone'])
    if clone_failed:
        return False

    # Checkout specified commit if needed.
    if 'checkout' in cmd:
        checkout_failed, _, _ = run_command(cmd['checkout'])
        if checkout_failed:
            return False

    cloc_failed, stdout, _ = run_command("cloc %s --json" % project_dir)
    if not cloc_failed:
        try:
            cloc_json_out = json.loads(stdout)
            project["LOC"] = cloc_json_out["SUM"]["code"]
            print("LOC calculated.")
        except:
            pass

    return True


def identify_build_system(project_dir):
    """Identifies the build system of a project.

    Used heuristics:
        - If there's a 'CMakeLists.txt' file at the project root: 'cmake'.
        - If there's an 'autogen.sh' script at the project root: run it.
        - If there's a 'configure' script at the project root: run it,
          then return 'makefile'.

    FIXME: If no build system found, should we apply the same
           heuristics for src subfolder if exists?

    The actual build-log generation happens in main().
    """

    project_files = os.listdir(project_dir)
    if not project_files:
        sys.stderr.write("[ERROR] No files found in '%s'.\n\n" % project_dir)
        return None

    if 'CMakeLists.txt' in project_files:
        return 'cmake'

    if 'Makefile' in project_files:
        return 'makefile'

    if 'autogen.sh' in project_files:
        # Autogen needs to be executed in the project's root directory.
        os.chdir(project_dir)
        autogen_failed, _, _ = run_command("sh autogen.sh")
        os.chdir(os.path.dirname(project_dir))
        if autogen_failed:
            return None

    # Need to re-list files, as autogen might have generated a config script.
    project_files = os.listdir(project_dir)

    if 'configure' in project_files:
        os.chdir(project_dir)
        configure_failed, _, _ = run_command("./configure")
        os.chdir(os.path.dirname(project_dir))
        if configure_failed:
            return None
        return 'makefile'

    sys.stderr.write("[ERROR] Build system cannot be identified.\n\n")
    return None


def check_logged(projects_root):
    """Post-script cleanup.

    Removes any projects that have an empty build-log JSON file
    at the end of the script.

    FIXME: instead of listing all directories only list the ones
           that were in the config file. Or move the check to
           log_project.
    """

    projects = os.listdir(projects_root)
    for project in projects:
        log = os.path.join(projects_root, project, 'compile_commands.json')
        if os.path.getsize(log) == 0:
            shutil.rmtree(os.path.join(projects_root, project))
    return os.listdir(projects_root)


def log_project(project_dir, num_jobs):
    # Identify build system (CMake / autotools)
    # + run configure script if needed.
    build_sys = identify_build_system(project_dir)
    if not build_sys:
        shutil.rmtree(project_dir)
        return False
    if build_sys == 'cmake':
        # Generate 'compile_commands.json' using CMake.
        cmd = "cmake -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -B%s -H%s" \
              % (project_dir, project_dir)
        cmake_failed, _, _ = run_command(cmd)
        if cmake_failed:
            shutil.rmtree(project_dir)
            return False
        sys.stderr.write("Build log generated successfully.\n\n")
        return True
    if build_sys == 'makefile':
        # Generate 'compile_commands.json' using CodeChecker.
        json_path = os.path.join(project_dir, "compile_commands.json")
        cmd = "CodeChecker log -b 'make -C%s -j%d' -o %s" \
              % (project_dir, num_jobs, json_path)
        cc_failed, _, _ = run_command(cmd)
        if cc_failed:
            shutil.rmtree(project_dir)
            return False
        sys.stderr.write("Build log generated successfully.\n\n")
    return True


def check_project(project, project_dir, config, num_jobs):
    json_path = os.path.join(project_dir, "compile_commands.json")
    result_path = os.path.join(project_dir, "cc_results")
    coverage_dir = os.path.join(result_path, "coverage")
    cmd = ("CodeChecker analyze '%s' -j%d -o %s -q " +
           "--analyzers clangsa --capture-analysis-output") \
        % (json_path, num_jobs, result_path)
    args_file, filename = tempfile.mkstemp()
    os.write(args_file, " -Xclang -analyzer-config -Xclang record-coverage=%s "
             % coverage_dir)
    if "clang_sa_args" in project:
        os.write(args_file, project["clang_sa_args"])
    cmd += " --saargs " + filename
    run_command(cmd)
    os.close(args_file)
    sys.stderr.write("Analysis is done.\n\n")
    tag = project["tag"] if "tag" in project else ""
    name = project["name"] + "_" + tag
    cmd = "CodeChecker store %s --url '%s' -n %s --tag %s" \
          % (result_path, config["CodeChecker"]["url"], name, tag)
    run_command(cmd)
    sys.stderr.write("Store is done.\n\n")


def main():
    parser = ap.ArgumentParser(description="Run differential analysis " +
                                           "experiment on a set of projects.",
                               formatter_class=ap.RawTextHelpFormatter)
    parser.add_argument("--config", metavar="FILE",
                        default='test_config.json',
                        help="JSON file holding a list of projects")
    parser.add_argument("--jobs", metavar="JOBS", type=int,
                        default=multiprocessing.cpu_count(),
                        help="number of jobs")
    args = parser.parse_args()

    try:
        run_command("CodeChecker version")
    except OSError as oerr:
        sys.stderr.write(
            "[ERROR] CodeChecker is not available as a command.\n")
        sys.exit(1)

    if args.jobs < 1:
        sys.stderr.write(
            "[ERROR] The number of jobs must be a positive integer.\n")

    config_path = os.path.join(TESTBENCH_ROOT, args.config)
    sys.stderr.write("\nUsing configuration file '%s'.\n" % config_path)
    config = load_config(config_path)
    sys.stderr.write("Number of projects: %d.\n\n" % len(config['projects']))

    projects_root = os.path.join(TESTBENCH_ROOT, 'projects')
    if not os.path.isdir(projects_root):
        os.mkdir(projects_root)

    for project in config['projects']:
        project_dir = os.path.join(projects_root, project['name'])

        clone_success = clone_project(project, project_dir)
        if not clone_success:
            shutil.rmtree(project_dir)
            continue

        if not log_project(project_dir, args.jobs):
            continue

        check_project(project, project_dir, config, args.jobs)

        print("Done analyzing %s (%s LOC)" % (project["name"],
                                 project["LOC"] if "LOC" in project else "?"))

    logged_projects = check_logged(projects_root)
    sys.stderr.write("\n# of analyzed logged projects: %d / %d\n\n"
                     % (len(logged_projects), len(config['projects'])))


if __name__ == '__main__':
    main()
