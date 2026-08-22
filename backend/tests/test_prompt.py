from app.rag.prompt import build_context, build_user_message


def hit(name="a.pdf", index=0, page=None, text="passage text"):
    return {
        "original_filename": name, "chunk_index": index,
        "page": page, "text": text,
    }


def test_passages_are_numbered_from_one():
    context = build_context([hit(text="first"), hit(text="second")])
    assert "[1]" in context and "[2]" in context


def test_page_is_preferred_over_chunk_index_in_the_citation_label():
    assert "page 4" in build_context([hit(page=4)])


def test_falls_back_to_chunk_index_when_a_page_is_unknown():
    # Documents indexed before page tracking have no page number.
    assert "chunk 7" in build_context([hit(index=7, page=None)])


def test_no_passages_is_stated_explicitly():
    message = build_user_message("anything?", [])
    assert "No passages" in message
    assert "anything?" in message


def test_the_question_is_included_with_the_passages():
    message = build_user_message("why?", [hit(text="because")])
    assert "because" in message and "why?" in message
