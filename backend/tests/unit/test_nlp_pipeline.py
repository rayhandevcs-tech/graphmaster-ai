"""Pipeline loading, and what happens when the model is not installed.

The unavailable path is the one an operator meets on a fresh deployment, so it
is worth testing on a machine where the model *is* present: the failure is
simulated rather than waited for.
"""

from __future__ import annotations

import pytest

from app.core.exceptions import AnalysisEngineUnavailableError
from app.nlp import pipeline


@pytest.fixture
def missing_model(monkeypatch):
    """Make the model look absent, and leave the cache clean either way."""
    import spacy

    def refuse(*args, **kwargs):
        raise OSError("[E050] Can't find model 'en_core_web_sm'")

    pipeline.get_nlp.cache_clear()
    monkeypatch.setattr(spacy, "load", refuse)
    yield
    pipeline.get_nlp.cache_clear()


def test_a_missing_model_raises_the_deployment_error(missing_model):
    with pytest.raises(AnalysisEngineUnavailableError) as exc:
        pipeline.get_nlp()
    # An operator meeting this needs the command that fixes it, not a stack
    # trace ending in a path they have never heard of.
    assert "python -m spacy download" in exc.value.message


def test_the_missing_model_error_is_a_503(missing_model):
    with pytest.raises(AnalysisEngineUnavailableError) as exc:
        pipeline.get_nlp()
    # A deployment fault, not a data fault: retrying the same request against a
    # correctly provisioned server would succeed.
    assert exc.value.status_code == 503


def test_availability_is_false_without_a_model(missing_model):
    assert pipeline.is_available() is False


def test_warm_up_reports_failure_without_raising(missing_model):
    # A server with no model must still start and serve everything that is not
    # scoring.
    assert pipeline.warm_up() is False


def test_pipeline_info_reports_the_model_as_unavailable(missing_model):
    info = pipeline.pipeline_info()
    assert info["available"] is False
    assert info["version"] is None
    assert info["pipes"] == []


@pytest.mark.usefixtures("spacy_model")
class TestLoaded:
    def test_the_pipeline_is_loaded_once(self):
        assert pipeline.get_nlp() is pipeline.get_nlp()

    def test_entity_recognition_is_disabled(self):
        # The most expensive stage in the default pipeline, and nothing here
        # uses entity labels.
        assert "ner" not in pipeline.get_nlp().pipe_names

    def test_the_components_matching_depends_on_are_present(self):
        pipes = pipeline.get_nlp().pipe_names
        assert {"tagger", "attribute_ruler", "lemmatizer", "parser"} <= set(pipes)

    def test_warm_up_succeeds(self):
        assert pipeline.warm_up() is True

    def test_pipeline_info_reports_the_loaded_model(self, settings):
        info = pipeline.pipeline_info()
        assert info["available"] is True
        assert info["model"] == settings.SPACY_MODEL
        assert info["version"]


def test_reloading_the_pipeline_invalidates_compiled_matchers(spacy_model, term_factory):
    """A matcher must never outlive the vocabulary it was built against.

    ``PhraseMatcher`` reports matches as hashes into its own ``Vocab``'s string
    store. Reusing a cached matcher after the pipeline is reloaded therefore
    fails with ``[E018] Can't retrieve string for hash`` — or, if the hash
    happens to resolve, silently matches the wrong term.
    """
    from app.nlp.analyzer import analyse

    targets = [term_factory("higher than", "high than", category="comparison")]
    text = "Revenue was higher than costs throughout."

    assert analyse(text, targets).score.unique_detected_count == 1

    pipeline.get_nlp.cache_clear()
    pipeline.get_nlp()

    assert analyse(text, targets).score.unique_detected_count == 1
