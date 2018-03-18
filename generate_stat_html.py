import os


def print_stats_html(name, data, html):
    stat_html = open(html, 'a')
    if os.stat(html).st_size == 0:
        stat_html.write("<html><head><title>Detailed Statistics</title></head>"
                        "<style>table {border-collapse: collapse; border-spacing: 0;} td, th {border: 1px solid #999999;} th {background: #dddddd; text-align: center;} td {text-align: right;}"
                        " td:first-child {text-align: left;} tr:nth-child(even) td {background: #ffffff;} tr:nth-child(odd) td {background: #eeeeee;}</style> <body>")
    keys = set()
    configurations = set()
    for configuration, val in data.iteritems():
        configurations.add(configuration)
        for stat_name in val:
            keys.add(stat_name)

    stat_html.write("<h1>" + name + "</h1>\n")
    stat_html.write("<table>\n")
    stat_html.write("<tr>\n")
    stat_html.write("<th>Statistic Name</th>")
    for conf in configurations:
        stat_html.write("<th>%s</th>" % conf)
    stat_html.write("</tr>\n")

    for stat_name in keys:
        stat_html.write("<tr>\n")
        stat_html.write("<td>%s</td>" % stat_name)
        for conf in configurations:
            val = "-"
            if stat_name in data[conf]:
                val = str(data[conf][stat_name])
            stat_html.write("<td>%s</td>" % val)
        stat_html.write("</tr>\n")
    stat_html.write("</table>\n\n")
    stat_html.close()
