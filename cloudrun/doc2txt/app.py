import os
import tempfile
from urllib import parse
import pathlib
import requests
import subprocess

from flask import Flask, Response, request

app = Flask(__name__)

_REQUEST_HEADEER = {
    "User-Agent": " ".join(
        [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "AppleWebKit/537.36 (KHTML, like Gecko)",
            "Chrome/91.0.4472.124",
            "Safari/537.36",
        ]
    ),
}


def soffice_convert_doc(file: pathlib.Path) -> pathlib.Path:
    """
    Convert a DOC file to a plain text file with libreoffice.
    """
    subprocess.run(
        [
            "soffice",
            "--headless",
            "--convert-to",
            "txt:Text",
            "--outdir",
            file.parent.as_posix(),
            file.as_posix(),
        ],
        check=True,
    )
    return file.with_suffix(".txt")


def convert_doc_to_text(url: str, chunk_size: int = 8192):
    """
    Convert a DOC file to a plain text file.
    """
    parsed_url = parse.urlparse(url)
    filename = pathlib.Path(parsed_url.path).name
    res = requests.get(url, headers=_REQUEST_HEADEER, timeout=1800)
    res.raise_for_status()

    with tempfile.TemporaryDirectory() as tmpdir:
        fp = pathlib.Path(tmpdir) / filename
        with fp.open("wb") as f:
            for chunk in res.iter_content(chunk_size=chunk_size):
                f.write(chunk)
        txtfp = soffice_convert_doc(fp)
        with txtfp.open("rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk


@app.route("/doc2txt")
def doc2txt():
    """
    Convert a DOC file to a plain text file.
    """
    url = request.args.get("url", None)
    if url is None:
        return Response("Missing url parameter", status=400)
    url = parse.unquote_plus(url)
    return Response(convert_doc_to_text(url), mimetype="text/plain")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
