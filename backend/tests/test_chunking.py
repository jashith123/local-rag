from app.rag.chunking import chunk_pages, chunk_text, normalize


def test_empty_input_produces_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_short_text_is_a_single_chunk():
    assert chunk_text("hello world") == ["hello world"]


def test_chunks_respect_the_size_limit():
    text = " ".join(f"word{i:04d}" for i in range(600))
    for chunk in chunk_text(text, chunk_size=1000, overlap=200):
        assert len(chunk) <= 1000


def test_consecutive_chunks_actually_overlap():
    text = " ".join(f"word{i:04d}" for i in range(600))
    chunks = chunk_text(text, chunk_size=1000, overlap=200)
    assert len(chunks) > 1
    # The tail of one chunk should reappear at the head of the next; that is
    # the whole point of the overlap.
    tail_word = chunks[0].split()[-1]
    assert tail_word in chunks[1][:400]


def test_overlap_larger_than_chunk_is_rejected():
    # Without this guard the loop below would never move forward.
    try:
        chunk_text("abc", chunk_size=10, overlap=10)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_tiny_chunks_terminate():
    """A chunk shorter than the overlap must not make `start` move backwards.

    This is the infinite-loop guard; if it regresses the test hangs rather
    than fails, which is why the input is small.
    """
    text = " ".join(f"w{i}" for i in range(200))
    chunks = chunk_text(text, chunk_size=20, overlap=15)
    assert len(chunks) > 0


def test_pages_carry_their_page_number():
    pages = ["first page text", "second page text", "third page text"]
    records = chunk_pages(pages)
    assert [r["page"] for r in records] == [1, 2, 3]


def test_a_chunk_never_spans_two_pages():
    records = chunk_pages(["alpha " * 50, "beta " * 50])
    for record in records:
        assert ("alpha" in record["text"]) != ("beta" in record["text"])


def test_blank_pages_are_skipped_but_do_not_shift_numbering():
    records = chunk_pages(["one", "", "three"])
    assert [r["page"] for r in records] == [1, 3]


def test_normalize_collapses_whitespace():
    assert normalize("a   b\n\n\n\nc") == "a b\n\nc"
