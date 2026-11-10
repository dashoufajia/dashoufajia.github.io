"""Fail the Render build if the required NLP resources are unavailable."""
from pathlib import Path
import sys
import nltk
import spacy
import textstat

assert sys.version_info[:2] == (3, 12), 'Use Python 3.12'
nltk.data.path.insert(0, str(Path(__file__).resolve().parents[1] / 'nltk_data'))
nltk.data.find('corpora/cmudict')
nlp = spacy.load('en_core_web_sm')
assert list(nlp('Cats sleep.').sents)
assert textstat.syllable_count('writing') > 0
print('Python 3.12, spaCy English model and cmudict are ready.')
