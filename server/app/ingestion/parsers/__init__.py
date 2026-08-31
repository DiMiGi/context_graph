from app.ingestion.parsers.php_parser import PhpParser
from app.ingestion.parsers.csharp_parser import CsharpParser
from app.ingestion.parsers.python_parser import PythonParser
from app.ingestion.parsers.jsts_parser import JsTsParser
from app.ingestion.parsers.doc_parser import DocParser
from app.ingestion.parsers.sql_parser import SqlParser
from app.ingestion.parsers.html_parser import HtmlParser
from app.ingestion.parsers.config_parser import ConfigParser
from app.ingestion.parsers.style_parser import StyleParser
from app.ingestion.parsers.diagram_parser import DiagramParser
from app.ingestion.parsers.text_parser import TextDocParser
from app.ingestion.parsers.generic_parser import GenericCodeParser

PARSERS_MAP = {
    # PHP
    ".php": PhpParser(),
    # C# / .NET
    ".cs": CsharpParser(),
    # Python
    ".py": PythonParser(),
    # JS / TS
    ".js": JsTsParser(),
    ".jsx": JsTsParser(),
    ".ts": JsTsParser(),
    ".tsx": JsTsParser(),
    # Web & UI Markup
    ".html": HtmlParser(),
    ".htm": HtmlParser(),
    ".css": StyleParser(),
    ".scss": StyleParser(),
    ".sass": StyleParser(),
    ".less": StyleParser(),
    # Config & Data
    ".json": ConfigParser(),
    ".yml": ConfigParser(),
    ".yaml": ConfigParser(),
    ".xml": ConfigParser(),
    ".conf": ConfigParser(),
    # Docs & Diagrams
    ".md": DocParser(),
    ".mdx": DocParser(),
    ".mmd": DiagramParser(),
    ".mermaid": DiagramParser(),
    ".txt": TextDocParser(),
    # SQL
    ".sql": SqlParser(),
    ".prisma": SqlParser(),
    # Compiled / Other Languages
    ".c": GenericCodeParser(),
    ".cpp": GenericCodeParser(),
    ".h": GenericCodeParser(),
    ".hpp": GenericCodeParser(),
    ".java": GenericCodeParser(),
    ".go": GenericCodeParser(),
    ".rs": GenericCodeParser(),
    ".kt": GenericCodeParser(),
    ".swift": GenericCodeParser(),
    ".rb": GenericCodeParser(),
    ".dart": GenericCodeParser(),
}

def get_parser(extension: str):
    return PARSERS_MAP.get(extension.lower())
