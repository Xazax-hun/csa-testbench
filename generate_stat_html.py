import os
import sys
import json


def print_stats_html(name, data, html):
    stat_html = open(html, 'a')
    if os.stat(html).st_size == 0:
        stat_html.write("<html><head><title>Detailed Statistics</title></head>"
                        "<style>table {border-collapse: collapse; border-spacing: 0;} td, th {border: 1px solid #999999;} th {background: #dddddd; text-align: center;} td {text-align: right;}"
                        " td:first-child {text-align: left;} tr:nth-child(even) td {background: #ffffff;} tr:nth-child(odd) td {background: #eeeeee;}</style> <body>")
    stat_html.write("<h1>" + name + "</h1>\n")
    stat_html.write("<table>\n")
    stat_html.write("<tr>\n")
    stat_html.write("<th>Statistic Name</th><th>Value</th>")
    stat_html.write("</tr>\n")

    with open(data) as stat_file:
        stat_json = stat_file.read()
        stats = json.loads(stat_json)
        for statname, statval in stats.iteritems():
            stat_html.write("<tr>\n")
            stat_html.write("<td>" + statname + "</td>")
            stat_html.write("<td>" + str(statval) + "</td>")
            stat_html.write("</tr>\n")
        stat_html.write("</table>\n\n")
    stat_html.close()


def main():
    print_stats_html(sys.argv[1], sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()
