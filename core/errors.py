"""Pipeline errors. Every failure of a job surfaces as a PipelineError subclass."""


class PipelineError(Exception):
    """Base class for job failures that must be reported to the user."""


class FetchError(PipelineError):
    """The video could not be fetched from its URL."""


class AudioExtractionError(PipelineError):
    """ffmpeg could not extract audio from the video."""


class SpeechToTextError(PipelineError):
    """The STT provider failed or returned an unusable response."""


class UnsupportedLanguageError(PipelineError):
    """The detected or requested language is not es, en or ru."""

    def __init__(self, lang: str, role: str = "source") -> None:
        super().__init__(f"Unsupported {role} language: {lang!r}")
        self.lang = lang
        self.role = role


class SameLanguageError(PipelineError):
    """The video is already in the requested target language."""


class TranslationError(PipelineError):
    """The translation provider failed."""


class TranslationMismatchError(TranslationError):
    """The translator response does not preserve segment ids 1:1."""


class RenderError(PipelineError):
    """An output file could not be rendered."""
