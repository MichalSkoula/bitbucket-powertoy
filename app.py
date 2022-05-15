from flask import Flask, session, render_template, request, flash, redirect, url_for
import requests
from requests.auth import HTTPBasicAuth
import urllib.parse

URL = "https://api.bitbucket.org/2.0/"

app = Flask(__name__)
app.secret_key = 'asdasdadadsasd'

@app.route("/")
def index():
    if ('username' in session):
        try:
            response = get('user')
        except:
            flash('Cannot log in #2')
            return redirect(url_for('logout'))

        # get all repositories
        repositories = get('repositories/' + session['owner'], 'pagelen=100')

        # get them issues, if any
        final_repos = []
        for r in repositories['values']:
            try:
                issues = get(
                    'repositories/' + session['owner'] + '/' + r['slug'] + '/issues', 
                    'pagelen=100&q=' + urllib.parse.quote_plus('state="new" OR state="open"')
                )

                final_issues = []
                for i in issues['values']:
                
                    if i['assignee'] != None and i['assignee']['account_id'] == session['account_id']:
                        final_issues.append(i)
                
                if final_issues:
                    r['open_issues'] = final_issues
                    final_repos.append(r)
            except:
                pass
        return render_template('index.html', repositories=final_repos)
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

def get(url, query = ''):
    return requests.get(
        URL + url + '?' + query,
        auth=HTTPBasicAuth(session['username'], session['password'])
    ).json()
