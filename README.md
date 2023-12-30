# rename_by_content (RBC)
_Automatically rename files and reorganize by looking at their contents._

RBC is a python script that can be used to automaticall guess
(hopefully) useful names and dates for files. It was written to
recover thousands of files that were deleted by mistake and partially
recovered by the excellent tool `photorec`. Running RBC on a file
will, by default:

+ try to find a better name for that file, and
+ make a copy of that file with the new name in a new folder of the
  type `YEAR/MONTH/`.

Supported file formats are:

pdf, ai, doc, tar, zip, txt, mbox, ods, xls, xlsx, docx, docm, html,
rtf, odt, png, jpg, gif, bmp, tif, ppt, pptx ,odg

For images, RBC uses optical character recognition (OCR) to try and
extract information.

## Requirements

* A linux machine with several opensource utilities (should work on a
  mac too, in principle):

	- [exiftool](https://www.sno.phy.queensu.ca/~phil/exiftool/)
	  (extract files metadata). Please make sure that your exiftool
	  install is complete. For instance, find a `.docx` file and run
	  `exiftool myfile.docx`: then
	  check the result for the line:  
	  `File Type Extension : docx`
	- [tesseract](https://github.com/tesseract-ocr/tesseract) (great OCR program). Use version 4 for best results (there is a ppa for ubuntu, see [here](https://github.com/tesseract-ocr/tesseract/wiki))
	- [libreoffice](https://www.libreoffice.org/) (to convert office documents to txt)
	- pdftotext (usually included in any linux distro; otherwise install `poppler-utils`)
	- mutool (convert pdf to image. `sudo apt install mupdf-tools`. This one can be replaced by its many equivalents. But [mupdf](https://mupdf.com/) is great.)
	- [pandoc](https://pandoc.org/) (`sudo apt install pandoc`)

* Python 2.7

  With additional packages:

  - [pyexiftool](https://smarnach.github.io/pyexiftool/) (download directly from [here](https://raw.githubusercontent.com/smarnach/pyexiftool/master/exiftool.py))
  - magic (`sudo apt install python-magic`)
  - dateparser (`sudo pip install dateparser`)

## Installation

* download [rename_by_content.py](https://github.com/sanette/rename_by_content/blob/master/rename_by_content.py)

* download [exiftool.py](https://raw.githubusercontent.com/smarnach/pyexiftool/master/exiftool.py) in the same directory

* make sure the other tools mentioned above are installed on your system

## Usage

### Command-line usage

```
python ./rename_by_content.py [-h] [-d] [-k] [-b]  
                              [--output OUTPUT]
                              [--log LOG]  
                              [--ocrdir OCRDIR]  
                              files [files ...]
```

Search for a title and a date for all `files`, and copy the renamed
files in `OUTPUT`. Inside the `OUTPUT` dir, paths have the form
`year/month/name_of_file.ext`. For instance `2018/02/example.pdf`.  By
default, the `OUTPUT` directory is called `output`.

The name is misleading, it actually _copies_ the files in the `OUTPUT`
directory. The original files are not affected (apart from being read,
of course).

* `files` can be the path of a single file, or a shell syntax of the
  form `dir/*` if you want to treat all files in the `dir` directory.

* After running RBC, the directory `OCRDIR` will contain all the texts
  extracted from the given `files`. If you run RBC a second time with
  the same `OCRDIR`, it will use the previously generated text, and
  hence run much faster. On the other hand, it is safe to delete the
  `OCRDIR` directory to force re-starting text extraction when running
  RBC again.

* The `LOG` file contains a list of all operations done, and the list
  of errors. This file can be use to cancel the operation, that is,
  remove all files that have been copied. For this, use the python
  function `remove_from_summary`. By default, the `LOG` file is called
  `summary.log`.

* `-b` or `--batch`: Batch mode: doesn't wait for user input.

* `-d` or `--dry`: Dry-run mode: does everything _but_ the final
  copy. However, the text files are generated in `OCRDIR` and the
  `LOG` is written.

* `-k` or `--keep`: Keep the original filename, but do all the
  analysis to guess a date, and copy the file to the corresponding
  folder. If several files from different directories have the same
  name, don't worry, a number will be appended to their name to
  distinguish them.

### Examples

`python ./rename_by_content.py -o /tmp/newfiles /home/joe/recup_dir/*`

This will examine all files in `/home/joe/recup_dir/*` and copy them,
with new names, into `/tmp/newfiles`, organized according to their
date (`year/month`).

___

`python ./rename_by_content.py -k -o My_PDFs Documents/*.pdf`

This will examine all files with the `pdf` extension in the
`Documents` folder, and copy them (with the same name) into the
`My_PDFs` folder, organized according to their date (`year/month`).

### In python programs

See the file [`example.py`](https://github.com/sanette/rename_by_content/blob/master/example.py).

Essentially your have to do

```
import rename_by_content as rbc
```

and then you may use the function

 - `rbc.batch(files, newdir)`, which will treat all `files` and copy
   them with their new title in `newdir`.

   You may also use the optional arguments `dry` and `ocr_dir`:
     * `dry` is a boolean. If true, the final copy is _not_ done.
     * `ocr_dir` is the path of the temporary directory used to store
       texts extracted from the files.

_Other utilities:_

 - `rbc.mkdir(path)`: create the `path` directory if it does not exist.
 
 - `rbc.ocr_dir()`: return the temporary directory used for storing
   extracted texts.

 - `rbc.clear_ocr()`: remove that temporary directory.

 - `rbc.copy_unique(src_dir, dst_dir)`: copy all files from `src_dir` into
   `dst_dir`, but never overwrites: if a file with the same name
   already exists in `dst_dir`, the file from `src_dir` will have a
   numbered suffix like '_01'.

   This is useful if you have run `rbc.batch` with several destination
   directories, and finally you want to group everything in the same
   location.

### TODO

- Language detection (English, French, etc.) for better date recognition.

  Currently you have to edit yourself the `MONTHS` variable if your
  documents are not in French.
