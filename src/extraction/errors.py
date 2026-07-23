class ExtractionError(RuntimeError):
    """A document could not be extracted with confidence.

    Operationally, every ExtractionError means the same thing: the photo needs
    human review before the document can move down the pipeline.
    """
