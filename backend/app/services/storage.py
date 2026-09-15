"""File and database persistence stubs.

TODO implement in Phase P0:
- write(request_id, file_id, UploadFile) -> path under settings.upload_dir
- record_bid(DocumentUpload) / record_document(...) into SQLite (schema.sql)
- load_pipeline_events(request_id) -> list[PipelineEvent]
"""

from pathlib import Path


class Storage:
    def __init__(self, upload_dir: str, db_path: str) -> None:
        self.upload_dir = Path(upload_dir)
        self.db_path = Path(db_path)

    def save(self, request_id: str, file_id: str, filename: str, content: bytes) -> Path:
        target = self.upload_dir / request_id / file_id
        target.mkdir(parents=True, exist_ok=True)
        path = target / filename
        path.write_bytes(content)
        return path