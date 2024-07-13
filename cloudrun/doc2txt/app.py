import os
import pathlib
import subprocess
import tempfile
from urllib import parse
import logging
import google.cloud.logging
import google.auth.exceptions  # type: ignore

import requests  # type: ignore
from flask import Flask, Response, request

app = Flask(__name__)
try:
    client = google.cloud.logging.Client()
    client.setup_logging()
    handler = google.cloud.logging.handlers.CloudLoggingHandler(client)
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger().addHandler(handler)
except google.auth.exceptions.DefaultCredentialsError:
    logging.error("Failed to initialize cloud logging")

_REQUEST_HEADER = {"User-Agent": ""}


def soffice_convert_doc(file: pathlib.Path) -> pathlib.Path:
    """
    Convert a DOC file to a plain text file with libreoffice.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                "soffice",
                "--headless",
                f"-env:UserInstallation=file://{tmpdir}",
                "--convert-to",
                "txt:Text",
                "--outdir",
                file.parent.as_posix(),
                file.as_posix(),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logging.info(result.stdout)
            logging.error(result.stderr)
            raise RuntimeError(result.stderr)
        return file.with_suffix(".txt")


def convert_doc_to_text(url: str, chunk_size: int = 8192):
    """
    Convert a DOC file to a plain text file.
    """
    parsed_url = parse.urlparse(url)
    filename = pathlib.Path(parsed_url.path).name
    res = requests.get(url, headers=_REQUEST_HEADER, timeout=1800)
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
    try:
        return Response(convert_doc_to_text(url), mimetype="text/plain")
    except RuntimeError as e:
        return Response(str(e), status=500)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
