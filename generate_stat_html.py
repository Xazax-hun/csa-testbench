import os

header = """
<!DOCTYPE html>
<html lang="en">
<head>
  <title>Detailed Statistics</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0/css/bootstrap.min.css">
  <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.3.1/jquery.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.12.9/umd/popper.min.js"></script>
  <script src="https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0/js/bootstrap.min.js"></script>
</head>
<body>
<div class="jumbotron text-center">
  <h1>Detailed Static Analyzer Statistics</h1>
</div>
<div class="container">
"""

footer = """
</div>
</body>
</html>
"""


def finish_stats_html(html):
    with open(html, 'a') as stat_html:
        stat_html.write(footer)


def extend_stats_html(name, data, html):
    stat_html = open(html, 'a')
    if os.stat(html).st_size == 0:
        stat_html.write(header)
    keys = set()
    configurations = set()
    for configuration, val in data.iteritems():
        configurations.add(configuration)
        for stat_name in val:
            keys.add(stat_name)

    stat_html.write("<h1>" + name + "</h1>\n")
    stat_html.write('<table class="table table-bordered table-striped table-sm">\n')
    stat_html.write('<thead class="thead-dark">')
    stat_html.write("<tr>\n")
    stat_html.write("<th>Statistic Name</th>")
    for conf in configurations:
        stat_html.write("<th>%s</th>" % conf)
    stat_html.write("</tr>\n")
    stat_html.write('</thread>\n')
    stat_html.write('<tbody>\n')

    for stat_name in keys:
        stat_html.write("<tr>\n")
        stat_html.write("<td>%s</td>" % stat_name)
        for conf in configurations:
            val = "-"
            if stat_name in data[conf]:
                val = str(data[conf][stat_name])
            stat_html.write("<td>%s</td>" % val)
        stat_html.write("</tr>\n")
    stat_html.write('</tbody>\n')
    stat_html.write("</table>\n\n")
    stat_html.close()
