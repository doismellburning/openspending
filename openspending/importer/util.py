from urllib import urlopen
from messytables.ilines import ilines

def urlopen_lines(url):
    """Yield lines from a URL"""
    return ilines(urlopen(url))


