#!/usr/bin/env python3
import argparse
import csv
import json
import logging
import os
import sys

# try:
#     import plotly.express as plotly
#     __HAS_CHARTS = True
# except ImportError:
#     __HAS_CHARTS = False


def load_json(json_file: str, fail_on_error: bool) -> dict:
    with open(json_file, 'r', encoding="utf-8", errors="ignore") as handle:
        data = json.load(handle, strict=False)
        if not data and fail_on_error:
            logging.error("Configuration file loading failed, or is empty.")
            sys.exit(1)
        return data


def process_project(config: dict, project_name: str):
    logging.info("Processing project '%s'...", project_name)
    basedir = os.path.join(config["__args__"].dir, project_name)
    if not os.path.isdir(basedir):
        logging.error("Directory for project '%s' not found", project_name)
        return

    for configuration in config["configurations"]:
        process_project_at_configuration(config, project_name,
                                         configuration["name"])

    logging.info("Done processing project '%s'.", project_name)


def process_project_at_configuration(config: dict,
                                     project_name: str,
                                     configuration: str):
    basedir = os.path.join(config["__args__"].dir, project_name)
    if not os.path.isdir(basedir):
        logging.error("Directory for project '%s' not found", project_name)
        return

    logging.info("Collecting data for '%s' with '%s'",
                 project_name, configuration)

    results = {"meta": {"files": 0}}

    for root, dirs, files in os.walk(basedir):
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
        emit_csv_for_results(os.path.join(config["__args__"].dir,
                                          project_name + "_" +
                                          configuration + ".csv"),
                             results)
        logging.info("Done.")
    else:
        logging.warning("Did not find results for configuration '%s' for '%s'",
                        configuration, project_name)


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
                filter(lambda e: e[0] != "meta", results.items()),
                key=lambda e: e[1],
                reverse=True):
            if key == "meta":
                continue
            print(key, value)
            writer.writerow([key, value])




def main():
    logging.basicConfig(format='%(asctime)s (%(levelname)s) %(message)s',
                        datefmt='%H:%M:%S', level=logging.INFO)

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
    args = parser.parse_args()

    logging.info("Using configuration file '%s'.", args.config)
    config = load_json(args.config, True)
    config["__args__"] = args

    for project in config["projects"]:
        process_project(config, project["name"])
        return


if __name__ == '__main__':
    main()
