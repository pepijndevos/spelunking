import flask
import tarfile
import urllib
import json
import subprocess
import os
import errno
import os.path

from pygments import highlight
from pygments.lexers import get_lexer_for_filename
from pygments.formatters import HtmlFormatter

app = flask.Flask(__name__)

def download_repo(owner, repo, ref="master"):
    (temp, _) = urllib.urlretrieve("https://api.github.com/repos/%s/%s/tarball/%s" % (owner, repo, ref))
    f = tarfile.open(temp, 'r:gz')
    f.extractall('source')

def get_latest(owner, repo, ref="master"):
    resp = urllib.urlopen("https://api.github.com/repos/%s/%s/git/refs/heads/%s" % (owner, repo, ref))
    data = json.load(resp)
    return data['object']['sha']

def folder_name(owner, repo, rev):
    return "%s-%s-%s/" % (owner, repo, rev[:7])

def generate_ctags(owner, repo, rev):
    path = folder_name(owner, repo, rev)
    subprocess.call(["ctags", "-o", "source/" + path + "tags", "-n", "-R", "source/" + path])

def generate_html(owner, repo, rev, path):
    htmlpath = '/'.join(['static', owner, repo, rev, path])
    sourcepath = "source/" + folder_name(owner, repo, rev) + path

    formatter = HtmlFormatter(
            full=True, # for now
            linenos='table',
            lineanchors='L',
            anchorlinenos=True,
            tagsfile="source/" + folder_name(owner, repo, rev) + "tags",
            tagurlformat="",
            )

    lexer = get_lexer_for_filename(path)
    with open(sourcepath, 'r') as inf:
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

@app.route("/")
def home():
    return "hello world"

@app.route("/<owner>/<repo>/<rev>/")
@app.route("/<owner>/<repo>/<rev>/<path:path>")
def repository(owner, repo, rev, path=""):
    fullpath = '/'.join([owner, repo, rev, path])

    if not os.path.exists("source/" + folder_name(owner, repo, rev)):
        download_repo(owner, repo, rev)
        generate_ctags(owner, repo, rev)

    if not os.path.exists('static/' + fullpath):
        generate_html(owner, repo, rev, path)

    with open('static/' + fullpath, 'r') as inf:
        return inf.read();

@app.route("/<owner>/<repo>/")
def bare_repository(owner, repo):
    rev = get_latest(owner, repo)
    url = flask.url_for('repository', owner=owner, repo=repo, rev=rev)
    return flask.redirect(url)

if __name__ == '__main__':
    app.run(debug=True)







