import os
import urllib.parse

from flask import Flask, session, render_template, request, flash, redirect, url_for
import requests
from requests.auth import HTTPBasicAuth

app = Flask(__name__)

# SETTINGS START #
URL = "https://api.bitbucket.org/2.0/"
app.secret_key = "asdasdadadsasd"
# SETTINGS END #

@app.route("/")
@app.route("/<what>")
def index(what="open"):
    if "username" not in session:
        return render_template("login.html")

    # some stats variables
    user_issue_count = {}
    issues_count = 0
    repositories_with_issues = {}

    # get all repositories
    try:
        repositories = fetch_repository_data(
            "repositories/" + session["owner"], "pagelen=100"
        )
    except ValueError as e:
        flash(str(e))
        return redirect(url_for("logout"))

    # get all issues - parallel requests
    issues_collection = load_issues(repositories["values"], what, session["critical"])

    # find issues for repos
    for repository in repositories["values"]:
        for issues in issues_collection:
            issues = issues.json().get("values")
            if (
                not issues
                or not issues[0]["repository"]["full_name"] == repository["full_name"]
            ):
                # no issues or repo does not have issue tracker?
                continue

            # we found issues for this repo
            repository["open_issues"] = []
            repositories_with_issues[repository["full_name"]] = len(issues)

            for issue in issues:
                if issue["assignee"]:
                    # Check if the key exists in the dictionary, if not, return 0 and add 1
                    user_issue_count[issue["assignee"]["display_name"]] = (
                        user_issue_count.get(issue["assignee"]["display_name"], 0) + 1
                    )
                elif session["not_assigned"] == False:
                    continue


                # show only my issues....or ALL issues if what=resolved or what=hold
                if (
                    what != "resolved" and what != "hold"
                ) and (
                    issue["assignee"]
                    and issue["assignee"]["account_id"] != session["account_id"]
                ):
                    continue

                repository["open_issues"].append(issue)
                issues_count += 1

    # sort user_issue_count by value desc
    user_issue_count = dict(
        sorted(user_issue_count.items(), key=lambda item: item[1], reverse=True)
    )

    # sort repositories_with_issues by value desc
    repositories_with_issues = dict(
        sorted(repositories_with_issues.items(), key=lambda item: item[1], reverse=True)
    )

    return render_template(
        "index.html",
        repositories=repositories["values"],
        what=what,
        issues_count=issues_count,
        user_issue_count=user_issue_count,
        repositories_with_issues=repositories_with_issues,
    )


@app.route("/login", methods=["POST"])
def login():
    required_form_data = (
        request.form.get("username"),
        request.form.get("password"),
    )
    if not all(required_form_data):
        flash("Please enter username and password")
        return redirect(url_for("index"))

    try:
        session["username"] = request.form.get("username")
        session["password"] = request.form.get("password")
        session["critical"] = request.form.get("critical") is not None
        session["not_assigned"] = request.form.get("not_assigned") is not None
        session["owner"] = (
            request.form.get("owner")
            if request.form.get("owner")
            else request.form.get("username")
        )

        response = fetch_repository_data("user")
    except ValueError:
        # wrong credentials or repository data fetching failed
        # because of TimeoutError, NetworkError etc.
        # So it is possible that we are lying to the user here
        flash("Username or Password is wrong")
    else:
        acc_id = response.get("account_id")
        if not acc_id:
            raise ValueError("Cannot set account ID")

        session["account_id"] = acc_id
        flash("You were successfully logged in")
    return redirect(url_for("index"))


@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username", None)
    session.pop("password", None)
    flash("You were successfully logged out")
    return redirect(url_for("index"))


@app.template_filter()
def format_datetime(value):
    return value[0:10]


# sync
def fetch_repository_data(url, query=""):
    credentials = (session.get("username"), session.get("password"))
    if not all(credentials):
        raise ValueError("Credentials were not provided")

    response = requests.get(
        url=URL + url + "?" + query, auth=HTTPBasicAuth(*credentials)
    )
    if not response.ok:
        raise ValueError(
            "Bad response - status code: {}\n{}".format(
                response.status_code, response.text
            )
        )
    return response.json()


# synchronous requests
def load_issues(repositories, issue_state, only_critical_and_blocker=False):
    DEFAULT_QUERY = '(state="new" OR state="open")'
    ISSUE_STATES_MAP = {
        "hold": '(state="on hold")',
        "resolved": '(state="resolved")',
    }
    
    responses = []
    
    for repository in repositories:
        # https://developer.atlassian.com/cloud/bitbucket/rest/intro#filtering
        current_issue_state = ISSUE_STATES_MAP.get(issue_state, DEFAULT_QUERY)

        if only_critical_and_blocker:
            current_issue_state += ' AND (priority > "major")'

        url = (
            URL
            + "repositories/"
            + session["owner"]
            + "/"
            + repository["slug"]
            + "/issues?pagelen=100&sort=-updated_on&q="
            + urllib.parse.quote_plus(current_issue_state)
        )
        
        try:
            response = requests.get(
                url,
                auth=HTTPBasicAuth(session["username"], session["password"]),
            )
            responses.append(response)
        except requests.RequestException:
            # Create a mock response object for failed requests
            class MockResponse:
                def json(self):
                    return {"values": []}
            responses.append(MockResponse())

    return responses


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=True)
