Clang Static Analyzer Test Bench
================================

The main purpose of this project is to make the development of the Clang
Static Analyzer easier. It consists of a collection of tools to help
finding projects to test certain checks or analyzer engine changes on
and to evaluate the results.

Generate Project List utility
-----------------------------

The `generate_project_list.py` utility can help to discover projects to
test a check on. It is using `https://searchcode.com` API. It is suitable
for getting a list of projects that are using a certain API or language
construct extensively.

Example usage:

```bash
python gen_project_list.py 'pthread_mutex_t' 'C C++' 5 −−output pthread.json
```

Itt will generate a list of 5 projects which can be both C or C++ projects that
are using `pthread_mutex_t`.

Running Experiments
-------------------

There is a `run_experiments.py` script to run the Clang Static Analyzer on a
set of projects and create a report. This script will download the projects
from a git repository, figure out the build system, generate a build log,
run the Static Analyzer, collect the output, and generate a report.

Example usage:

```bash
python run_experiments.py --config projects.json --jobs 8
```

Note that, the CodeChecker server at the URL specified in the config needs to
be started separately before running an experiment.

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
      "name": "original",
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

![Example report](https://raw.githubusercontent.com/Xazax-hun/csa-testbench/master/pictures/report.png)

### Dependencies

In order for this set of scripts to work, [CodeChecker](https://github.com/Ericsson/codechecker)
should be installed and available in the `PATH`. The packages from the
`python_requirements` file should also be installed.

If `cloc` utility is in the path the script will also count the lines of
code of the analyzed projects and include it in the final report.

If `clang` is compiled with the statistics enabled the scripts will collect
this data and include in the final report.

If [line based code coverage support is present](https://github.com/Xazax-hun/clang/commit/8428aeb89deb0b61a5d0101dc7fab962be0cf6e8)
the script will collect coverage data and include it in the final report.
Note that, this requires a patched version of clang, this support is not
upstreamed yet. For the code coverage collection support to work
you need to have the `MergeCoverage.py` script and `gcovr` utility
in the `PATH`.

Example coverage report:

![Coverage report](https://raw.githubusercontent.com/Xazax-hun/csa-testbench/master/pictures/coverage.png)

### Configuration

There is an example configuration below. A minimal configuration should contain a list
of projects and a CodeChecker url. Each project should at least contain a git url and
a name. Every other configuration value is optional.

```json
{
  "projects": [
    {
      "name": "tmux",
      "url": "https://github.com/tmux/tmux.git",
      "tag": "2.6",
      "configurations": [
        {
          "name": "original",
          "clang_sa_args": "",
          "analyze_args": "",
          "store_args": "",
          "clang_path": ""
        },
        {
          "name": "with_stats",
          "clang_sa_args": "-Xclang -analyzer-stats"
        }
      ]
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
      "make_command": "make"
    },
    {
      "name": "xerces-c",
      "url": "https://github.com/apache/xerces-c.git",
      "prepared": true
    }
  ],
  "configurations": [
    {
      "name": "original",
      "clang_sa_args": "",
      "analyze_args": "",
      "store_args": "",
      "clang_path": ""
    },
    {
      "name": "with_stats",
      "clang_sa_args": "-Xclang -analyzer-stats"
    }
  ],
  "CodeChecker": {
    "url": "http://localhost:8001/Default",
    "analyze_args": "",
    "store_args": ""
  }
}
```

#### Optional configuration values

* **Configurations**: It is possible to specify multiple configurations. If multiple configurations are
specified all project will be analyzes for each configuration. The global configuration
entry applies to every project. A configuration entry local to a project will overwrite
the global settings. Every configuration should have at least a name.
* **clang_sa_args**: Arguments passed to Clang (not cc1). The entry in CodeChecker applies to
all projects and appended to the final list of arguments. The entries in the project are
apply to every configurations.
* **analyze_args**: Arguments passed to the CodeChecker analyze command. Works the same way as
`analyzer_args`.
* **store_args**: Arguments passed to the CodeChecker store command. Works the same way as
`analyzer_args`.
* **clang_path**: The directory where the Clang binaries are. This can be useful to test Clang
before and after a patch is applied.
* **tag**: A commit hash or tag name of a project that will be checked out. It can be
useful to make the experiments reproducible, i.e.: always testing with the same code.
* **make_command**: If this configuration value is set the script will not try to 
infer the build system but invoke the make command specified in this value.
* **prepared**: If this configuration value is specified, the script will not attempt to
check out the project and not attempt to create a build log. It will assume that a folder
with the name of the project exist and contains a `compile_commands.json`. It will use that
file to analyze the project.

### Limitations

These scripts will not figure out the dependencies of a project. It is the user's job
to make sure the projects in the configuration file can be compiled on the machine where
the experiments are run.
