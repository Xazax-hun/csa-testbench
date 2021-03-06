#!/usr/bin/env python3

import os
import sys


def summarize_gcov(path: str):
    summary = {}
    overall_sum = 0
    overall_missed = 0
    overall_noop = 0
    overall_covered = 0
    overall_max = 0
    for root, _, files in os.walk(path):
        for gcov_file in files:
            if not gcov_file.endswith(".gcov"):
                continue
            file_path = os.path.join(root, gcov_file)
            file_max = 0
            file_sum = 0
            file_covered = 0
            file_missed = 0
            file_noop = 0
            with open(file_path) as content:
                for line in content:
                    value = line.split(":")[0]
                    if value == "#####":
                        file_missed += 1
                        continue
                    if value == "-":
                        file_noop += 1
                        continue
                    value = int(value)
                    file_covered += 1
                    file_sum += value
                    if value > file_max:
                        file_max = value
            file_all = max(file_covered + file_missed, 1)
            summary[file_path] = {"max": file_max, "coverage": file_covered / file_all,
                                  "sum": file_sum, "missed": file_missed, "covered": file_covered,
                                  "average": file_sum / file_all, "noop": file_noop}
            if file_max > overall_max:
                overall_max = file_max
            overall_covered += file_covered
            overall_missed += file_missed
            overall_noop += file_noop
            overall_sum += file_sum
    overall_all = max(overall_covered + overall_missed, 1)
    summary["overall"] = {"max": overall_max, "coverage": overall_covered / overall_all,
                          "sum": overall_sum, "missed": overall_missed, "covered": overall_covered,
                          "average": overall_sum / overall_all, "noop": overall_noop}
    return summary


if __name__ == "__main__":
    import json
    res = summarize_gcov(sys.argv[1])
    with open(sys.argv[2], "w") as f:
        json.dump(res, f, indent=2)
