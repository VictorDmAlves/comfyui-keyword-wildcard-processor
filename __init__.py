from .keyword_wildcard_processor import KeywordWildcardProcessor

NODE_CLASS_MAPPINGS = {
    "KeywordWildcardProcessor": KeywordWildcardProcessor,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KeywordWildcardProcessor": "Keyword Wildcard Processor",
}

WEB_DIRECTORY = "./web"

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]
