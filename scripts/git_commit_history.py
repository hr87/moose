#!/usr/bin/env python
import sys
import subprocess
import datetime
import re
import numpy
import matplotlib.pyplot as plt
import multiprocessing
import argparse
import itertools
import os


# A helper function for running git commands
def run(*args, **kwargs):

  options = kwargs.pop("options", None)

  if options:
    loc = os.getenv('MOOSE_DIR', os.path.join(os.getenv('HOME'), 'projects', 'moose'))
    if options.framework:
      loc = os.path.join(loc, 'framework')
    elif options.modules:
      loc = os.path.join(loc, 'modules')
    args += ('--', loc)

  output, _ = subprocess.Popen(args, stdout = subprocess.PIPE).communicate()
  if kwargs.pop('split',True):
    return filter(None, output.split('\n'))
  else:
    return output

# Return the list of contributors, sorted by the number of contributions
def getContributors(options, **kwargs):

  # Get the number of authors
  num_authors = kwargs.pop('authors', options.authors)

  # Extract the authors and total number of commits
  log = run('git', 'shortlog', '-s', '--no-merges', options=options)
  authors = []
  commits = []
  for row in log:
    r = row.split('\t')
    commits.append(int(r[0]))
    authors.append(r[1])

  # Return the authors sorted by commit count
  contributors = [x for (y,x) in sorted(zip(commits, authors), reverse=True)]

  # Limit to the supplied number of authors
  n = len(contributors)
  if num_authors == 'moose':
    contributors = ['Derek Gaston', 'Cody Permann', 'David Andrs', 'John W. Peterson', 'Andrew E. Slaughter']
    contributors += ['Other (' + str(n-len(contributors)) + ')']

  elif num_authors:
    num_authors = int(num_authors)
    contributors = contributors[0:num_authors]
    contributors += ['Other (' + str(n-num_authors) + ')']

  return contributors

# Return the date and contribution date
def getData(options):

  # Build a list of contributors
  contributors = getContributors(options)

  # Flag for lumping into two categories MOOSE developers and non-moose developers
  dev = options.moose_dev
  if dev:
    moose_developers = contributors[0:-1]
    contributors = ['MOOSE developers (' + str(len(contributors)-1) + ')', contributors[-1]]

  # Build a list of unique dates
  all_dates = sorted(set(run('git', 'log', '--reverse', '--format=%ad', '--date=short', options=options)))
  d1 = datetime.datetime.strptime(all_dates[0], '%Y-%m-%d')
  d2 = datetime.datetime.strptime(all_dates[-1], '%Y-%m-%d')
  dates = [d1 + datetime.timedelta(days=x) for x in range(0, (d2-d1).days, options.days)]

  # Build the data arrays, filled with zeros
  N = numpy.zeros((len(contributors), len(dates)), dtype=int)
  data = {'commits' : numpy.zeros((len(contributors), len(dates)), dtype=int),
          'in' : numpy.zeros((len(contributors), len(dates)), dtype=int),
          'out' : numpy.zeros((len(contributors), len(dates)), dtype=int)}

  contrib = numpy.zeros(len(dates), dtype=int)
  all_contributors = getContributors(options, authors=None)
  unique_contributors = []

  # Get the additions/deletions
  commits = run('git', 'log', '--format=%H\n%ad\n%aN', '--date=short', '--no-merges', '--reverse', '--shortstat', split=False, options=options)
  commits = filter(None, re.split(r'[0-9a-z]{40}', commits))

  # Loop over commits
  for commit in commits:
    c = filter(None, commit.split('\n'))
    date = datetime.datetime.strptime(c[0], '%Y-%m-%d')
    author = c[1]

    if dev and author in moose_developers:
      author = contributors[0]
    elif author not in contributors:
      author = contributors[-1]

    i = contributors.index(author) # author index

    d = filter(lambda x: x > date, dates)
    if d:
      j = dates.index(d[0])
    else:
      j = dates.index(dates[-1])
    data['commits'][i,j] += 1

    if options.additions and len(c) == 3:
      a = c[2].split()
      n = len(a)
      files = int(a[0])

      if n == 5:
        if a[4].startswith('insertion'):
          plus = int(a[3])
          minus = 0
        else:
          minus = int(a[3])
          plus = 0
      else:
        plus = int(a[3])
        minus = int(a[5])

      data['in'][i,j] += plus
      data['out'][i,j] += minus

    # Count unique contributions
    unique_author_index = all_contributors.index(c[1])
    unique_author = all_contributors[unique_author_index]
    if unique_author not in unique_contributors:
      unique_contributors.append(unique_author)
      contrib[j] += 1

  # Perform cumulative summations
  data['commits'] = numpy.cumsum(data['commits'], axis=1)
  contrib = numpy.cumsum(contrib)

  # Return the data
  return dates, data, contrib, contributors


# MAIN
if __name__ == '__main__':

  # Command-line options
  parser = argparse.ArgumentParser(description="Tool for building commit history of a git repository")
  parser.add_argument('--additions', action='store_true', help='Show additions/deletions graph')
  parser.add_argument('--days', type=int, default=1, help='The number of days to lump data (e.g., use 7 for weekly data)')
  parser.add_argument('--disable-legend', action='store_true', help='Disable display of legend')
  parser.add_argument('--stack', '-s', action='store_true', help='Show graph as stacked area instead of line plot')
  parser.add_argument('--unique', '-u', action='store_true', help='Show unique contributor on secondary axis')
  parser.add_argument('--open-source', '-r', action='store_true', help='Show shaded region for open sourcing of MOOSE')
  parser.add_argument('--pdf', '--file', '-f', action='store_true', help='Write the plot to a pdf file (see --output)')
  parser.add_argument('--output', '-o', type=str, default='commit_history.pdf', help='The filename for writting the plot to a file')
  parser.add_argument('--authors', default=None, help='Limit the graph to the given number of entries authors, or use "moose" to limit to MOOSE developers')
  parser.add_argument('--moose-dev', action='store_true', help='Create two categories: MOOSE developers and other (this overrides --authors)')
  parser.add_argument('--framework', action='store_true', help='Limit the analysis to framework directory')
  parser.add_argument('--modules', action='store_true', help='Limit the analysis to modules directory')
  parser.add_argument('--font', default=12, help='The font-size, in points')
  parser.parse_args('-surf'.split())
  options = parser.parse_args()

  # Markers/colors
  marker = itertools.cycle(('o', 'v', 's', 'd'))
  color = itertools.cycle(('g', 'r', 'b', 'c', 'm', 'y', 'k'))

  # Setup authors defaults for various cases
  if options.moose_dev and options.authors:
    raise Exception("Can not specify both --authors and --moose-dev");
  elif options.moose_dev:
    options.authors = 'moose'

  # Error if both --framework and --modules are given
  if options.framework and options.modules:
    raise Exception("Can not specify both --framework and --modules")

  # Extract the data
  dates, data, contrib, contributors = getData(options)

  # Create the figure
  fig, ax1 = plt.subplots()
  for tick in ax1.yaxis.get_ticklabels():
    tick.set_fontsize(options.font)
  for tick in ax1.xaxis.get_ticklabels():
    tick.set_fontsize(options.font)

  # Show unique contributors
  if options.unique:
    ax2 = ax1.twinx()
    ax2.plot(dates, contrib, linewidth=4, linestyle='-', color='k')
    ax2.set_ylabel('Unique Contributors', color='k', fontsize=options.font)
    for tick in ax2.yaxis.get_ticklabels():
      tick.set_fontsize(options.font)
    for tick in ax2.xaxis.get_ticklabels():
      tick.set_fontsize(options.font)

    arrow = dict(arrowstyle="-|>", connectionstyle="arc3,rad=0.3", fc="w")
    i = int(len(dates)*0.75)
    c = int(contrib[-1]*0.75)
    ax2.annotate('Unique Contributors', xy=(dates[i], contrib[i]), xytext=(datetime.date(2014,1,1), c), ha='right', size=options.font, arrowprops=arrow)

  # labels
  y_label = 'Commits'

  # Plot the data
  if options.stack: # stack plot
    handles = plt.stackplot(dates, data['commits'])
    for i in range(len(handles)):
      handles[i].set_label(contributors[i])

  elif options.additions: #additions/deletions plot
    y_label = 'Additions / Deletions'
    for i in range(len(contributors)):
      x = numpy.array(dates)
      y = data['in'][i,:]
      label = contributors[i] + '(Additions)'
      clr = color.next()
      ax1.fill_between(x, 0, y, label=label, linewidth=2, edgecolor=clr, facecolor=clr, alpha=0.5)
      ax1.plot([], [], color=clr, label=label) # legend proxy
      y = -data['out'][i,:]
      label = contributors[i] + '(Deletions)'
      clr = color.next()
      ax1.fill_between(x, 0, y, label=label, linewidth=2, edgecolor=clr, facecolor=clr, alpha=0.5)
      ax1.plot([], [], color=clr, label=label) # legend proxy

    if not options.disable_legend:
      handles, labels = ax1.get_legend_handles_labels()
      lgnd = plt.legend(handles, labels, loc='upper left', fontsize=options.font)
      lgnd.draw_frame(False)

  else: # line plot
    handles = []
    for i in range(len(contributors)):
      x = numpy.array(dates)
      y = data['commits'][i,:]
      idx = y>0
      h = ax1.plot(x[idx], y[idx], label=contributors[i], linewidth=2, markevery=60, marker=marker.next(), color=color.next())
      handles.append(h[0])

    if not options.disable_legend:
      lgnd = plt.legend(handles, contributors, loc='upper left', fontsize=options.font)
      lgnd.draw_frame(False)

  # Add labels
  ax1.set_ylabel(y_label, fontsize=options.font)
  ax1.set_xlabel('Date', fontsize=options.font)

  # Show open-source region
  if options.open_source:
    os = datetime.date(2014,3,10)
    y_lim = plt.ylim()
    delta = plt.xlim()[1] - os.toordinal()
    plt.gca().add_patch(plt.Rectangle((os, y_lim[0]), delta, y_lim[1]-y_lim[0], facecolor='green', alpha=0.2))


  # Write to a file
  if options.pdf:
    fig.savefig(options.output)

  plt.tight_layout()
  plt.show()
