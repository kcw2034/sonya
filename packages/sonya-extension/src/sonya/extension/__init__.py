"""sonya.extension — bidirectional integration with external frameworks."""

from sonya.core import register_adapter

from sonya.extension.utils.tool_converter import (
    to_langchain_tool,
    to_sonya_tool,
)
from sonya.extension.client.langchain_client import (
    LangChainAdapter,
    LangChainClient,
)
from sonya.extension.models.langchain_model import (
    SonyaChatModel,
)

register_adapter('LangChainClient', LangChainAdapter)

__version__ = '0.0.1'

__all__ = [
    # Tool converters
    'to_langchain_tool',
    'to_sonya_tool',
    # LangChain → sonya
    'LangChainClient',
    'LangChainAdapter',
    # sonya → LangChain
    'SonyaChatModel',
    # Meta
    '__version__',
]
