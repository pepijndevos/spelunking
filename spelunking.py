import flask
import tarfile
import urllib2
import json
import subprocess
import os
import errno
import os.path
import shutil
import tempfile
import codecs

from pygments import highlight
from pygments.lexers import get_lexer_for_filename
from pygments.formatters import HtmlFormatter

app = flask.Flask(__name__)

secret_souce = "?client_id=80690b45e37d126cf0b3&client_secret=1575880eac803128879b62c0e225b902393d1241"

def get_json(url):
    try:
        resp = urllib2.urlopen("https://api.github.com/" + url + secret_souce)
    except urllib2.HTTPError as e:
        flask.abort(e.code)

    return json.load(resp)

def download_repo(owner, repo, ref="master"):
    try:
        resp = urllib2.urlopen("https://api.github.com/repos/%s/%s/tarball/%s%s" % (owner, repo, ref, secret_souce))
    except urllib2.HTTPError as e:
        flask.abort(e.code)

    with tempfile.NamedTemporaryFile(delete=False) as temp:
        shutil.copyfileobj(resp, temp)

    with tarfile.open(temp.name, 'r:gz') as t:
        t.extractall('source')

def get_latest(owner, repo, ref="master"):
    data = get_json("repos/%s/%s/git/refs/heads/%s" % (owner, repo, ref))
    return data['object']['sha']

def folder_name(owner, repo, rev):
    return "%s-%s-%s/" % (owner, repo, rev[:7])

def generate_ctags(owner, repo, rev):
    path = "source/" + folder_name(owner, repo, rev)
    subprocess.call(["ctags", "-n", "-R", "."], cwd=path)

def generate_html(owner, repo, rev, path):
    htmlpath = '/'.join(['static', owner, repo, rev, path])
    sourcepath = "source/" + folder_name(owner, repo, rev) + path

    formatter = HtmlFormatter(
            full=True, # for now
            linenos='table',
            lineanchors='L',
            anchorlinenos=True,
            tagsfile="source/" + folder_name(owner, repo, rev) + "tags",
            tagurlformat='/'.join(['', owner, repo, rev, "%(path)s/%(fname)s%(fext)s"]),
            )

    lexer = get_lexer_for_filename(path)
    with codecs.open(sourcepath, 'r', 'utf8') as inf:
        source = inf.read();

    dirname = os.path.dirname(htmlpath);
    try:
        os.makedirs(dirname)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(dirname):
            pass
        else:
            raise

    with open(htmlpath, 'w+') as outf:
        highlight(source, lexer, formatter, outf)

@app.route("/<owner>/<repo>/<rev>/")
@app.route("/<owner>/<repo>/<rev>//<path:path>")
@app.route("/<owner>/<repo>/<rev>/<path:path>")
def repository(owner, repo, rev, path=""):
    path = path.strip('/');
    fullpath = '/'.join([owner, repo, rev, path])
    sourceroot = "source/" + folder_name(owner, repo, rev)

    if not os.path.exists(sourceroot):
        download_repo(owner, repo, rev)
        generate_ctags(owner, repo, rev)

    sourcepath = sourceroot + path
    if os.path.isdir(sourcepath):
        return flask.render_template("list.html",
                owner=owner,
                repo=repo,
                pages=[{"name": p, "href": p + "/"} for p in os.listdir(sourcepath)])

    if not os.path.exists(sourceroot + path):
        flask.abort(404)

    if not os.path.exists('static/' + fullpath):
        generate_html(owner, repo, rev, path)

    return flask.send_file('static/' + fullpath, 'text/html')

@app.route("/<owner>/<repo>/")
def bare_repository(owner, repo):
    rev = get_latest(owner, repo)
    url = flask.url_for('repository', owner=owner, repo=repo, rev=rev)
    return flask.redirect(url)

@app.route("/<owner>/")
def profile(owner):
    data = get_json("users/%s/repos" % owner)

    return flask.render_template("list.html",
            owner=owner,
            pages=[{"name": item["name"], "href": "/" + item["full_name"]} for item in data])

@app.route("/")
def home():
    return flask.send_file("templates/home.html", "text/html")

if __name__ == '__main__':
    app.run(debug=True)







