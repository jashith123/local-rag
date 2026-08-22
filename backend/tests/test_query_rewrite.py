from app.rag import query_rewrite


def test_a_standalone_question_is_not_rewritten(monkeypatch):
    """No history, no model call — a rewrite would cost a round trip."""
    def explode(*args, **kwargs):
        raise AssertionError("should not call the model")
    monkeypatch.setattr(query_rewrite, "get_provider", explode)

    query, changed = query_rewrite.rewrite("what is the time complexity of BFS", [])
    assert query == "what is the time complexity of BFS"
    assert changed is False


def test_a_question_with_its_own_subject_skips_the_rewrite(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("should not call the model")
    monkeypatch.setattr(query_rewrite, "get_provider", explode)

    history = [{"role": "user", "content": "tell me about BFS"}]
    query, changed = query_rewrite.rewrite(
        "what is the space complexity of breadth first search", history
    )
    assert changed is False


def test_a_pronoun_follow_up_is_rewritten(monkeypatch):
    class FakeProvider:
        def complete(self, system, messages):
            return "How fast is breadth first search?", {}

    monkeypatch.setattr(query_rewrite, "get_provider", lambda: FakeProvider())
    history = [
        {"role": "user", "content": "what is breadth first search"},
        {"role": "assistant", "content": "BFS explores level by level."},
    ]
    query, changed = query_rewrite.rewrite("how fast is it", history)
    assert query == "How fast is breadth first search?"
    assert changed is True


def test_a_failed_rewrite_falls_back_to_the_original(monkeypatch):
    class Broken:
        def complete(self, system, messages):
            raise RuntimeError("model down")

    monkeypatch.setattr(query_rewrite, "get_provider", lambda: Broken())
    history = [{"role": "user", "content": "about BFS"}]
    query, changed = query_rewrite.rewrite("how fast is it", history)
    assert query == "how fast is it"
    assert changed is False


def test_a_rambling_rewrite_is_rejected(monkeypatch):
    class Chatty:
        def complete(self, system, messages):
            return "Sure! " + ("x" * 400), {}

    monkeypatch.setattr(query_rewrite, "get_provider", lambda: Chatty())
    history = [{"role": "user", "content": "about BFS"}]
    query, _ = query_rewrite.rewrite("how fast is it", history)
    assert query == "how fast is it"
