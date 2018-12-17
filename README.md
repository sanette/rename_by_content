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

## Installation

* download [rename_by_content.py](https://github.com/sanette/rename_by_content/blob/master/rename_by_content.py)

* download [exiftool.py](https://raw.githubusercontent.com/smarnach/pyexiftool/master/exiftool.py) in the same directory

* make sure the other tools mentioned above are installed on your system

## Usage

```
python ./rename_by_content.py [-h] [-d] [-b]  
                              [--output OUTPUT]
                              [--log LOG]  
                              [--ocrdir OCRDIR]  
                              files [files ...]
```

Search for a title and a date for all `files`, and copy the renamed
files in `OUTPUT`.

The name is misleading, it actually _copies_ the files in the `OUTPUT`
directory. The original files are not affected (apart from being read,
of course).

* `files` can be the path of a single file, or a shell syntax of the
  form `dir/*` if you want to treat all files in the `dir` directory.

* The directory `OCRDIR` contains all the texts extracted from the
  given `files`. If you run RBC a second time with the same `OCRDIR`,
  it will use the previously generated text, and hence run much
  faster.

* The `LOG` file contains a list of all operations done, and the list
  of errors. This file can be use to cancel the operation, that is,
  remove all files that have been copied. For this, use the python
  function `remove_from_summary`.

* `-b` or `--batch`: Batch mode: doesn't wait for user input.

* `-d` or `--dry`: Dry-run mode: does everything _but_ the final
  copy. However, the text files are generated in `OCRDIR` and the
  `LOG` is written.
  
