from flask import Flask, session, render_template, request, flash, redirect, url_for
import grequests
import requests
from requests.auth import HTTPBasicAuth
import urllib.parse


app = Flask(__name__)

# SETTINGS START #
URL = "https://api.bitbucket.org/2.0/"
app.secret_key = 'asdasdadadsasd'
show_all_assignment_on_resolved_issues = True
# SETTINGS END #

@app.route("/")
@app.route("/<what>")
def index(what = 'open'):
    if ('username' in session):
        try:
            get('user')
        except:
            flash('Cannot log in #2')
            return redirect(url_for('logout'))

        # get all repositories
        repositories = get('repositories/' + session['owner'], 'pagelen=100')

        # get all issues - parallel requests
        issues_collection = load_issues(repositories['values'], what)

        # find issues for repos
        for r in repositories['values']:
            for issues in issues_collection:
                issues = issues.json()
                issues = issues['values']
                if issues and issues[0]['repository']['full_name'] == r['full_name']:
                    # we found issues for this repo
                    r['open_issues'] = []
                    for i in issues:
                        # show only my issues....or ALL issues if what=resolved
                        if (show_all_assignment_on_resolved_issues == True and what == 'resolved') or (i['assignee'] != None and i['assignee']['account_id'] == session['account_id']):
                            r['open_issues'].append(i)
                    continue

        return render_template('index.html', repositories=repositories['values'], what=what)
    else:
        return render_template('login.html')

@app.route("/login", methods=['POST'])
def login():
    try:
        session['username'] = request.form.get('username')
        session['password'] = request.form.get('password')
        session['owner'] = request.form.get('owner') if request.form.get('owner') != "" else request.form.get('username')

        response = get('user')
        session['account_id'] = response['account_id']
        flash('You were successfully logged in')
    except:
        flash('Cannot log in #1')
    return redirect(url_for('index'))

@app.route("/logout", methods=['GET'])
def logout():
    session.pop('username', None)
    session.pop('password', None)
    flash('You were successfully logged out')
    return redirect(url_for('index'))

@app.template_filter()
def format_datetime(value):
    return value[0:10]

# sync
def get(url, query = ''):
    return requests.get(
        URL + url + '?' + query,
        auth=HTTPBasicAuth(session['username'], session['password'])
    ).json()

# async - grequests
def load_issues(repositories, what):
    # first, prepare get requests
    regs = []
    really_what = what
    for r in repositories:
        if what == 'hold':
            really_what = 'state="on hold"'
        elif what == 'resolved':
            really_what = 'state="resolved"'
        else:
            really_what = 'state="new" OR state="open"'
        
        regs.append(
            grequests.get(
                URL + 'repositories/' + session['owner'] + '/' + r['slug'] + '/issues?pagelen=100&sort=-updated_on&q=' + urllib.parse.quote_plus(really_what),
                auth=HTTPBasicAuth(session['username'], session['password'])
            )
        )

    # fire all get requests at once
    return grequests.map(regs);
