import sys
import re
import os
from enum import Enum
from collections import defaultdict
from math import log10, floor


def dice_coefficient(a, b):
    if not len(a) or not len(b): return 0.0
    """ quick case for true duplicates """
    if a == b: return 1.0
    """ if a != b, and a or b are single chars, then they can't possibly match """
    if len(a) == 1 or len(b) == 1: return 0.0

    """ use python list comprehension, preferred over list.append() """
    a_bigram_list = [a[i:i + 2] for i in range(len(a) - 1)]
    b_bigram_list = [b[i:i + 2] for i in range(len(b) - 1)]

    a_bigram_list.sort()
    b_bigram_list.sort()

    # assignments to save function calls
    lena = len(a_bigram_list)
    lenb = len(b_bigram_list)
    # initialize match counters
    matches = i = j = 0
    while i < lena and j < lenb:
        if a_bigram_list[i] == b_bigram_list[j]:
            matches += 2
            i += 1
            j += 1
        elif a_bigram_list[i] < b_bigram_list[j]:
            i += 1
        else:
            j += 1
    score = float(matches) / float(lena + lenb)
    return score


# the different type of statistics and their corresponding pattern
class StatType(Enum):
    NUM = '#'
    PER = '%'
    MAX = 'maximum'


def summ_stats(dir, verbose=True):
    statMap = defaultdict(int)
    perHelper = defaultdict(int)
    group = {}
    if os.path.isdir(dir):
        for file in os.listdir(dir):
            summ_stats_on_file(os.path.join(dir, file), statMap, perHelper, group)
    elif os.path.isfile(dir):
        summ_stats_on_file(dir, statMap, perHelper, group)
    else:
        return statMap

    if verbose:
        # print the content of statMap in a formatted way grouped by the statistic producing file
        lastSpace = floor(log10(max(statMap.values()))) + 1
        for key in sorted(group.iterkeys(), key=(lambda x: group[x])):
            val = statMap[key]
            if isinstance(val, float):
                numOfSpaces = int(lastSpace - floor(log10(int(val)))) - 4
                sys.stdout.write("{0:.3f}".format(val))
            else:
                numOfSpaces = int(lastSpace - floor(log10(val)))
                sys.stdout.write(str(val))
            print(' ' * numOfSpaces + '- ' + key)

    return statMap


def summ_stats_on_file(filename, statMap, perHelper, group):
    typePattern = ''
    for t in StatType:
        typePattern += t.value + '|'
    typePattern = typePattern[:-1]
    statPattern = re.compile("([0-9]+(?:\.[0-9]+)?) (.+) - (The (" + typePattern + ") .+)")
    actNums = {}
    perToNumMap = {}
    perToUpdate = {}
    isInStatBlock = False
    f = open(filename)
    lines = f.readlines()
    for line in lines:
        m = statPattern.search(line)
        if m:
            isInStatBlock = True
            statType = StatType(m.group(4))
            statName = m.group(3)
            statVal = m.group(1)
            group[statName] = m.group(2)
            if statType == StatType.NUM:
                statMap[statName] += int(statVal)
                actNums[statName] = int(statVal)
            elif statType == StatType.MAX:
                statMap[statName] = max(statMap[statName], int(statVal))
            elif statType == StatType.PER:
                perToUpdate[statName] = statVal
        # when all the other statistics has been processed (to a file) than check the % stats
        elif isInStatBlock:
            isInStatBlock = False
            for key, val in perToUpdate.iteritems():
                # find the most similar # stat
                numData = max(actNums.iterkeys(), key=(lambda x: dice_coefficient(x, key)))
                perHelper[numData] += int(actNums[numData] * 100 / float(val))
                # check for consistency
                assert (not (key in perToNumMap and perToNumMap[key] != numData))
                perToNumMap[key] = numData
                statMap[key] = floor(statMap[numData]) / perHelper[numData] * 100
            actNums = {}


def main(argv):
    summ_stats(argv[1])


if __name__ == "__main__":
    main(sys.argv)
