Clang Static Analyzer Test Bench
================================

The CSA test bench is a collection of tools that aim to ease
[Clang Static Analyzer](https://clang-analyzer.llvm.org/) development
by finding projects on which certain checks or analyzer engine changes
can be tested and by making the evaluation of the results easier.

Generate Project List utility
-----------------------------

The `generate_project_list.py` utility can help discover relevant projects
on which a check or a change can be tested. It generates a list of projects
that use a certain API or language construct extensively, based on
[SearchCode](https://searchcode.com) query results.

Example usage:

```bash
python generate_project_list.py 'pthread_mutex_t' 'C C++' 5 --output pthread.json
```

The above command will generate a list of 5 projects written in either C or C++
that use `pthread_mutex_t`.

Generate Project List from Debian packages
------------------------------------------

It is also possible to create a project list file from Debian source packages.
The resulting file will contain lots of unsupported projects, so we
advise filtering the list afterward.

```bash
python project_list_from_debian.py -u ftp://ftp.se.debian.org/debian/ --output debian.json
```

We do plan to include additional facilities to help with filtering the list
and building the packages in the future.

Running Experiments
-------------------

The `run_experiments.py` script runs the Clang Static Analyzer on a set of
projects and generates a detailed report from the results. It downloads the
projects specified in a JSON config file from a git repository or a tarball,
infers the build system, generates a build log, runs the Static Analyzer,
collects the output, and generates an HTML report that holds all information
needed to reproduce the same experiment.

Example usage:

```bash
python run_experiments.py --config projects.json --jobs 8
```

Note that the CodeChecker server at the URL specified in the config file needs
to be started separately before running an experiment.

Example configuration:

```json
{
  "projects": [
    {
      "name": "tmux",
      "url": "https://github.com/tmux/tmux.git",
      "tag": "2.6"
    },
    {
      "name": "curl",
      "url": "https://github.com/curl/curl.git"
    }
  ],
  "configurations": [
    {
      "name": "baseline",
      "clang_sa_args": "-Xclang -analyzer-stats"
    },
    {
      "name": "unroll",
      "clang_sa_args": "-Xclang -analyzer-stats -Xclang -analyzer-config -Xclang unroll-loops=true,cfg-loopexit=true"
    }
  ],
  "CodeChecker": {
    "url": "http://localhost:15010/Default"
  }
}
```

Example report:

![Example report](https://raw.githubusercontent.com/Xazax-hun/csa-testbench/master/pictures/report.gif)

### Dependencies

In order for this set of scripts to work, [CodeChecker](https://github.com/Ericsson/codechecker)
needs to be installed and available in the `PATH`. Packages from the
`python_requirements` file should also be installed after CodeChecker's virtual environment was activated.
Example setup below:

```bash
cd path/to/CodeChecker
make venv
source venv/bin/activate
make package
export PATH="$PWD/build/CodeChecker/bin:$PATH"
cd path/to/csa-testbench
pip install -r python_requirements
```

If the `cloc` utility is in the path, the script will also count the lines of
code of the analyzed projects and include them in the final report.

If `clang` is compiled with statistics enabled, the scripts will collect and
include them in the final report.

If [line based code coverage support is present](https://github.com/Xazax-hun/clang/commit/8428aeb89deb0b61a5d0101dc7fab962be0cf6e8),
the script can collect coverage data and include it in the final report.
Note that this requires a patched version of `clang`, this feature is not
upstreamed yet. For the code coverage collection support to work, you need to
have the `MergeCoverage.py` script and `gcovr` utility in the `PATH`.

Add the `"coverage": true` line to the configuration in which you want to record the
coverage:

```json
{
  "projects": [ ... ],
  "configurations": [
    {
      "name": "your_configuration",
      "coverage": true
    },
    ...
  ],
  "CodeChecker": { ... }
}
```

Example coverage report:

![Coverage report](https://raw.githubusercontent.com/Xazax-hun/csa-testbench/master/pictures/coverage.gif)

### Configuration

A minimal configuration should contain a list of projects and a CodeChecker URL.
Each project should at least contain a git or tarball URL and a name. Other
configuration values are optional.

```json
{
  "projects": [
    {
      "name": "tmux",
      "url": "https://github.com/tmux/tmux.git",
      "tag": "2.6",
      "skip": [ "-*/cmd-break-pane.c*", "-*/cmd-bind-key.c*"],
      "configure_command": "sh autogen.sh && ./configure",
      "configurations": [
        {
          "name": "original"
        },
        {
          "name": "with_stats",
          "clang_sa_args": "-Xclang -analyzer-stats"
        }
      ]
    },
    {
      "name": "SQLite",
      "url": "https://www.sqlite.org/2018/sqlite-autoconf-3230000.tar.gz"
    },
    {
      "name": "bitcoin",
      "url": "https://github.com/bitcoin/bitcoin.git",
      "tag": "v0.15.1",
      "clang_sa_args": "-Xclang -analyzer-stats"
    },
    {
      "name": "redis",
      "url": "https://github.com/antirez/redis.git",
      "tag": "727dd43614ec45e23e2dedbba08b393323feaa4f",
      "make_command": "make -j $JOBS",
      "binary_dir": "build"
    },
    {
      "name": "xerces-c",
      "url": "https://github.com/apache/xerces-c.git",
      "prepared": true
    },
    {
      "name": "icu",
      "url": "http://download.icu-project.org/files/icu4c/61.1/icu4c-61_1-src.tgz",
      "source_dir": "source"
    },
    {
      "name": "llvm",
      "url": "https://github.com/llvm-mirror/llvm.git",
      "binary_dir": "build",
      "subprojects": [
        {
          "name": "clang",
          "subdir": "tools/clang",
          "url": "https://github.com/llvm-mirror/clang.git"
        }
      ]
    },
    {
      "name": "zlibconan",
      "package": "zlib/1.2.11@conan/stable",
      "package_type": "conan"
    },
    {
      "name": "zlibvcpkg",
      "package": "zlib",
      "package_type": "vcpkg"
    }
  ],
  "configurations": [
    {
      "name": "original",
      "clang_sa_args": "",
      "clang_tidy_args": "",
      "analyze_args": "",
      "store_args": "",
      "clang_path": ""
    },
    {
      "name": "with_stats",
      "clang_sa_args": "-Xclang -analyzer-stats",
      "coverage": true
    }
  ],
  "charts": ["Coverage", "Duration", "Result count"],
  "CodeChecker": {
    "url": "http://localhost:8001/Default",
    "analyze_args": "",
    "store_args": "",
    "analyzers": "clangsa clang-tidy"
  }
}
```

#### Optional configuration values

* **configurations**: It is possible to specify multiple `clang` configurations,
in which case each project will be analyzed using each of the `clang`
configurations. The global configuration entry applies to each project. A
configuration entry local to a project will overwrite the global settings. Each
configuration should have at least a name.
* **clang_sa_args**: Arguments passed to `clang` (not `cc1`). The entry under
`CodeChecker` applies to all projects and is appended to the final list of
arguments. Entries under the projects apply to each configuration.
* **analyze_args**: Arguments passed to the `CodeChecker analyze` command. It works
the same way as `clang_sa_args`.
* **analyzers**: Which analyzers to run. Defaults to Clang Static Analyzer only.
* **store_args**: Arguments passed to the `CodeChecker store` command. It works the
same way as `clang_sa_args`.
* **coverage**: If set to true, precise coverage information will be recorded.
* **clang_path**: The directory containing the `clang` binaries. This can be
useful for testing `clang` before and after a patch is applied.
* **tag**: A commit hash or tag name of a project that will be checked out. It
can be useful to make the experiments reproducible, i.e., always test with the
same code.
* **configure_command**: If this configuration value is set, the script will
issue this command before building the project. It will not appear in the build
log. The working directory will be the root of the project. The string `$JOBS`
will be replaced with the number of jobs specified in the command line.
* **make_command**: If this configuration value is set, the script will not try
to infer the build system, but will invoke the `make` command specified in this
value. The working directory will be the root of the project. The string `$JOBS`
will be replaced with the number of jobs specified in the command line.
If this configuration value is set, but to an empty string, then no build
invocation will happen.
* **binary_dir**: The binary dir can be specified for out-of-tree builds. It can
be relative to the project root. Currently, this is only supported for `cmake`
projects.
* **source_dir**: If the source code and the related build files of the project
are not in the project root, this directory can specify the location.
* **prepared**: If this configuration value is set to `true`, the script will not
attempt to check out the project and will not attempt to create a build log.
It will assume that a folder with the name of the project exists and contains a
`compile_commands.json` file. It will use that file for the analysis of the
project.
* **submodules**: If this configuration value is set to `true`, the script will
also initialize submodules after checking the repository out.
* **charts**: The list of statistics that should be charted.
* **subprojects**: List of other repositories to check out before building into the
**subdir** directory.
* **package_type**: package manager to build a C++ package.
[Conan](https://conan.io/) and [vcpkg](https://docs.microsoft.com/en-us/cpp/vcpkg) are supported.
* **skip**: specify the [skiplist](https://github.com/Ericsson/codechecker/blob/master/docs/user_guide.md#skip)
for a project. Each element in the list corresponds to a line in the generated skiplist file.

### Limitations

These scripts will not figure out the dependencies of a project. It is the
user's responsibility to make sure that the projects in the configuration file
can be compiled on the machine on which the experiments are run.

Measuring bug path length statistics
------------------------------------

The `bug_stats.py` file can be used to calculate descriptive statistics from the
results of the analysis. It takes the "product URL" argument of a **running**
CodeChecker server (`--url http://localhost:8001/Default`) and some project
names (`--name Project1 Project2`, or `--all`) and generates statistics and
histograms for each project given.

```bash
bug_stats.py --url http://example.org:8080/MyProduct --name my_run
```

<p align="center"><img src="https://raw.githubusercontent.com/Xazax-hun/csa-testbench/master/pictures/bug_stats.png" width="70%" alt="Example bug statistics" /></p>

This script also supports generating statistics from the difference of two runs,
based on the bug reports presented by `CodeChecker cmd diff`:

```bash
bug_stats.py --url http://example.org:8080/MyProduct --diff \
  --basename baseline --newname csa_patched --new
```

Other Tips and Tricks
---------------------

### CReduce diffs

[CReduce](https://embed.cs.utah.edu/creduce/) is a useful tool to get minimal reproducers for compiler bugs.
It is also great for getting minimal reproducers for assertion fails or crashes of static analysis tools.
Moreover, we can use this tool to get minimal regressions or improvements between two versions of an
analysis engine.

This section is a small example of how to do it for the Clang Static Analyzer.

1. Create the file to reduce

  Create a preprocessed file for which the two versions of the analyzer give different results

2. Create the reduce script

  Create a script that executes both versions of the analyzer on the preprocessed file and compares the output.
  Note that this script should return 0 if a transformation of creduce preserved the property we want, and non-zero
  otherwise. In case one of the implementations is crashed, we should return non-zero since our goal is not to get
  minimal crash reproducers.
  
  ```bash
  # reduce.sh
  set -e
  /path/to/basline/clang --analyze preprocessed.c 2> out1.txt
  /path/to/modified/clang --analyze preprocessed.c 2> out2.txt
  
  ! cmp --silent out1.txt out2.txt
  ```
  
3. Execute creduce and wait for the results

  ```bash
  creduce reduce.sh preprocessed.c --n 8
  ```

Note that the final result might contain a warning that differs from the initials.
