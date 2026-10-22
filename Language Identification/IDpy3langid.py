"""Language identification module using py3langid."""
import unittest
from typing import Literal

import py3langid as langid
from py3langid.langid import MODEL_FILE, LanguageIdentifier

AVAILABLE_LANGUAGES: list[str] = [
'ace', 'af', 'am', 'an', 'ar', 'ary', 'arz', 'as', 'az', 'ba', 'bcl',
'be', 'bg', 'bn', 'br', 'bs', 'ca', 'crh', 'cs', 'cy',  'da',  'de',
'dz', 'el', 'en', 'eo', 'es', 'et', 'eu', 'ext', 'fa', 'fi', 'fo', 'fr',
'fuv', 'fy', 'ga', 'gcf', 'gcr', 'gd', 'gl', 'gom', 'grc', 'gu', 'gug',
'guw', 'ha', 'hbo', 'he', 'hi', 'hr', 'ht', 'hu', 'hy', 'id', 'ig', 'is',
'it', 'ja', 'jv', 'ka', 'kab', 'kik', 'kk', 'km', 'kn', 'ko', 'ku', 'ky',
'la', 'lb', 'lg', 'lij', 'ln', 'lo', 'lt', 'ltg', 'lv', 'mg', 'mk', 'ml',
'mn', 'mr', 'ms', 'mt', 'my', 'ne', 'nl', 'nn', 'no', 'nso', 'oc', 'om',
'or', 'pa', 'pcm', 'pl', 'ps', 'pt', 'qu', 'ro', 'ru', 'rw', 'sa', 'sdh',
'se', 'si', 'sk', 'sl', 'sn', 'so', 'sq', 'sr', 'st', 'sv', 'sw', 'ta',
'te', 'tg', 'th', 'tk', 'tl', 'tr', 'tt', 'ug', 'uk', 'ur', 'uz', 'uzs',
'vec', 'vi', 'vo', 'wa', 'wuu', 'xh', 'yo', 'yue', 'zh', 'zu', 'zxx']

def identify_language(text) -> tuple[str, float]:
    """Identified language and probability with absolute value and rounded to 2 decimal places"""
    language, probability = langid.classify(instance=text)
    return language, abs(round(number=probability, ndigits=2))

def identify_normalized(text: str, norm_probs=True, min_confidence=0.15, languages: None | list[str] = None) -> tuple[str | Literal['No language detected'], float]:
    '''Identified language and probability with absolute value and rounded to 2 decimal places, using normalized probabilities and a minimum confidence threshold
    If no language is detected under the threshold, returns 'No language detected' and the probability.
    Identifier can be limited to a list of languages, provided as a list of ISO 639-1 or ISO 639-3 codes. If no languages are provided, all available languages will be used.'''

    identifier: LanguageIdentifier = LanguageIdentifier.from_model_file(model_file=MODEL_FILE, norm_probs=norm_probs, min_confidence=min_confidence)
    identifier.set_languages(langs=languages) # If needed, a list of languages can be specified to limit the detection
    language, probability = identifier.classify(text=text)
    if language == 'und':
        language: str = f'No language detected under the threshold of {min_confidence}'
    return language, abs(round(number=probability*100, ndigits=2))
def identify_languages(text, candidates: int = 3) -> list[tuple[str, float]]:
    """Returns potential languages and probabilities with absolute value and rounded to 2 decimal places, limited by the candidates parameter"""
    candidates_list = [
        (language, abs(round(number=probability, ndigits=2)))
        for language, probability in langid.rank(instance=text)[:candidates]
    ]
    return candidates_list

def run_all_functions(text: str) -> None:
    lang, prob = identify_language(text)
    print(f"Identified language: '{lang}', Probability: {prob}%")
    lang, prob = identify_normalized(text)
    print(f"Identified language with normalized probabilities: '{lang}', Probability: {prob}%")
    returned_candidates = 5
    candidates: list[tuple[str, float]] = identify_languages(text, candidates=returned_candidates)
    print(f"Top {returned_candidates} candidates: {candidates}")

class TestIdentifyLanguage(unittest.TestCase):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.text = "Ce mai faci?"
    def test_identify_language(self) -> None:
        self.assertEqual(first=identify_language(text=self.text), second=("ro", 19.82))
    def test_identify_normalized(self) -> None:
        self.assertEqual(first=identify_normalized(text=self.text), second=("ro", 27.83))
    def test_identify_languages(self) -> None:
        self.assertEqual(first=identify_languages(text=self.text, candidates=5), second=[('ro', 19.82), ('oc', 23.78), ('it', 24.34), ('ha', 25.05), ('fr', 25.24)])

if __name__ == "__main__":
    text = "Cine este letconex?"
    run_all_functions(text)
    unittest.main()
