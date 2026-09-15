"""File persistence — stores uploads under `uploads/{request_id}/{file_id}/`."""

from pathlib import Path


class Storage:
    def __init__(self, upload_dir: str, db_path: str) -> None:
        self.upload_dir = Path(upload_dir)
        self.db_path = Path(db_path)

    def save(self, request_id: str, file_id: str, filename: str, content: bytes) -> Path:
        target = self.upload_dir / request_id / file_id
        target.mkdir(parents=True, exist_ok=True)
        path = target / Path(filename).name  # strip any client-supplied path segments
        path.write_bytes(content)
        return path