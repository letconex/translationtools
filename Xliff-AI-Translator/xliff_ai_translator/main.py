"""
Script for translating XLIFF files using AI-based models.

This script provides functionality to translate text in XLIFF (XML Localisation 
Interchange File Format) files using a pre-trained M2M100 model from Hugging Face's 
transformers library. It supports batch processing and handling of various text 
elements within XLIFF files.

The script includes classes and functions to parse XLIFF files, configure translation 
settings, perform the translation, and build the translated XLIFF file. It is designed 
to be run as a command-line tool, where the user can specify the source file, 
destination file, and target language for the translation.

Key Components:
- TranslatorConfig: Configuration class for translation settings.
- translate_batch: Function to translate a batch of text strings.
- Classes for handling XLIFF file structure: GElement, TextContainer, TransUnit, File.
- parse_xliff, parse_text_container: Functions to parse XLIFF files.
- copy_source_to_target: Function to copy source text to target.
- translate_targets: Function to translate target texts in files.
- build_xliff: Function to build the final translated XLIFF file.

Usage:
    Run as a script with command-line arguments for source file, destination file, 
    and target language code.

Example Command:
    python script_name.py source_file.xliff destination_file.xliff target_language

Dependencies:
- lxml for XML parsing
- transformers library from Hugging Face for AI-based translation, version < 5
"""

import argparse
import re
from copy import deepcopy
from dataclasses import dataclass, field

from lxml import etree
from transformers import AutoTokenizer, M2M100ForConditionalGeneration


@dataclass
class TranslatorConfig:
    """
    Configuration class for text translation tasks using the M2M100 model.

    Attributes:
        model (M2M100ForConditionalGeneration): Pre-trained M2M100 model for 
            machine translation.
        tokenizer (AutoTokenizer): Tokenizer for the M2M100 model.
        batch_size (int): Number of text entries in a batch, default is 10.

    Example usage:
        model = M2M100ForConditionalGeneration.from_pretrained(
            'facebook/m2m100_418M')
        tokenizer = AutoTokenizer.from_pretrained('facebook/m2m100_418M')
        config = TranslatorConfig(model=model, tokenizer=tokenizer, 
                                batch_size=10)
    """

    model: M2M100ForConditionalGeneration
    tokenizer: AutoTokenizer
    batch_size: int = 10


def translate_batch(text_batch, dest_lang, model, tokenizer):
    """
    Translates a batch of text strings into a specified destination language.

    Args:
        text_batch (list[str]): A list of text strings for translation.
        dest_lang (str): The ISO code of the destination language.
        model (transformers.PreTrainedModel): The pre-trained translation model.
        tokenizer (transformers.PreTrainedTokenizer): The tokenizer for the model.

    Returns:
        list[str]: The list of translated strings in the destination language.

    Example usage:
        translated_texts = translate_batch(["Hello, world!"], 'fr', model, tokenizer)
    """

    model_inputs = tokenizer(
        text_batch, return_tensors="pt", padding=True, truncation=True, max_length=512)
    gen_tokens = model.generate(
        **model_inputs, forced_bos_token_id=tokenizer.get_lang_id(dest_lang))
    translations = tokenizer.batch_decode(gen_tokens, skip_special_tokens=True)
    return translations


@dataclass
class GElement:
    """
    Represents a 'g' element in an XLIFF file, which is a text block.

    Attributes:
        id (str): The ID of the element.
        ctype (str): The content type of the element.
        text (str): The text content of the element.
    """

    id: str
    ctype: str
    text: str


@dataclass
class TextContainer:
    """
    Represents a container for text in an XLIFF file, either source or target.

    Attributes:
        text (Optional[str]): Text content of the container.
        g_elements (list[GElement]): list of GElement objects representing 'g'
            elements within the container.
    """

    text: str | None = None
    g_elements: list[GElement] = field(default_factory=list)


@dataclass
class TransUnit:
    """
    Represents a translation unit in an XLIFF file, consisting of source and target text blocks.

    Attributes:
        id (str): The ID of the translation unit.
        source (TextContainer): The source text container.
        target (TextContainer): The target text container.
    """

    id: str
    source: TextContainer = field(default_factory=TextContainer)
    target: TextContainer = field(default_factory=TextContainer)


@dataclass
class File:
    """
    Represents a file in an XLIFF file, containing multiple translation units.

    Attributes:
        original (str): The original file name.
        datatype (str): The data type of the file.
        source_language (str): The source language of the file.
        target_language (str): The target language of the file.
        trans_units (list[TransUnit]): A list of TransUnit objects within the file.
    """

    original: str
    datatype: str
    source_language: str
    target_language: str
    trans_units: list[TransUnit] = field(default_factory=list)


def parse_xliff(file_path):
    """
    Parses an XLIFF file and extracts translation data into structured objects.

    Args:
        file_path (str): Path to the XLIFF file.

    Returns:
        list[File]: A list of File objects representing the content of the XLIFF file.

    Example usage:
        files = parse_xliff('path/to/file.xlf')
    """

    with open(file=file_path, mode='r', encoding='utf-8') as file:
        tree = etree.parse(file)
    root = tree.getroot()

    ns = {'default': root.nsmap[None]}
    files = []

    for file_elem in root.findall('default:file', namespaces=ns):
        file_original = file_elem.get('original')
        file_datatype = file_elem.get('datatype')
        file_source_language = file_elem.get('source-language')
        file_target_language = file_elem.get('target-language')
        trans_units = []

        for trans_unit_elem in file_elem.findall('.//default:trans-unit', namespaces=ns):
            trans_unit_id = trans_unit_elem.get('id')
            source = parse_text_container(trans_unit_elem.find(
                'default:source', namespaces=ns), ns)
            target = parse_text_container(trans_unit_elem.find(
                'default:target', namespaces=ns), ns)

            trans_units.append(
                TransUnit(id=trans_unit_id, source=source, target=target))

        files.append(File(
            original=file_original,
            datatype=file_datatype,
            source_language=file_source_language,
            target_language=file_target_language,
            trans_units=trans_units
        ))

    return files


def parse_text_container(elem, ns) -> TextContainer:
    """
    Parses a text container element in an XLIFF file to extract text and 'g' elements.

    Args:
        elem (xml.etree.ElementTree.Element): The XML element representing the text container.
        ns (dict): The namespace dictionary for parsing the XML.

    Returns:
        TextContainer: An object representing the parsed text container.
    """

    text_container = TextContainer()
    if elem is not None:
        # If there is text directly in the element, retrieve it
        if elem.text:
            text_container.text = elem.text.strip()

        # Parse the <g> elements if they exist
        for g_elem in elem.findall('default:g', namespaces=ns):
            g_id = g_elem.get('id')
            g_ctype = g_elem.get('ctype')
            g_text = ''.join(g_elem.itertext()).strip()
            text_container.g_elements.append(
                GElement(id=g_id, ctype=g_ctype, text=g_text))

    return text_container


def copy_source_to_target(files: list[File]) -> None:
    """
    Copies source text to the target text for each translation unit in the provided files.

    Args:
        files (list[File]): A list of File objects containing translation units.

    Note:
        This function directly modifies the provided File objects.
    """

    for file in files:
        for trans_unit in file.trans_units:
            # If there is a source, copy its content to the target
            if trans_unit.source:
                if trans_unit.target is None:
                    trans_unit.target = deepcopy(trans_unit.source)
                else:
                    trans_unit.target.text = deepcopy(trans_unit.source.text)
                    trans_unit.target.g_elements = deepcopy(
                        trans_unit.source.g_elements)


def contains_letters(text) -> bool:
    """
    Checks if a given text string contains any letters.

    Args:
        text (str): The text string to check.

    Returns:
        bool: True if the text contains letters, False otherwise.
    """

    return bool(re.search('[a-zA-Z]', text))


def translate_targets(files, dest_lang, model, tokenizer):
    """
    Translates the target text of each translation unit in the provided files.

    Args:
        files (list[File]): A list of File objects to translate.
        dest_lang (str): The destination language for translation.
        model (transformers.PreTrainedModel): The translation model.
        tokenizer (transformers.PreTrainedTokenizer): The tokenizer for the model.

    Returns:
        list[File]: The list of File objects with translated target texts.

    Note:
        This function directly modifies the provided File objects.
    """

    # Prepare the list of texts to translate
    text_to_translate = []
    mapping = []  # To track where each text should go

    for file in files:
        for trans_unit in file.trans_units:
            # Add the source text to the translation list if it's not empty and it contains letters
            if (trans_unit.source.text and trans_unit.source.text.strip()
                    and contains_letters(trans_unit.source.text)):
                text_to_translate.append(trans_unit.source.text)
                # None for the texts that are not in <g>
                mapping.append((trans_unit, 'text', None))
            else:
                # Keep the original text if the text does not contain any letters
                trans_unit.target.text = trans_unit.source.text

            # Do the same for the elements if they exist and are not empty
            for g_element in trans_unit.source.g_elements:
                if g_element.text and g_element.text.strip() and contains_letters(g_element.text):
                    text_to_translate.append(g_element.text)
                    mapping.append((trans_unit, 'g', g_element))
                else:
                    # Find the corresponding <g> element in `target` and keep the original text
                    corresponding_g_element = next(
                        (ge for ge in trans_unit.target.g_elements if ge.id == g_element.id), None)
                    if corresponding_g_element:
                        corresponding_g_element.text = g_element.text

    # Translate only if there are texts to translate 
    print(text_to_translate)

    if text_to_translate:
        translated_texts = translate_batch(
            text_to_translate, dest_lang, model, tokenizer)

        # Assign the translated texts to their respective positions in `target`
        for (trans_unit, text_type, g_element), translation in zip(mapping, translated_texts):
            if text_type == 'text':
                # update the text directly in `target`
                trans_unit.target.text = translation
            elif text_type == 'g' and g_element is not None:
                # Find the corresponding g-element in `target` and update it
                corresponding_g_element = next(
                    (ge for ge in trans_unit.target.g_elements if ge.id == g_element.id), None)
                if corresponding_g_element:
                    corresponding_g_element.text = translation
    else:
        print("No text to be translated.")

    return files


def build_xliff(files, target_language):
    """
    Builds an XLIFF file from the provided list of File objects.

    Args:
        files (list[File]): A list of File objects to include in the XLIFF.
        target_language (str): The target language of the translation.

    Returns:
        str: The XML string representation of the XLIFF file.
    """

    # Create the root element with the necessary namespaces
    nsmap = {
        None: "urn:oasis:names:tc:xliff:document:1.2",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xhtml": "http://www.w3.org/1999/xhtml"
    }
    # Create the root element with the necessary namespaces
    xliff_elem = etree.Element("xliff", nsmap=nsmap, version="1.2")
    xliff_elem.set("{http://www.w3.org/2001/XMLSchema-instance}schemaLocation",
                   "urn:oasis:names:tc:xliff:document:1.2 "
                   "http://docs.oasis-open.org/xliff/v1.2/os/xliff-core-1.2-strict.xsd")

    for file in files:

        file_attributes = {
            'original': file.original if file.original is not None else '',
            'datatype': file.datatype if file.datatype is not None else '',
            'source-language': file.source_language if file.source_language
            is not None else target_language,
            'target-language': file.target_language if file.target_language
            is not None else target_language,
        }

        # Create the <file> element for each file
        file_elem = etree.SubElement(xliff_elem, "file", file_attributes)

        # Create and add the <body>
        body_elem = etree.SubElement(file_elem, "body")

        for trans_unit in file.trans_units:
            # Create the <trans-unit> element
            trans_unit_elem = etree.SubElement(
                body_elem, "trans-unit", {"id": trans_unit.id})

            # Add the <source> element and its content
            source_elem = etree.SubElement(trans_unit_elem, "source")
            if trans_unit.source.text:
                source_elem.text = trans_unit.source.text
            for g_element in trans_unit.source.g_elements:
                g_elem = etree.SubElement(source_elem, "g", {
                    "id": g_element.id,
                    "ctype": g_element.ctype
                })
                g_elem.text = g_element.text

            # Add the <target> element and its content
            target_elem = etree.SubElement(trans_unit_elem, "target")
            if trans_unit.target.text:
                target_elem.text = trans_unit.target.text
            for g_element in trans_unit.target.g_elements:
                g_elem = etree.SubElement(target_elem, "g", {
                    "id": g_element.id,
                    "ctype": g_element.ctype
                })
                g_elem.text = g_element.text

    # Convert the XML tree to a string with pretty printing and UTF-8 encoding
    xml_output = etree.tostring(
        xliff_elem,
        pretty_print=True,
        encoding='UTF-8',
        xml_declaration=True
    ).decode()

    return xml_output


def main() -> None:
    """
    Main function for translating XLIFF files using command-line arguments.

    Handles arguments for the source file, destination path, and target language code.
    Sets up the M2M100 model and tokenizer, processes the source file, performs 
    translation, and saves the translated content.

    Translates text in the XLIFF file from source to target language as specified. 
    Uses functions to parse XLIFF, copy source to target, translate text blocks, 
    and reconstruct the XLIFF with translated content.

    Usage:
        python script_name.py source_file.xliff destination_file.xliff target_language

    Example:
        python script_name.py example.xliff translated_example.xliff fr

    Args:
        source (str): Path to the source XLIFF file.
        destination (str): Path for the translated XLIFF file.
        language (str): ISO code for the target translation language.
    """

    parser = argparse.ArgumentParser(
        description='Translate XLF/XLIFF files using batch processing.')
    parser.add_argument(
        'source', help='The source subtitle file to translate.')
    parser.add_argument(
        'destination', help='The subtitle file where to save the translation.')
    parser.add_argument(
        'language', help='The target language code for the translation.')
    args = parser.parse_args()

    model_name = "facebook/m2m100_418M"
    model = M2M100ForConditionalGeneration.from_pretrained(model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    files = parse_xliff(args.source)
    copy_source_to_target(files)
    files2 = translate_targets(files, args.language, model, tokenizer)

    translated_xliff_content = build_xliff(files2, args.language)
    print(translated_xliff_content)

    with open(args.destination, 'w', encoding='utf-8') as f:
        f.write(translated_xliff_content)

if __name__ == "__main__":
    main()
