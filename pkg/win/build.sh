#!/bin/sh


if [ "x$1" = "xtest" ]; then
    ./wine-debug.sh python setup.py py2exe
    ./wine-debug.sh python setup.py py2exe
    python pkg/win/fix_pe.py

else
    ./wine.sh python setup.py py2exe
    ./wine.sh python setup.py py2exe
    python pkg/win/fix_pe.py
fi




