from __future__ import division
import sys
import os


def summarize_gcov(path):
    summary = {}
    overall_sum = 0
    overall_missed = 0
    overall_noop = 0
    overall_covered = 0
    overall_max = 0
    for root, _, files in os.walk(path):
        for f in files:
            if not f.endswith(".gcov"):
                continue
            file_path = os.path.join(root, f)
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
                    elif value == "-":
                        file_noop += 1
                        continue
                    value = int(value)
                    file_covered += 1
                    file_sum += value
                    if value > file_max:
                        file_max = value
            summary[file_path] = {"max": file_max, "coverage": file_covered / (file_covered + file_missed),
                                  "sum": file_sum, "missed": file_missed, "covered": file_covered,
                                  "average": file_sum / (file_covered + file_missed), "noop": file_noop}
            if file_max > overall_max:
                overall_max = file_max
            overall_covered += file_covered
            overall_missed += file_missed
            overall_noop += file_noop
            overall_sum += file_sum
    summary["overall"] = {"max": overall_max, "coverage": overall_covered / (overall_covered + overall_missed),
                          "sum": overall_sum, "missed": overall_missed, "covered": overall_covered,
                          "average": overall_sum / (overall_covered + overall_missed), "noop": overall_noop}
    return summary


if __name__ == "__main__":
    summarize_gcov(sys.argv[1])
