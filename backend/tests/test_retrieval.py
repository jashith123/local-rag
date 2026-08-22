from app.rag.retrieval import _fuse


def hit(doc, index, score, text="text"):
    return {
        "document_id": doc, "chunk_index": index, "score": score,
        "original_filename": f"{doc}.pdf", "page": 1, "text": text,
    }


def test_fusion_prefers_a_passage_both_retrievers_found():
    # 'b' is second on both lists; 'a' is first on one and absent from the
    # other. Agreement should win.
    vector = [hit("d", 1, 0.9), hit("d", 2, 0.8)]
    keyword = [hit("d", 3, 5.0), hit("d", 2, 4.0)]
    fused = _fuse(vector, keyword, limit=3)
    assert (fused[0]["document_id"], fused[0]["chunk_index"]) == ("d", 2)


def test_fusion_records_which_retrievers_matched():
    fused = _fuse([hit("d", 1, 0.9)], [hit("d", 1, 5.0)], limit=1)
    assert sorted(fused[0]["matched_by"]) == ["keyword", "vector"]
    assert fused[0]["vector_score"] == 0.9
    assert fused[0]["keyword_score"] == 5.0


def test_fusion_ignores_incompatible_score_scales():
    """A huge BM25 score must not outrank a top-ranked vector hit.

    This is the reason RRF is used instead of adding the scores: cosine sits
    near 1 and BM25 is unbounded.
    """
    vector = [hit("d", 1, 0.99)]
    keyword = [hit("d", 2, 9999.0), hit("d", 1, 0.1)]
    fused = _fuse(vector, keyword, limit=2)
    assert fused[0]["chunk_index"] == 1


def test_fusion_deduplicates_the_same_passage():
    fused = _fuse([hit("d", 1, 0.9)], [hit("d", 1, 5.0)], limit=5)
    assert len(fused) == 1


def test_fusion_respects_the_limit():
    vector = [hit("d", i, 1.0) for i in range(10)]
    assert len(_fuse(vector, [], limit=3)) == 3
