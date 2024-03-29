# -*- coding: utf-8 -*

# --------------------------------------------------------------------------
# rename_by_content.py (RBC)
#
# (c) 2018-2023, San Vu Ngoc
# University of Rennes 1
#
# --------------------------------------------------------------------------
# Rename files by looking at their contents (even for images if they
# have text) and reorganize them by date (year/month). Useful for
# recovering thousands of files after a crash or accidental deletions
# (as a complement to photorec, for instance).
# --------------------------------------------------------------------------


# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import argparse
import re
import subprocess
import errno
import os
import os.path
from shutil import copyfile, copystat, rmtree
import tempfile
import zipfile
import codecs
import datetime

from unidecode import unidecode
#sudo apt install python3-unidecode

import magic
# sudo apt install python3-magic

import dateparser.search
# sudo apt install python3-dateparser
# (or: sudo pip install dateparser)

import exiftool
# python3 -m pip install -U pyexiftool


#------------------#
# Global variables #
#------------------#

OCR_DIR = None # where to store TXT and OCRed docs
MAX_LINES = 200 # number of lines of text to copy if we cannot detect the first
                # page.
CUSTOM_OCR_DIR = False
FORCE_PDF_OCR = False
MIN_YEAR = 1900
MAX_DATE = datetime.date.today()

# for best results, uncomment the line below and set a maximum date for all
# your files (typically, one day after the crash)
# MAX_DATE = datetime.datetime(2018, 11, 30)

# we use a relative base in the future to make sure we don't take into account
# incomplete parses from dateparser, when the year is absent.
RELATIVE_BASE = datetime.datetime(datetime.date.today().year + 10, 1, 1)

LANG = ['fr']

# French months:
MONTHS_FR = ["janvier", "f(?:é|e)vrier", "mars", "avril", "mai",
          "juin", "juillet", "ao(?:û|u)t",
          "septembre", "octobre", "novembre", "d(?:é|e)cembre"]

# English months:
MONTHS_EN = ["january", "february", "march", "april", "may",
             "june", "july", "august",
             "september", "october", "november", "december" ]

MONTHS = []
RE_MONTH = ""

if 'fr' in LANG:
    MONTHS = MONTHS + MONTHS_FR

if 'en' in LANG:
    MONTHS = MONTHS + MONTHS_EN
    
RE_MONTH = '|'.join(MONTHS)


#-----------------------------------#
# applying OCR on various documents #
#-----------------------------------#

def pdf_to_image(filename):
    """Extract the first page of the pdf to a PNG image"""

    _, image = tempfile.mkstemp(prefix="rbc-image-", suffix = "1.png")
    print ("Generating temporary image %s"%image)
    out = image[:-5] + ".png" # we remove the "1" at the end of the filename
                        # because mutool will add it back...
    ret = subprocess.call(["mutool", "convert",
                           "-o", out,
                           "-O", "resolution=300", filename, "1"])
    if ret == 0 and os.path.isfile(image):
        return (image)
    else:
        print ("RBC ERROR: Pdf extraction failed")
        return (None)

def ppt_to_image(filename):
    """Powerpoint to image"""

    image = os.path.splitext(os.path.basename(filename))[0] + '.png'
    imagedir = tempfile.mkdtemp(prefix = "rbc-" + image[:-4] + "-")
    image = os.path.join(imagedir, image)
    print ("Generating temporary image %s"%image)
    ret = subprocess.call(["libreoffice", "--headless",
                               "--convert-to",  'png', "--outdir",
                                 imagedir, filename])
    if ret == 0:
        return (image)
    else:
        print ("RBC ERROR: Image conversion failed")
        return (None)

def pdf_to_ocr(filename, textfile):
    """Extract text from PDF using OCR on the rendered document image"""

    image = pdf_to_image(filename)
    if image is not None:
        textfile = image_to_txt(image, textfile)
        os.remove(image)
        return (textfile)
    else:
        return (None)


#----------------------------#
# String/filenames utilities #
#----------------------------#

def get_valid_filename(s, convert_accent=True):
    """Return a clean filename"""

    s = s.strip().replace(' ', '_')
    s = s.strip().replace('\000', '')
    if convert_accent:
        s = unidecode(s)  # "ça c'est sûr" ==> "ca c'est sur"
    s = re.sub(r'[^A-Za-z0-9._-]', '_', s)
    s = re.sub(r'_00+', '', s)
    # line above is an adhoc rule because I have many files (generated by photorec) like:
    # 23292344_000_000D_000_000f_000a_000v_000o_000r_000a_000b_000l_000e-ANNEE_UNIVERSITAIRE_2017-2018_DO.pdf
    return (s)

def make_unique_path(path):
    """return a unique path for a file or directory (case sensitive)"""
    count = 1
    base, ext = os.path.splitext(path)
    while os.path.exists(path):
        path = base + ("_%02d"%count) + ext
        count += 1

    return(path)

# https://docs.python.org/2/howto/unicode.html: "Software should only work with
# Unicode strings internally, converting to a particular encoding on output."
# https://docs.python.org/3/howto/unicode.html?highlight=unicode#python-s-unicode-support

def to_utf8(string, encoding='utf-8'):
    """Convert from given encoding to 'unicode' type

    There might be some losses. We never know what we are given,
    especially when reading files.
    """
    if isinstance(string, str):
        return (string)
    else:
        try:
            s = string.decode(encoding)
        except UnicodeDecodeError:
            if encoding == 'ascii': # must be wrong, because ascii wouldn't
                                    # cause errors...
                encoding = 'utf-8'
            print ("RBC ERROR: cannot convert to utf-8 from claimed " + encoding )
            s = string.decode(encoding, errors='replace')
        return (s)

#-------------------------------------#
# Extract information from text files #
#-------------------------------------#

def title_from_txt(textfile):
    """Return probable title in a pure text file, or None"""
    if textfile is None or not os.path.isfile(textfile):
        return None

    print ("Examining " + textfile)
    # we start by reading the first N=12 lines with more than X=50 alphanumeric
    # chars, as the title is often there.
    with open(textfile, 'rt', encoding="utf-8") as f:
        ascii_count = 0
        i = 0
        accum = ""
        for line in f:
            i += 1
            line = to_utf8(line.strip())
            print (i, ascii_count, line)
            line = re.sub(r' (\w) ', r'\1', line) # "S a l u t " --> "Salut "
            line = line.replace('…', '')
            line = re.sub(r'--+', '-', line)
            line = re.sub(r'\.\.+', '.', line)
            line = re.sub(r'\s\s+', ' ', line)
            nascii = len (re.sub(r'[^\w]', '', line))
            if nascii > 40: # then we keep only this one
                print (line)
                return (line)
            else:
                ascii_count += nascii
                line = line if i == 1 else " " + line
                accum += line
                if ascii_count > 50: # X=50. we return the accumulated lines
                    print (accum)
                    return (accum)
            if i > 12: # N=12, ok  ??
                break
    print ("Trying to find another line...")
    # we search for a line with a 4-digit number that could be a year
    # because years often appear in a title.
    with open(textfile, 'rt', encoding="utf-8") as f:
        for line in f:
            line = to_utf8(line.strip())
            years = re.search(r'\b(19|20)\d{2}\b', line) # year 19xx or 20xx
            if years is not None:
                print (line) # TODO test if year is within reasonable range
                y = int(years.group(0))
                if y >= MIN_YEAR: # we don't impose y <= MAKE_DATE.year because
                                  # even a future date can be common in a
                                  # title.
                    return (line)
    return None

def compare_dates(d1,d2):
    return (d1.year < d2.year or (d1.year == d2.year and d1.month <= d2.month))

def max_dates(dates):
    m = datetime.datetime(1,1,1)
    for d in dates:
        if compare_dates(m, d):
            m = d
    if m.year == 1:
        return (None)
    else:
        return (m)

def dateparser_parse(string):
    """Use dateparser to return a (past) date corresponding to the string"""

    try:
        d = dateparser.parse(string, languages=LANG,
                settings={'DATE_ORDER': 'DMY' if 'fr' in LANG else 'YMD',
                          'RELATIVE_BASE': RELATIVE_BASE})
    except: # encoding error?
        print ("RBC ERROR:dateparser.parse")
        return (None)
    return (d if d is not None and compare_dates(d, MAX_DATE) else None)

def dateparser_search(line):
    """Use dateparser to search for dates in a utf8 string

    Recall: we wish to date a document, so only past dates are returned.
    PROBLEM: dateparser.search.search_dates is VERY slow and gives many
    false positives. Don't use this too often...
    """

    print ("Searching for date in line: " + line)
    try:
        p = dateparser.search.search_dates(line,
            settings={'PREFER_DATES_FROM': 'future',
            # WARNING [(u'21/09/17', datetime.datetime(2117, 9, 21, 0, 0))] test/recup_dir.2/f23208752.pdf
            'DATE_ORDER': 'DMY' if 'fr' in LANG else 'YMD',  
            'RELATIVE_BASE': RELATIVE_BASE,
            'PREFER_DAY_OF_MONTH': 'last'})
    except: # probably encoding error, but not only, I've seen dateparser fail
            # with "division by zero" on strings without dates... :(
        print ("RBC ERROR:dateparser")
        return ([])

    if p is not None:
        print (p)
        #dates = list(zip(*p)[1])
        valid_dates = []
        for (string, d) in p:
            # because of "future" settings in dateparser_search, a date like
            # 21/3/14 will give year 2214 instead of 2014... We only allow now + 1
            # year, in order to later reject dates like "3 janvier" without years.
            y = d.year
            if str(y % 100) in string: # at least the last 2 digits must be in string
                if str(y) not in string and d.year > MAX_DATE.year + 1:
                    # this means dateparser must have applied the "future" setting
                    y = d.year - 100
                    print ("Assume year in %s is %u"%(string, y))
                    # Problem: dateparser will translate the string "1827" to
                    # datetime.datetime(2027, 8, 1, 0, 0) !!
                d = datetime.datetime(y, d.month, d.day)
                if compare_dates(d,MAX_DATE) and d.year >= MIN_YEAR: # remove dates in the future
                    valid_dates.append(d)
        print (valid_dates)
        return (valid_dates)
    else:
        return ([])

def complete_year(year):
    if year < 100:
        if year <= MAX_DATE.year % 100:
            year += 2000
        else:
            year += 1900
    return (year)

def validate_date(day, month, year):
    print (year, month, day)
    ok = ( year <= MAX_DATE.year and
           year >= MIN_YEAR
           and day >= 1 and day <= 31 and
           month >= 1 and month <= 12 )
    return (ok)
    
def date_from_string(line):
    """Return a plausible date with a score between 0 and 30

    [line] should be a unicode string."""

    s = re.search(r'(fait|,)\s+le\s+(?P<date>\d+.+?\b((19|20)\d{2})\b)', line, re.I) # ex: "Rennes, le 3 janvier 2018" (FRENCH!)
    if s is not None:
        print (s.group("date"))
        d = dateparser_parse("le " + s.group("date"))
        if d is not None:
            return ((d, 30))

    s = re.search(r'\bdate\s*:\s*(\d+.+?\b((19|20)\d{2})\b)', line, re.I)  # ex: "Date: 3 novembre 2018. Signé: moi"
    if s is not None:
        print (s.group(1))
        d = dateparser_parse(s.group(1))
        if d is not None:
            return ((d, 30))

    s = re.search(r'(\bdate\s*:\s*)', line, re.I)  # ex: "Date: 3/11/18 mais ça s'arrête"
    if s is not None:
        print (line[s.end(1):])
        d = dateparser_search(line[s.end(1):])
        if d != []:
            return ((d[0], 5))

    s = re.search(r'\b(?P<day>\d{1,4})\s*(?P<sep>[/\-:\.])\s*(?P<month>\d{1,2})\s*(?P=sep)\s*(?P<year>(\d{2}\b|\b((19|20)\d{2})\b))', line)
    # ex "Le 03/12/18" (French DMY) (but also tries to detect "2001/1/23")
    # TODO do not try ":", most of the time it's for times, not dates??
    if s is not None:
        print (s.group(0))
        day = int(s.group("day"))
        month = int(s.group("month"))
        year = int(s.group("year"))
        if day // 100 == 19 or day // 100 == 20:
            day, year = year, day
        year = complete_year(year)
        if validate_date (day, month, year):
            d = datetime.datetime(year, month, day)
            if compare_dates (d, MAX_DATE):
                return (d, 10)

    re_year = r'(\d{2}\b|\b((19|20)\d{2})\b)'
    reg = r'(\d*)\s*(%s)\s+%s'%(RE_MONTH, re_year)
    s = re.search(reg, line, re.I)  # ex: "VIE UNIVERSITAIRE MERCREDI 18 FEVRIER 1998'
    if s is not None:
        print (s.group(0))
        d = dateparser_parse(s.group(0))
        # in fact we have all the info to do it directly without using
        # dateparser_parse: day = s.group(1), month = s.group(2) (transform to
        # int), year = s.group(3)
        if d is not None:
            score = 5 if s.group(1) == "" else 10
            return ((d, score))

    # something like "Screenshot_20230504_164636.png":
    s = re.search (r'[_\-\ ](?P<year>(19|20)\d{2})(?P<month>\d{2})(?P<day>\d{2})[_\-\ \.]', line, re.I)
    if s is not None:
        print (s.group(0))
        day = int(s.group("day"))
        month = int(s.group("month"))
        year = int(s.group("year"))
        if validate_date (day, month, year):
            d = datetime.datetime(year, month, day)
            if compare_dates (d, MAX_DATE):
                return (d, 5)
    
    if re.search(r'\b((19|20)\d{2})\b', line) is not None: # ex: "Réunion de 2018-2019"
        y = find_year(line)
        if y is not None:
            return (y, 2)

    return ((None, 0))
 # we could try a desperate dateparser_search but it
 # returns too many false positive.

def max_scores(datelist):
    """Return the list of dates having max score"""

    res = []
    mscore = 0
    for (d, score) in datelist:
        if score > mscore:
            res = [d]
            mscore = score
        elif score == mscore:
            res.append(d)
    return (res)

def date_from_txt(textfile):
    """Return probable date in a pure text file, or None"""
    if textfile is None or not os.path.isfile(textfile):
        return None

    print ("Looking for a date (sic) in " + textfile)
    candidates = []
    with open(textfile, 'rt', encoding="utf-8") as f:
        count = 0
        for line in f:
            line = to_utf8(line.strip())
            count += 1
            if count > MAX_LINES:
                break
            d, score = date_from_string(line)
            count += score
            if d is not None:
                candidates.append((d, score))

    if candidates == []:
        return (None)
    else:
        print (candidates)
        return (max_dates(max_scores(candidates)))


#--------------------------------#
# Convert various formats to txt #
#--------------------------------#

def text_to_txt(filename, textfile, encoding):
    """Convert textfile to utf-8. 'encoding' is the file original
    encoding."""

    # TODO only copy MAX_LINES
    if encoding == 'utf-8':
        copyfile(filename, textfile)
    else:
        print ("Converting %s to utf-8 %s"%(filename, textfile))
        with open(filename, 'rt', encoding="utf-8") as infile, codecs.open(textfile, 'wt', encoding='utf-8') as outfile:
            outfile.writelines([to_utf8(l, encoding) for l in infile.readlines()])
    return (textfile)

def image_to_txt(image, textfile, language="fra"):
    """Run OCR on the image and return the path of the textfile"""
    # put language="fra+eng" to add english language

    base, _ = os.path.splitext(textfile)
    print ("Generating %s using tesseract"%(base + ".txt"))
    ret = subprocess.call(["tesseract", "-l", language, "-c", "tessedit_page_number=0", image, base])
    if ret == 0:
        return(base + ".txt")
    else:
        print ("RBC ERROR: OCR failed")
        return (None)

def pdf_to_txt(filename, base):
    """Return the path of the txt version of the pdf file

    (and generate it if necessary)
    """
    textfile = os.path.join(OCR_DIR, base + ".txt")

    if not FORCE_PDF_OCR:
        if not os.path.isfile(textfile):
            print ("Generating %s"%textfile)
            if subprocess.call(["pdftotext", "-l", "1", filename, textfile]) == 0:
                print ("pdftotext OK")
            else:
                print ("ERROR! continuing anyway")
        else:
            print ("Using already generated %s"%textfile)

        if os.path.isfile(textfile) and os.path.getsize(textfile) > 20:
            return (textfile)

        # (else) now textfile is probably too short to be useful

    ocr_txt = os.path.join(OCR_DIR, base + "_ocr.txt")
    print ("Looking for" + ocr_txt)
    if os.path.isfile(ocr_txt):
        copyfile (ocr_txt, textfile)
    else:
        ocr_pdf = os.path.join(OCR_DIR, base + "_ocr.pdf")
        print ("Looking for" + ocr_pdf)
        if os.path.isfile(ocr_pdf):
            print ("Generating %s"%ocr_txt)
            subprocess.call(["pdftotext", "-l", "1", ocr_pdf, ocr_txt])
        else:
            print ("Trying OCR... please wait")
            ocr_txt = pdf_to_ocr(filename, ocr_txt)
        if ocr_txt is not None and os.path.isfile(ocr_txt):
            copyfile (ocr_txt, textfile)
    if os.path.isfile(textfile):
        return (textfile)
    else:
        return (None)

def doc_to_txt(filename, textfile):
    # sometimes catdoc has a huge memory leak for some bad doc files (and
    # finally abort) so we prefer libreoffice, if available...
    # if os.system("catdoc %s > %s"%(filename, textfile)) == 0:
    ret = subprocess.call(["libreoffice", "--headless",
                           "--convert-to",  'txt:Text (encoded):UTF8', "--outdir",
                               os.path.dirname(textfile), filename])
    if ret == 0 and os.path.isfile(textfile):
        return (textfile)
    else:
        return (None)

def tar_to_txt(filename, textfile):
    """Extract list of files"""

    if os.system("tar -t -f %s > %s"%(filename, textfile)) == 0:
        return (textfile)
    else:
        return (None)

def zip_to_txt(filename, textfile):
    """Extract list of files

    And write date of first file on first line"""

    if zipfile.is_zipfile(filename):
        z = zipfile.ZipFile(filename)
        l =  z.namelist()
        l = [ to_utf8(n) for n in l ]
        if not l == []:
            date = z.getinfo(l[0]).date_time
            with codecs.open(textfile, 'w', encoding='utf-8') as f:
                f.write (l[0] + " %u/%u/%u\n"%(date[0], date[1], date[2]))
                f.write ('\n'.join(l)) # TODO only write MAX_LINES
            return (textfile)
        else:
            return (None)
    else:
        return (None)

def pandoc_to_txt(filename, textfile):

    print ("Converting %s to %s using pandoc"%(filename, textfile))
    if subprocess.call(["pandoc", "-o", textfile, filename]) == 0:
        return (textfile)
    else:
        return (None)

def ods_to_txt(filename, textfile):
    #https://wiki.openoffice.org/wiki/Documentation/DevGuide/Spreadsheets/Filter_Options#Filter_Options_for_the_CSV_Filter

    ret = subprocess.call(["libreoffice", "--headless",
                           "--convert-to",  'csv:Text - txt - csv (StarCalc):32,ANSI,76',
                               "--outdir", os.path.dirname(textfile), filename])
    base = os.path.splitext(textfile)[0]
    if ret == 0 and os.path.isfile(base + ".csv"):
        copyfile(base + ".csv", textfile)
        return (textfile)
    else:
        ret = subprocess.call(["libreoffice", "--headless",
                               "--convert-to",  'txt', "--outdir",
                                   os.path.dirname(textfile), filename])
        if ret == 0 and os.path.isfile(textfile):
            return (textfile)
        else:
            return (None)

def mbox_to_txt(filename, textfile):
    """Insert a date at the start of the file"""

    date = ""
    with open(filename, 'tr', encoding="utf-8") as f:
        for line in f:
            line = to_utf8(line)
            if line.startswith("Date: "):
                date = line
                break

    # TODO  only copy MAX_LINES
    with open(filename, 'tr', encoding="utf-8") as infile, open(textfile, 'tw', encoding="utf-8") as outfile:
        outfile.write("MailBox %s\n"%date)
        outfile.writelines(infile.readlines())
        # doing this we also convert the various line feeds into standard '\n'
        # which a simple os.system('cat ' + filename + " >> " + textfile)
        # would not do.
        return (textfile)

def file_to_txt(filename, base, extension):

    textfile = os.path.join(OCR_DIR, base + ".txt")
    if os.path.isfile(textfile):
        print ("Using already generated %s"%textfile)
        return (textfile)
    else:
        if extension in ['pdf', 'ai']:
            return (pdf_to_txt(filename, base))
        elif extension == 'doc':
            return (doc_to_txt(filename, textfile))
        elif extension == 'tar':
            return (tar_to_txt(filename, textfile))
        elif extension == 'zip':
            return (zip_to_txt(filename, textfile))
        elif extension in ['txt-ascii', 'txt-utf-8']: #, 'txt-iso-8859-4']:
            copyfile(filename, textfile)
            return (textfile)
        elif extension == 'mbox':
            return (mbox_to_txt(filename, textfile))
        elif extension in ['ods', 'xls', 'xlsx']:
            return (ods_to_txt(filename, textfile))
        elif extension in ['docx', 'docm', 'html', 'rtf', 'odt']:
            return (pandoc_to_txt(filename, textfile))
        elif extension in ['png', 'jpg', 'gif', 'bmp', 'tif']:
            return (image_to_txt(filename, textfile))
        elif extension in ['ppt', 'pptx', 'odg']:
            image = ppt_to_image(filename)
            if image is not None:
                #TODO remove the temp directory
                return (image_to_txt(image, textfile))
            else:
                return (None)
        else:
            print ("Filetype %s not supported"%extension)
            return (None)

#----------------------#
# exiftool information #
#----------------------#

def get_tag(et, tag, filename):
    """Get string tag, or None"""

    # without the exiftool binding, one could do instead, for instance:
    # title = subprocess.check_output(["exiftool", "-Title", "-s",  "-S",  filename])
    try:
        dic = et.get_tags(filename, tags=[tag])[0]
    except exiftool.exceptions.ExifToolExecuteError:
        print ("ExifToolExecuteError")
        return (None)
    src = dic.pop("SourceFile")
    print ("Tag src = " + src)
    values = []
    for k, v in dic.items():
        values.append(v)
    if values == []:
        print ("Cannot get tag [%s]"%tag)
        return None
    else:
        if len (values) > 1:
            print ("EXIF: multiplies values for [%s]"%tag)
            print (values)
        return (values[0])

def find_title(et, filename, extension):
    """Return probable title = (old_title, new_title).

    old_title will be empty if it has no interesting content.
    """

    basename = os.path.basename(filename)
    base, _ = os.path.splitext(basename)
    numbers = len(''.join(re.findall(r'\d+', base)))
    if len(base) - numbers >= 2:
        prefix = base
        # if the original filename is not full of number, it is probably best
        # to keep it
    else:
        print ("We discard the original filename [%s]"%base)
        prefix = ""

    title = get_tag(et, "Title", filename)
    if title is not None and len(title) >= 3:
        print ("Title=" +  title)
        if (get_valid_filename(title)) in filename:
            print ("Title is already in filename: we don't modify.")
            return ((base, ""))
        else:
            return ((prefix, title))
    else:
        print ("No Title tag, we try scanning the text.")
        textfile = file_to_txt(filename, base, extension)

        author = None
        creator = None
        title = title_from_txt(textfile)
        if title is None:
            title = ""
        if len(title) < 20:
            author = get_tag(et, "Author", filename)
            if author is not None:
                print ("Author=" + author)
            if len(title) < 5:
                creator = get_tag(et, "Creator", filename) # only for PDF?
                if creator is not None:
                    print ("Creator=" +  creator)
                    creator = creator[:10]
                    # truncate to the first 10 chars
        new_title = '-'.join(filter(None, [title, author, creator]))
        if new_title == "" and prefix == "":
            print ("Could not find any content. Using original file name")
            prefix = base
        return ((prefix, new_title))

def find_year(string): # dateparser_search is sometimes
                       # more precise, and can find the month
    """Find a plausible year in a string (returns a string or None)"""

    years = re.findall(r'\b((19|20)\d{2})\b', string)
    # eg: years = [('2018', '20')]
    yn = MAX_DATE.year
    years = [ y[0] for y in years if int(y[0]) <= yn and int(y[0]) >= MIN_YEAR ]
    if not years == []:
        year = max(years)
        #year = max(zip(*years)[0])
        print ("Let's say the year is %s..."%year)
        return (datetime.datetime(int(year), 1, 1)) # we choose 1rst of January as "improbable"
    else:
        return (None)

def year_month_from_date(date):
    """Return (date,month) strings from datetime object"""
    year, month = None, None
    if date is not None:
        # because of "future" settings in dateparser_search, a date like
        # 21/3/14 will give year 2214 instead of 2014... We only allow now + 1
        # year, in order to later reject dates like "3 janvier" without years.
        # TODO move this test in dateparser_search:
        y = date.year - 100 if date.year > MAX_DATE.year +1 else date.year
        year = str(y)

        month = (None if date.month == 1 and date.day == 1 else str(date.month))
    return ((year, month))

def find_date(et, filename, title, extension):
    """Try to guess the date"""

    # do NOT use FileModifyDate, this was probably reset when
    # recovering data by photorec
    search_tags = [ "ModifyDate", "CreateDate" ]
    if extension in [ 'pdf', 'ai' ]:
        search_tags.insert(0,"PDF:ModifyDate") # see below why
    if extension == "zip":
        search_tags.append("ZipModifyDate")
    elif extension in ['ods', 'odt']:
        search_tags.append("Date")
        search_tags.append("Creation-date")
        # TODO add more tags
    exifdates = []
    # for easier debugging we first print all the date tags we consider:
    for tag in search_tags:
        print (tag)
        d = get_tag(et, tag, filename)
        if d is not None:
            print (tag + "=" + d)
            exifdates.append(d)
    # and now we chose the first valid date:
    for d in exifdates:
        date = None
        for pattern in ["%Y:%m:%d", "%d/%m/%y", "%d/%m/%Y", "%d %B %Y"]:
            # I don't know why for test/recup_dir.2/f26378280.ai we get
            # "CreateDate=09/01/17 12:23"
            # this is due to the python exiftool binding, from the command line this is ok
            # exiftool -d "%Y:%m:%d" -CreateDate -s -S test/recup_dir.2/f26378280.ai
            # To show why the error occurs, see:
            # exiftool -d "%Y:%m:%d" -time:all -a -G0:1 -s test/recup_dir.2/f26378280.ai
# [File:System]   FileModifyDate                  : 2018:11:16
# [File:System]   FileAccessDate                  : 2018:12:10
# [File:System]   FileInodeChangeDate             : 2018:12:05
# [XMP:XMP-xmp]   MetadataDate                    : 2017:01:09
# [XMP:XMP-xmp]   ModifyDate                      : 2017:01:09
# [XMP:XMP-xmp]   CreateDate                      : 2017:01:09
# [XMP:XMP-xmpMM] HistoryWhen                     : 2017:01:09
# [PostScript]    CreateDate                      : 09/01/17 12:23
# [PDF]           CreateDate                      : 2017:01:09
# [PDF]           ModifyDate                      : 2017:01:09

            try:
                date = datetime.datetime.strptime(d.split(' ')[0], pattern)
                break
            except ValueError:
                print ("RBC ERROR: strptime")
        if date is not None:
            return ((date.year, date.month))
        else:
            p = dateparser_search(d)
            if p != []:
                return (year_month_from_date(max_dates(p)))
            else:
                print ("Cannot guess any date format! (very rare)")

    print ("Cannot find date. Trying to scan title.")
    d, _ = date_from_string(title)
    # TODO chercher aussi Screenshot_20230504_164636.png
    if d is not None:
        print (d)
        return (year_month_from_date(d))
    else:
        print ("Cannot find date in title, we try scanning the text.")
        base, _ = os.path.splitext(os.path.basename(filename))
        textfile = file_to_txt(filename, base, extension)
        return (year_month_from_date(date_from_txt(textfile)))


def mkdir(path):
    # python 3 could do this:
    # os.makedirs(OCR_DIR, exist_ok=True)
    try:
        os.mkdir(path)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise

def check_txt_file_type(textfile, encoding='ascii'):
    """Try to guess what kind of textfile this is"""

    print ("Trying to guess what kind of textfile this is")
    with open(textfile, 'r', encoding="utf-8") as f:
        for line in f:
            line = to_utf8(line, encoding)
            if (line.startswith("Received: from ") or
                    line.startswith("Message-ID:") or
                    line.startswith("Message-Id:")) :
                print ("File %s looks like a mailbox"%textfile)
                return ('mbox')
            # TODO add more tests
    return ('txt-'+encoding)

#--------------#
# Magic lookup #
#--------------#

def find_type(et, filename):
    """Return a normalized extension representing the file type"""

    # For instance, 'pdf'. In the special case of txt files, we concatenate
    # the detected encoding, as in 'txt-utf-8'.
    extension = get_tag(et, "FileTypeExtension", filename)
    if extension is not None and extension != "":
        return (extension.lower())
    else:
        typ = magic.from_file(filename)
        print ("MAGIC TYPE= " + typ)
        if "text" in typ:
            if "ISO-8859" in typ:
                encoding = "iso-8859-1"
            elif "UTF-8" in typ:
                encoding = "utf-8"
            else:
                encoding = "ascii" # TODO add more encodings
            return (check_txt_file_type (filename, encoding))
        else: # TODO more types (html, ...)
            return (os.path.splitext(filename)[1].lower()[1:])



def rename(et, filename, newdir, dry, keep):
    """Guess name and date of filename according to its content

    Returns a path of the form YEAR/MONTH/TITLE.ext
    """

    extension = find_type(et, filename)
    print ("Extension=" + extension)
    old_title, new_title = find_title(et, filename, extension)
    title = '-'.join(filter(None, [old_title, new_title]))
    print ("proposed title=" + title)
    year, month = find_date(et, filename, title, extension)
    if year is None:
        year = "Unknown_year"
        month = ""
    else:
        year = str(year)
        if month is None:
            month= "Unknown_month"
        else:
            month = "%02d"%(int(month))
    print ("year=%s, month=%s"%(year, month))
    directory = os.path.join(newdir, year)
    if not dry:
        mkdir(directory)
    directory = os.path.join(directory, month)
    if not dry:
        mkdir(directory)

    if not keep:
        # we remove too many _s and truncate at 100 chars
        title = re.sub(r'_{2,}', '_', get_valid_filename(title))[:100]
        if extension[0:3] == 'txt':
            extension = 'txt'
        path = os.path.join(directory, title + "." + extension)
    else:
        path = os.path.join(directory, os.path.basename(filename))
        new_title = old_title
    newfile = make_unique_path(path)
    print ("sanitized version=" + newfile)
    print ("%s copying [%s] to [%s]"%(not dry, filename, newfile))

    if not dry:
        copyfile(filename, newfile)
        try:
            copystat(filename, newfile)
        except OSError:
            pass
    return (newfile, new_title)


# --------------------------#
# This is the main function #
# --------------------------#
def batch(flist, newdir, dry = False, ocr_dir = None, keep = False):
    """Find a name and a date for each file in [flist]

    and copy then into [newdir] (if [dry] is [False]). If ocr_dir is not
    specified, a new tmp dir will be created.
    """
    global OCR_DIR, CUSTOM_OCR_DIR

    if ocr_dir is None:
        OCR_DIR = tempfile.mkdtemp(prefix='rbc-ocr_')
        CUSTOM_OCR_DIR = False
        print ("Notice: Will save text data in " + OCR_DIR)
    else:
        if ocr_dir != OCR_DIR:
            OCR_DIR = ocr_dir
            CUSTOM_OCR_DIR = True
        print ("Notice: Will use/save text data from/to " + OCR_DIR)
    created = []
    not_treated = []
    remaining = list(flist) # we make a copy
    et = exiftool.ExifToolHelper()
    i = 0
    n = len(flist)
    for filename in flist:
        i += 1
        print ("")
        print ("----------------------------------------------------------------")
        print ("---(%u/%u)--- Processing "%(i,n) + filename)
        print ("----------------------------------------------------------------")

        assert (remaining.pop(0) == filename)
        if os.path.isfile(filename):
            #try:
            newfile, title = rename(et, filename, newdir, dry, keep)
            #except:
            #    print ("---- Unexpected error:", sys.exc_info())
            #    print ("Quitting")
            #    return (created, remaining)
            created.append([filename, newfile, title])
        else:
            not_treated.append(filename)
            if os.path.isdir(filename):
                print ("WARNING: Skipping directory " + filename)
            else:
                print ("WARNING: Skipping " + filename)
    et.terminate()
    return (created, not_treated + remaining)


def printf(f, string):
    """Print [string] to console and file"""
    print (string)
    f.write (string)
    f.write('\n')


#---------------------#
# Command-line Script #
#---------------------#

def script ():
    global FORCE_PDF_OCR
    print ("""
Welcome to 'rename_by_content'
by San Vu Ngoc, University of Rennes 1.
""")
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--dry", action="store_true",
                        help="don't copy the files (but still create some files in the ocr dir)")
    parser.add_argument("-k", "--keep", action="store_true",
                        help="keep the original filename, only detect the date for reorganizing")
    parser.add_argument("-b", "--batch", action="store_true",
                        help="don't ask questions")
    parser.add_argument("--output", '-o', help="output directory")
    parser.add_argument("--log", '-l', help="summary log file")
    parser.add_argument("--ocrdir", help="where to store (and look for) converted text files")
    parser.add_argument("--force_pdf_ocr", action="store_true", help="Always use OCR to extract text from PDF files")
    parser.add_argument('files', nargs='+')

    args = parser.parse_args()

    FORCE_PDF_OCR = args.force_pdf_ocr

    print ("This program comes with ABSOLUTELY NO WARRANTY")
    print ("Make sure you have a copy of all your data before proceeding")
    if not args.batch:
        input ("Press enter to continue...")

    if args.ocrdir is not None:
        mkdir(args.ocrdir)
    output = make_unique_path ("output") if args.output is None else args.output
    mkdir(output)
    renamed, remaining = batch(args.files, output, args.dry, args.ocrdir, args.keep)
    print ("")
    summary = make_unique_path ("summary.log") if args.log is None else args.log
    with codecs.open(summary, 'w', encoding='utf-8') as f:
        printf (f, "-------------------------------- Summary of renamed files: --------------------------------")
        for [file, newfile, title] in renamed:
            #title = to_utf8(title) # should not be necessary
            line = "[%s] was copied to [%s] (%s)"%(file, newfile, title)
            printf (f, line)
        if not remaining == []:
            printf (f, "---- WARNING: Some files were not copied:")
            printf (f, str(remaining))
        printf (f, "------------------- Done. Copied %u of %u files to %s ---------------------\n"%(len(renamed), len(args.files), output))


if __name__ == "__main__":
    script ()

#-----------------------------------------------#
# Some helper functions, not used by the script #
#-----------------------------------------------#


# Minimal test
def test():
    newdir = "/tmp/Nouveaux"
    created, failed = batch(["aaa.pdf"], newdir, True)
    print (created, failed)


def remove_from_summary(summary):
    """Use this to remove all files that have been copied in a previous

    round of rename_by_content.  It is useful in case you want to
    recreate them: if you don't remove the files before recreating, they
    will be duplicated (with a _01, _02, etc. suffix). In order to do
    this you need the "summary.log" file.
    """

    with open(summary, "rt", encoding="utf-8") as f:
        for line in f:
            line = to_utf8(line)
            s = re.search(r'\] was copied to \[(.+)\] \(', line) # TODO this is not safe
            if s is not None:
                file = s.group(1)
                print ("Remove " + file)
                os.remove(file)

def copy_unique(src_dir, dst_dir, errors=0):
    """disjoint union of all files into new_dir

    Case sensitive
    SKIPS all symlinks"""

    print ("Entering directory " + src_dir)
    if not os.path.isdir(dst_dir):
        print ("Creating directory " + dst_dir)
        os.makedirs(dst_dir)
    names = os.listdir(src_dir)
    for name in names:
        src_name = os.path.join(src_dir, name)
        dst_name = os.path.join(dst_dir, name)
        if os.path.isfile(src_name):
            dst_name = make_unique_path(dst_name)
            print ("Copy %s to %s"%(src_name, dst_name))
            copyfile(src_name, dst_name)
            copystat(src_name, dst_name)
        elif os.path.isdir(src_name):
            copy_unique(src_name, dst_name, errors)
        else:
            print ("--- ERROR: What is %s ??"%name)
            errors += 1

def get_multiple_tag(dic, tag):
    """Return all the exif values that have the same tag

    (This can happen, for instance, for CreateDate)
    """
    return ([dic[i] for i in dic.keys() if i.split(':')[-1] == tag])

def get_ocr_dir():
    return(OCR_DIR)

def clear_ocr():
    """Remove ocr dir. WARNING: no confirmation is asked!"""

    if CUSTOM_OCR_DIR or not ("rbc-ocr_" in OCR_DIR):
        print ("ERROR: I will not remove %s because it was created by user"%OCR_DIR)
    else:
        print ("Removing %s and all its contents"%OCR_DIR)
        rmtree(OCR_DIR)
