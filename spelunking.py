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
import threading
import logging
import fcntl

from pygments import highlight
from pygments.lexers import get_lexer_for_filename, TextLexer
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound

app = flask.Flask(__name__)
app.logger.addHandler(logging.FileHandler("flask.log"))

secret_souce = "?client_id=80690b45e37d126cf0b3&client_secret=1575880eac803128879b62c0e225b902393d1241"

def get_json(url):
    try:
        resp = urllib2.urlopen("https://api.github.com/" + url + secret_souce)
    except urllib2.HTTPError as e:
        flask.abort(e.code)

    return json.load(resp)

def download_repo(owner, repo, ref):
    os.mkdir("source/" + folder_name(owner, repo, ref))
    try:
        resp = urllib2.urlopen("https://api.github.com/repos/%s/%s/tarball/%s%s" % (owner, repo, ref, secret_souce))
    except urllib2.HTTPError as e:
        flask.abort(e.code)

    with tarfile.open(None, 'r|gz', resp) as t:
        def is_within_directory(directory, target):
            
            abs_directory = os.path.abspath(directory)
            abs_target = os.path.abspath(target)
        
            prefix = os.path.commonprefix([abs_directory, abs_target])
            
            return prefix == abs_directory
        
        def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
        
            for member in tar.getmembers():
                member_path = os.path.join(path, member.name)
                if not is_within_directory(path, member_path):
                    raise Exception("Attempted Path Traversal in Tar File")
        
            tar.extractall(path, members, numeric_owner=numeric_owner) 
            
        
        safe_extract(t, "source")

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

    try:
        lexer = get_lexer_for_filename(path)
    except ClassNotFound:
        lexer = TextLexer();

    with codecs.open(sourcepath, 'r', 'utf8') as inf:
        try:
            fcntl.flock(inf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            return

        source = inf.read();

        dirname = os.path.dirname(htmlpath);
        try:
            os.makedirs(dirname)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(dirname):
                pass
            else:
                raise
        
        fd, tmpath = tempfile.mkstemp(dir="static")
        with os.fdopen(fd, 'w') as outf:
            highlight(source, lexer, formatter, outf)
            os.rename(tmpath, htmlpath)

        fcntl.flock(inf, fcntl.LOCK_EX | fcntl.LOCK_NB)

@app.route("/<owner>/<repo>/<rev>/")
@app.route("/<owner>/<repo>/<rev>//<path:path>")
@app.route("/<owner>/<repo>/<rev>/<path:path>")
def repository(owner, repo, rev, path=""):
    path = path.strip('/');
    fullpath = '/'.join([owner, repo, rev, path])
    sourceroot = "source/" + folder_name(owner, repo, rev)

    if not os.path.exists(sourceroot):
        def prepare():
            download_repo(owner, repo, rev)
            generate_ctags(owner, repo, rev)

        threading.Thread(target=prepare).start()
        return flask.render_template("wait.html", owner=owner, repo=repo)

    sourcepath = sourceroot + path
    if os.path.isdir(sourcepath):
        return flask.render_template("list.html",
                owner=owner,
                repo=repo,
                pages=[{"name": p, "href": p + "/"} for p in os.listdir(sourcepath)])

    if not os.path.exists(sourcepath):
        flask.abort(404)

    if not os.path.exists('static/' + fullpath):
        threading.Thread(target=generate_html, args=(owner, repo, rev, path)).start()
        return flask.render_template("wait.html", owner=owner, repo=repo)

    return flask.redirect(fullpath, 301)

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
    return flask.render_template("home.html", load=', '.join(["%.2f" % l for l in os.getloadavg()]))

if __name__ == '__main__':
    app.run(debug=True)
