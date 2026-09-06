"""
SFTP upload to Hostinger, ported from Json_handling.html's "Uploading
Images on hostinger" cell: convert to WEBP (quality 90) and upload,
returning the public URL the site will read from `feature_image_url` /
`profile_image_url` / `cover_image_url`.
"""
import io

import paramiko
from PIL import Image

from lib.config import SFTP_HOST, SFTP_PASSWORD, SFTP_PORT, SFTP_USERNAME


def _connect():
    if not all([SFTP_HOST, SFTP_USERNAME, SFTP_PASSWORD]):
        raise RuntimeError(
            "SFTP_HOST / SFTP_USERNAME / SFTP_PASSWORD are not fully set in .env — "
            "image upload to Hostinger is not configured."
        )
    transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
    transport.connect(username=SFTP_USERNAME, password=SFTP_PASSWORD)
    sftp = paramiko.SFTPClient.from_transport(transport)
    return transport, sftp


def _ensure_remote_dir(sftp: paramiko.SFTPClient, remote_folder: str) -> None:
    """Creates each path segment that doesn't exist yet — sftp.mkdir isn't
    recursive, so this walks the path one segment at a time."""
    path = ""
    for part in remote_folder.strip("/").split("/"):
        path = f"{path}/{part}" if path else part
        try:
            sftp.stat(path)
        except FileNotFoundError:
            sftp.mkdir(path)


def upload_image(image: Image.Image, remote_folder: str, public_base_url: str, base_name: str) -> str:
    """Converts `image` to WEBP (quality 90, matching the existing
    pipeline) and uploads it to `remote_folder/<base_name>.webp` over SFTP.
    Returns the public URL it will be served from."""
    to_save = image if image.mode in ("RGBA", "LA") else image.convert("RGB")
    buffer = io.BytesIO()
    to_save.save(buffer, "WEBP", quality=90)
    buffer.seek(0)

    transport, sftp = _connect()
    try:
        _ensure_remote_dir(sftp, remote_folder)
        remote_path = f"{remote_folder}/{base_name}.webp"
        sftp.putfo(buffer, remote_path)
    finally:
        sftp.close()
        transport.close()

    return f"{public_base_url}/{base_name}.webp"
