import py3langid as langid

def identify_language(text):
    # identified language and probability
    print(langid.classify(text))
# unpack the result tuple in variables
    lang, prob = langid.classify(text)
    # all potential languages
    print(langid.rank(text))
    return lang, prob
