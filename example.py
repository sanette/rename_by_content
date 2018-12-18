# rename_by_content: example
# San Vu Ngoc, 2018
#
# This sample code looks at all files in the directory "test/recup_dir.2" and
# copy them with their new names in "/tmp/newdir"

import os

import rename_by_content as rbc

dir = "test/recup_dir.2"
files = [os.path.join(dir,f) for f in os.listdir(dir)]
newdir = "/tmp/newdir"
rbc.mkdir(newdir) # this will create the directory if it does not exist

# here we run RBC.
copied, errors = rbc.batch(files, newdir)

# and we show the result.
print ("\nCopied files:")
if copied == []:
    print ("None")
else:
    for f in copied:
        print (f)

print ("")

if errors != []:
    print ("\nWarning: the following files were not copied:")
    for f in errors:
        print (f)


# now we try another time (on a subset of the files) to check that the
# previously extracted texts are used.
files = [f for f in files if f.endswith('odt')]
copied, errors = rbc.batch(files, newdir, ocr_dir = rbc.ocr_dir())

# finally we clear the temporary OCR directory.
rbc.clear_ocr()
