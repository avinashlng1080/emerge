"""
Contains the implementation of the Python language parser and a relevant keyword enum.
"""

# Authors: Grzegorz Lato <grzegorz.lato@gmail.com>
# License: MIT

import pyparsing as pp
from typing import Dict
from enum import Enum, unique
import coloredlogs
import logging
from pathlib import PosixPath

from emerge.languages.abstractparser import AbstractParser, ParsingMixin, Parser, CoreParsingKeyword, LanguageType
from emerge.results import FileResult
from emerge.abstractresult import AbstractResult, AbstractEntityResult
from emerge.logging import Logger
from emerge.statistics import Statistics

LOGGER = Logger(logging.getLogger('parser'))
coloredlogs.install(level='E', logger=LOGGER.logger(), fmt=Logger.log_format)


@unique
class PythonParsingKeyword(Enum):
    IMPORT = "import"
    FROM = "from"
    INLINE_COMMENT = "#"
    BLOCK_COMMENT = '"""'
    NEWLINE = '\n'
    EMPTY = ''
    BLANK = ' '


class PythonParser(AbstractParser, ParsingMixin):

    def __init__(self):
        self._results: Dict[str, AbstractResult] = {}
        self._token_mappings: Dict[str, str] = {
            ':': ' : ',
            ';': ' ; ',
            '{': ' { ',
            '}': ' } ',
            '(': ' ( ',
            ')': ' ) ',
            '[': ' [ ',
            ']': ' ] ',
            '?': ' ? ',
            '!': ' ! ',
            ',': ' , ',
            '<': ' < ',
            '>': ' > ',
            '"': ' " '
        }

    @classmethod
    def parser_name(cls) -> str:
        return Parser.PYTHON_PARSER.name

    @property
    def results(self) -> Dict[str, AbstractResult]:
        return self._results

    @results.setter
    def results(self, value):
        self._results = value

    def generate_file_result_from_analysis(self, analysis, *, file_name: str, full_file_path: str, file_content: str) -> None:
        LOGGER.debug(f'generating file results...')
        scanned_tokens = self.preprocess_file_content_and_generate_token_list_by_mapping(file_content, self._token_mappings)

        # make sure to create unique names by using the relative analysis path as a base for the result
        parent_analysis_source_path = f"{PosixPath(analysis.source_directory).parent}/"
        relative_file_path_to_analysis = full_file_path.replace(parent_analysis_source_path, "")

        file_result = FileResult.create_file_result(
            analysis=analysis,
            scanned_file_name=file_name,
            relative_file_path_to_analysis=relative_file_path_to_analysis,
            absolute_name=full_file_path,
            display_name=file_name,
            module_name="",
            scanned_by=self.parser_name(),
            scanned_language=LanguageType.C,
            scanned_tokens=scanned_tokens
        )

        self._add_package_name_to_result(file_result)
        self._add_imports_to_result(file_result, analysis)
        self._results[file_result.unique_name] = file_result

    def after_generated_file_results(self, analysis) -> None:
        pass

    def generate_entity_results_from_analysis(self, analysis):
        raise NotImplementedError(f'currently not implemented in {self.parser_name()}')

    def create_unique_entity_name(self, entity: AbstractEntityResult) -> None:
        raise NotImplementedError(f'currently not implemented in {self.parser_name()}')

    def _add_imports_to_result(self, result: AbstractResult, analysis):
        LOGGER.debug(f'extracting imports from file result {result.scanned_file_name}...')
        list_of_words_with_newline_strings = result.scanned_tokens

        source_string_no_comments = self._filter_source_tokens_without_comments(
            list_of_words_with_newline_strings, PythonParsingKeyword.INLINE_COMMENT.value, PythonParsingKeyword.BLOCK_COMMENT.value, PythonParsingKeyword.BLOCK_COMMENT.value)
        filtered_list_no_comments = self.preprocess_file_content_and_generate_token_list_by_mapping(source_string_no_comments, self._token_mappings)

        # for simplicity we can parse python dependencies just line by line
        source_import_lines = []
        line = PythonParsingKeyword.EMPTY.value
        for word in filtered_list_no_comments:
            if word is not PythonParsingKeyword.NEWLINE.value:
                line += word
                line += PythonParsingKeyword.BLANK.value  # make sure to seperate the words
            else:  # remove the last blank if NEWLINE is found
                line = line[:-1]
                # only append relevant lines with 'import'
                if line is not PythonParsingKeyword.EMPTY.value and PythonParsingKeyword.IMPORT.value in line and line not in source_import_lines:
                    source_import_lines.append(line)
                line = PythonParsingKeyword.EMPTY.value

        for line in source_import_lines:

            # create parsing expression
            valid_name = pp.Word(pp.alphanums + CoreParsingKeyword.DOT.value +
                                 CoreParsingKeyword.UNDERSCORE.value + CoreParsingKeyword.DASH.value + CoreParsingKeyword.SLASH.value)

            expression_to_match = (pp.Keyword(PythonParsingKeyword.IMPORT.value) | pp.Keyword(PythonParsingKeyword.FROM.value)) + \
                valid_name.setResultsName(CoreParsingKeyword.IMPORT_ENTITY_NAME.value) + \
                pp.Optional(pp.FollowedBy(pp.Keyword(PythonParsingKeyword.IMPORT.value)))

            try:
                parsing_result = expression_to_match.parseString(line)

            except Exception as some_exception:
                result.analysis.statistics.increment(Statistics.Key.PARSING_MISSES)
                LOGGER.warning(f'warning: could not parse result {result=}\n{some_exception}')
                continue

            analysis.statistics.increment(Statistics.Key.PARSING_HITS)

            # ignore any dependency substring from the config ignore list
            dependency = getattr(parsing_result, CoreParsingKeyword.IMPORT_ENTITY_NAME.value)
            if self._is_dependency_in_ignore_list(dependency, analysis):
                LOGGER.debug(f'ignoring dependency from {result.unique_name} to {dependency}')
            else:
                result.scanned_import_dependencies.append(dependency)
                LOGGER.debug(f'adding import: {dependency}')

    def _add_package_name_to_result(self, result: AbstractResult) -> str:
        result.module_name = None


if __name__ == "__main__":
    LEXER = PythonParser()
    print(f'{LEXER.results=}')