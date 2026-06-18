from app.services.ingestion import chunk_text


def test_chunk_text_overlaps():
    chunks = chunk_text("word " * 500, size=100, overlap=20)
    assert len(chunks) > 1
    assert all(chunks)
