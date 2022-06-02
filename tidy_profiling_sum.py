#!/usr/bin/env python3
import argparse
from collections import OrderedDict
import copy
import csv
import hashlib
import itertools
import json
import logging
import os
import sys
from typing import Optional

import generate_stat_html as stat_html

logging.basicConfig(format='%(asctime)s (%(levelname)s) %(message)s',
                    datefmt='%H:%M:%S', level=logging.INFO)


# To generate Tidy check profiling results and charts, perform
# 'run_experiments.py' with the configuration file, for each configuration,
# specifying the following "clang_tidy_args":
#
#     --enable-check-profile --store-check-profile=<name of the configuration>
#
# For each configuration entry, a custom "tidy_chart_title" can be specified.


try:
    import plotly
    from plotly import express as pex
    from plotly import graph_objects as pgo
    from plotly import subplots as psp

    import pandas as __pandas  # Needed by plotly.express

    __HAS_CHARTS = True

    try:
        import kaleido
        __HAS_STATIC_CHARTS = True
    except ImportError:
        logging.warning("Could not find the 'kaleido' library - "
                        "static charts will not be generated!")
        __HAS_STATIC_CHARTS = False
except ImportError:
    logging.error("Could not find the 'plotly' or 'pandas' library - "
                  "interactive charts will not be generated!")
    __HAS_CHARTS = False


def hex_colour_for_string(text: str) -> str:
    return "#" + str(int(hashlib.sha1(text.encode("utf-8")).hexdigest(),
                         16) % (10 ** 6))


def load_json(json_file: str, fail_on_error: bool) -> dict:
    with open(json_file, 'r', encoding="utf-8", errors="ignore") as handle:
        data = json.load(handle, strict=False)
        if not data and fail_on_error:
            logging.error("Configuration file loading failed, or is empty.")
            sys.exit(1)
        return data


def process_project(config: dict, root_dir: str, project_name: str,
                    HTML: stat_html.HTMLPrinter):
    logging.info("Processing project '%s'...", project_name)
    basedir = os.path.join(root_dir, project_name)
    if not os.path.isdir(basedir):
        logging.error("Directory for project '%s' not found", project_name)
        return

    results = dict()
    for configuration in config["configurations"]:
        results[configuration["name"]] = \
            process_project_at_configuration(root_dir,
                                             project_name,
                                             configuration["name"])

    make_chart(config, root_dir, project_name, results, HTML)
    logging.info("Done processing project '%s'.", project_name)


def process_project_at_configuration(root_dir: str,
                                     project_name: str,
                                     configuration: str) -> Optional[dict]:
    basedir = os.path.join(root_dir, project_name)
    if not os.path.isdir(basedir):
        logging.error("Directory for project '%s' not found", project_name)
        return None

    logging.info("Collecting data for '%s' with '%s'",
                 project_name, configuration)

    results = {"meta": {"files": 0}}

    for root, dirs, _ in os.walk(basedir):
        if configuration not in dirs:
            continue

        local_results = get_tidy_profiles_from_dir(
            os.path.join(root, configuration))
        if not local_results:
            logging.debug("Configuration-like directory '%s' was empty.",
                          os.path.join(root, configuration))
            continue

        merge_results(results, local_results)

    if results["meta"]["files"] > 0:
        logging.info("Done. Writing output...")
        emit_csv_for_results(os.path.join(root_dir,
                                          project_name + "_" +
                                          configuration + ".csv"),
                             results)
        logging.info("Done.")
    else:
        logging.warning("Did not find results for configuration '%s' for '%s'",
                        configuration, project_name)

    return results


def get_tidy_profiles_from_dir(directory: str) -> dict:
    results = {"meta": {"files": 0}}

    for root, _, files in os.walk(directory):
        for file in files:
            if not file.endswith(".json"):
                continue

            file_data = load_json(os.path.join(root, file), False)
            if not file_data:
                continue

            results["meta"]["files"] += 1

            for key, value in file_data["profile"].items():
                if not key.startswith("time.") or not key.endswith(".wall"):
                    continue
                checker_name = key.replace("time.clang-tidy.", ""). \
                    replace(".wall", "")

                try:
                    results[checker_name] += value
                except KeyError:
                    results[checker_name] = value

    return results


def merge_results(results: dict, to_add: dict) -> dict:
    try:
        results["meta"]["files"] += to_add["meta"]["files"]
    except KeyError:
        try:
            results["meta"]["files"] = to_add["meta"]["files"]
        except KeyError:
            results["meta"]["files"] = 0

    for key in to_add:
        if key == "meta":
            continue

        try:
            results[key] += to_add[key]
        except KeyError:
            results[key] = to_add[key]

    return results


def emit_csv_for_results(output_path: str, results: dict):
    with open(output_path, 'w') as handle:
        writer = csv.writer(handle)
        writer.writerow(["Check", "Wall-Time"])

        for key, value in sorted(
                filter(lambda kv: kv[0] != "meta", results.items()),
                key=lambda kv: kv[1],
                reverse=True):
            if key == "meta":
                continue
            writer.writerow([key, value])


def make_chart(config: dict, root_dir: str, project_name: str, results: dict,
               HTML: stat_html.HTMLPrinter):
    if not __HAS_CHARTS:
        return
    logging.info("Writing HTML for '%s'..." % project_name)

    try:
        highlight_checkers = config["tidy_charts"]["highlight_checkers"]
        highlight_colours = list(itertools.islice(
            itertools.cycle(plotly.colors.qualitative.Light24),
            len(highlight_checkers)))
    except KeyError:
        highlight_checkers = highlight_colours = []

    # Create a list of all checkers so the colouring is consistent.
    all_checkers = set()
    for _, data in results.items():
        all_checkers.update(data.keys())
    all_checkers.remove("meta")
    all_checkers = sorted(all_checkers)

    colors = dict(map(lambda cn: [cn, hex_colour_for_string(cn)]
                          if cn not in highlight_checkers
                          else [cn, "__HIGHLIGHT__"],
                      all_checkers))
    hi_idx = 0
    for cn, c in colors.items():
        if c == "__HIGHLIGHT__":
            colors[cn] = highlight_colours[hi_idx]
            hi_idx += 1

    # Set up the canvas.
    max_row = config["tidy_charts"]["rows"]
    max_col = config["tidy_charts"]["columns"]
    specs = [[{"type": "domain"} for _ in range(max_row)]
             for _ in range(max_col)]
    titles = list(map(lambda cfg: cfg["tidy_chart_title"]
                                  if "tidy_chart_title" in cfg
                                  else cfg["name"],
                      filter(lambda cfg: cfg["name"] in results and
                                results[cfg["name"]]["meta"]["files"] > 0,
                             config["configurations"])))
    fig = psp.make_subplots(rows=max_row,
                            cols=max_col,
                            specs=specs,
                            subplot_titles=titles)

    web_statistics = dict()

    # Draw a plot for each configuration.
    r = 1
    c = 0
    for configuration in config["configurations"]:
        c += 1
        if c > max_col:
            c = 1
            r += 1

        cfg = configuration["name"]
        label = configuration["tidy_chart_title"] \
                if "tidy_chart_title" in configuration else cfg
        if cfg not in results:
            continue

        results_for_cfg = OrderedDict()
        colors_ordered = list()
        for k, v in sorted(filter(lambda kv: kv[0] != "meta",
                                  results[cfg].items()),
                           key=lambda kv: kv[1],
                           reverse=True):
            results_for_cfg[k] = v
            colors_ordered.append(colors[k])

        # For the webpage, show only the meaningful results.
        web_statistics[label] = copy.deepcopy(results_for_cfg)

        for missing_checker_in_this_cfg in all_checkers - \
                results_for_cfg.keys():
            results_for_cfg[missing_checker_in_this_cfg] = 0
            colors_ordered.append(colors[missing_checker_in_this_cfg])

        fig.add_trace(pgo.Pie(
            labels=list(results_for_cfg.keys()),
            values=list(map(lambda kv: kv[1],
                            results_for_cfg.items())),
            pull=list(map(lambda cn: 0.225 if cn in highlight_checkers else 0,
                          results_for_cfg.keys())),
            marker=dict(colors=colors_ordered),
            name=label),
                      r, c)

    fig.update_traces(hoverinfo="label+value+percent", textinfo="none")
    fig.update(layout_title_text=project_name)

    fig = pgo.Figure(fig)
    if __HAS_STATIC_CHARTS:
        fig.write_image(os.path.join(root_dir, project_name + ".png"),
                        width=1920, height=1080)
    HTML.extend_with_project(project_name, web_statistics,
                             {"Wall time": fig})
    logging.info("Done with HTML")


def main():
    parser = argparse.ArgumentParser(
        description="Tally checker runtime statistics from Clang-Tidy output")
    parser.add_argument("--config",
                        metavar="FILE",
                        default="test_config.json",
                        help="JSON file holding the list of projects and "
                             "analysis configurations.")
    parser.add_argument("--dir",
                        metavar="DIRECTORY",
                        default="projects",
                        help="The directory where the analyses took place, "
                             "usually created by 'run_experiments.py'.")
    parser.add_argument("--rows",
                        metavar='N',
                        type=int,
                        default=0,
                        help="The number of rows to organise the results in "
                             "the created charts. Defaults to as many "
                             "configurations as there is, if 0.")
    parser.add_argument("--cols",
                        metavar='M',
                        type=int,
                        default=1,
                        help="The number of columns to organise the results in "
                             "the created charts.")
    args = parser.parse_args()

    logging.info("Using configuration file '%s'.", args.config)
    config = load_json(args.config, True)
    if args.rows == 0:
        args.rows = len(config["configurations"])
    if "tidy_charts" not in config:
        config["tidy_charts"] = {}
    config["tidy_charts"]["rows"] = args.rows
    config["tidy_charts"]["columns"] = args.cols

    with stat_html.HTMLPrinter(os.path.join(args.dir, "tidy_results.html"),
                               config) as HTML:
        for project in config["projects"]:
            process_project(config, args.dir, project["name"], HTML)


if __name__ == '__main__':
    main()
