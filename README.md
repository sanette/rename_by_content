# rename_by_content (RBC)
_Automatically rename files by looking at their contents._

RBC is a python script that can be used to automaticall guess (hopefully) useful names and dates for files. It was written to recover thousands of files that were deleted by mistake and partially recovered by the excellent tool `photorec`.

Supported file formats are:
pdf, ai, doc, tar, zip, txt, mbox, ods, xls, xlsx, docx, docm, html, rtf, odt, png, jpg, gif, bmp, tif, ppt, pptx ,odg

For images, RBC uses optical character recognition (OCR) to try and extract information.

## Requirements

* A linux machine with several opensource utilities (should work on a
  mac too, in principle):

  - exiftool (extract files metadata)
  - tesseract (great OCR program). Use version 4 for best results (there is a ppa for ubuntu, see [here](https://github.com/tesseract-ocr/tesseract/wiki))
  - libreoffice (to convert office documents to txt)
  - pdftotext
  - mudraw (convert pdf to image. `sudo apt install mupdf-tools`. This one can be replaced by its many equivalents. But [mupdf](https://mupdf.com/) is great.)
  - [pandoc](https://pandoc.org/) (`sudo apt install pandoc`)

* Python 2.7

  With additional packages:

  - [exiftool](https://smarnach.github.io/pyexiftool/) (download directly from [here](https://raw.githubusercontent.com/smarnach/pyexiftool/master/exiftool.py))
  - magic (`sudo apt install python-magic`)
  - dateparser (`sudo pip install dateparser`)
