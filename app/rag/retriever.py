from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.rag.story_bank import Story


class StoryRetriever:
    """Finds the story most relevant to a given application question.

    Uses TF-IDF + cosine similarity rather than a real embedding model.
    That's a deliberate tradeoff: a candidate's story bank is small (a
    handful of stories, not thousands of documents), so keyword-overlap
    retrieval works fine at this scale, and it means no embedding API call
    and no model download - this runs fully offline and is trivial to
    test deterministically. Swapping in real embeddings later (e.g. an
    embeddings API) would only require changing this one class.
    """

    def __init__(self, stories: list[Story]):
        if not stories:
            raise ValueError("Story bank is empty - add at least one story.")
        self.stories = stories
        corpus = [f"{s.title} {' '.join(s.tags)} {s.text}" for s in stories]
        self._vectorizer = TfidfVectorizer(stop_words="english")
        self._matrix = self._vectorizer.fit_transform(corpus)

    def best_match(self, question: str) -> Story:
        query_vector = self._vectorizer.transform([question])
        scores = cosine_similarity(query_vector, self._matrix)[0]
        best_index = scores.argmax()
        return self.stories[best_index]
