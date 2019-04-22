#!/usr/bin/env python2
from collections import defaultdict
from cgi import escape
from datetime import timedelta
import json

try:
    import plotly.offline as py
    import plotly.graph_objs as go
    charts_supported = True
except ImportError:
    charts_supported = False

header = """
<!DOCTYPE html>
<html lang="en">
<head>
  <title>Detailed Statistics</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css"
        integrity="sha384-ggOyR0iXCbMQv3Xipma34MD+dH/1fQ784/j6cY/iJTQUOhcWr7x9JvoRxT2MZw1T"
        crossorigin="anonymous">
  <script src="https://code.jquery.com/jquery-3.3.1.slim.min.js"
          integrity="sha384-q8i/X+965DzO0rT7abK41JStQIAqVgRVzpbzo5smXKp4YfRvH+8abtTE1Pi6jizo"
          crossorigin="anonymous"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.14.7/umd/popper.min.js"
          integrity="sha384-UO2eT0CpHqdSJQ6hJty5KVphtPhzWj9WO1clHTMGa3JDZwrnQq4sF86dIHNDz0W1"
          crossorigin="anonymous"></script>
  <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/js/bootstrap.min.js"
          integrity="sha384-JjSmVgyd0p3pXB1rRibZUAYoIIy6OrQ6VrjIEaFf/nJGzIxFDsf4x0xIM+B07jRM"
          crossorigin="anonymous"></script>
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
  <script type="text/javascript">
      // Reload Poltly graphs on tab change.
      $(document).ready(function () {
          $('a[data-toggle="tab"]').on('shown.bs.tab', function (e) {
              var target = $(e.target).attr("href");
              var toRemove = [];
              var toAppend = [];
              $(target).find("SCRIPT").each(function (index, element) {
                  var script = document.createElement('script');
                  script.type = 'text/javascript';
                  script.text = element.text
                  toRemove.push(element);
                  toAppend.push(script);
              });
              toRemove.forEach(function (item) {
                  item.remove();
              });
              toAppend.forEach(function (item) {
                  $(target).append(item);
              });
              $(target).find("DIV").each(function (index, element) {
                   if (element.className.includes("plotly-graph-div")) {
                       Plotly.relayout(element, {height: 500});
                   }
               });
          })
      });
  </script>
  <style> .tab-content { padding: 10px; } </style>
</head>
<body>
<div class="jumbotron text-center">
  <h1>Detailed Static Analyzer Statistics</h1>
</div>
<div class="container">
"""

footer = """
</div>
</div>
<footer>
  <div class="container-fluid bg-light p-3 mb-2">
    <span class="text-muted">This report is created by the
      <a href="https://github.com/Xazax-hun/csa-testbench">CSA-Testbench</a> toolset.</span>
  </div>
</footer>
</body>
</html>
"""


# FIXME: Escape strings.
class HTMLPrinter(object):

    def __init__(self, path, config):
        self.html_path = path
        self.charts = config.get("charts", ["Duration", "Result count"])
        self.excludes = ["TU times"]
        self.as_comment = ["Analyzer version"]
        self.projects = {}
        with open(self.html_path, 'w') as stat_html:
            stat_html.write(header)
            stat_html.write("<!-- %s -->\n" %
                            escape(json.dumps(config)))
            # Generate nav bar.
            stat_html.write('<nav>\n<div class="nav nav-tabs" id="nav-tab" role="tablist">\n')
            active = "active"
            for project in config["projects"]:
                name = escape(project["name"])
                text = '<a class="nav-item nav-link {0}" id="nav-{1}-tab"' \
                       ' data-toggle="tab" href="#nav-{1}" role="tab"' \
                       ' aria-controls="nav-{1}" aria-selected="{2}">{1}</a>' \
                    .format(active, name, active != "")
                stat_html.write(text)
                active = ""
            text = '<a class="nav-item nav-link" id="nav-charts-tab"' \
                   ' data-toggle="tab" href="#nav-charts" role="tab"' \
                   ' aria-controls="nav-charts" aria-selected="false">Charts</a>'
            stat_html.write(text)
            stat_html.write('</div>\n</nav>\n')
            stat_html.write('<div class="tab-content" id="nav-tabContent">\n')

    def finish(self):
        with open(self.html_path, 'a') as stat_html:
            self._generate_charts(stat_html)
            stat_html.write(footer)

    def extend_with_project(self, name, data):
        first = len(self.projects) == 0
        self.projects[name] = data
        stat_html = open(self.html_path, 'a')
        keys = set()
        configurations = set()
        for configuration, val in data.items():
            configurations.add(configuration)
            for stat_name in val:
                keys.add(stat_name)

        tab = '<div class="tab-pane fade {0}" ' \
              'id="nav-{1}" role="tabpanel" aria-labelledby="nav-{1}-tab">\n'\
            .format("show active" if first else "", escape(name))
        stat_html.write(tab)
        stat_html.write('<table class="table table-bordered table-striped table-sm">\n')
        stat_html.write('<thead class="thead-dark">')
        stat_html.write("<tr>\n")
        stat_html.write("<th>Statistic Name</th>")
        for conf in configurations:
            stat_html.write("<th>%s</th>" % escape(conf))
        stat_html.write("</tr>\n")
        stat_html.write('</thead>\n')
        stat_html.write('<tbody>\n')

        for stat_name in keys:
            if stat_name in self.excludes or \
               stat_name in self.as_comment:
                continue
            stat_html.write("<tr>\n")
            stat_html.write("<td>%s</td>" % escape(stat_name))
            for conf in configurations:
                val = str(data[conf].get(stat_name, '-'))
                stat_html.write("<td>%s</td>" % val)
            stat_html.write("</tr>\n")
        stat_html.write('</tbody>\n')
        stat_html.write("</table>\n\n")

        # Output some values as comments.
        for stat_name in self.as_comment:
            for conf in configurations:
                val = str(data[conf].get(stat_name, '-'))
                stat_html.write("<!-- %s[%s]=%s -->\n" %
                                (escape(conf), escape(stat_name), escape(val)))

        HTMLPrinter._generate_time_histogram(stat_html, configurations, data)
        stat_html.write('</div>\n')
        stat_html.close()

    @staticmethod
    def _generate_time_histogram(stat_html, configurations, data):
        if not charts_supported:
            return
        traces = []
        for conf in configurations:
            if "TU times" in data[conf]:
                if not data[conf]["TU times"]:
                    continue
                traces.append(go.Histogram(x=data[conf]["TU times"],
                                           name=conf))
        if not traces:
            return
        layout = go.Layout(barmode='overlay')
        fig = go.Figure(data=traces, layout=layout)
        div = py.plot(fig, show_link=False, include_plotlyjs=False,
                      output_type='div', auto_open=False)
        stat_html.write("<h3>Time per TU histogram</h3>\n")
        stat_html.write(div)

    def _generate_charts(self, stat_html):
        stat_html.write('<div class="tab-pane fade" id="nav-charts"'
                        ' role="tabpanel" aria-labelledby="nav-charts-tab">\n')
        if not charts_supported:
            stat_html.write("<p>Charts not supported."
                            "Install Plotly python library.</p>\n</div>\n")
            return
        layout = go.Layout(barmode='group')
        for chart in self.charts:
            names = defaultdict(list)
            values = defaultdict(list)
            for project, data in self.projects.items():
                for configuration, stats in data.items():
                    values[configuration].append(
                        HTMLPrinter._get_chart_value(stats.get(chart, 0)))
                    names[configuration].append(project)

            # Skip empty charts.
            if all([all([x == 0 for x in values[conf]]) for conf in names]):
                continue

            bars = []
            for conf in names:
                bar = go.Bar(x=names[conf], y=values[conf], name=conf)
                bars.append(bar)

            fig = go.Figure(data=bars, layout=layout)
            div = py.plot(fig, show_link=False, include_plotlyjs=False,
                          output_type='div', auto_open=False)
            stat_html.write("<h2>%s</h2>\n" % escape(chart))
            stat_html.write(div)

        stat_html.write("</div>\n")

    @staticmethod
    def _get_chart_value(value):
        if isinstance(value, timedelta):
            return value.seconds
        return float(value)
