"""
    KeepNote
    Extension system
"""

#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
#  Author: Matt Rasmussen <rasmus@mit.edu>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA.
#

import os

import keepnote


def dependency_satisfied(ext, dep):
    """Checks whether an extension satisfies a dependency"""

    name, rel, version = dep

    if ext is None:
        return (rel == "!=")

    if rel == ">":
        if not (ext.version > version): return False
    elif rel == ">=":
        if not (ext.version >= version): return False
    elif rel == "==":
        if not (ext.version == version): return False
    elif rel == "<=":
        if not (ext.version <= version): return False
    elif rel == "<":
        if not (ext.version < version): return False

    return True


class DependencyException (Exception):
    
    def __init__(self, ext, dep):
        self.ext = ext
        self.dep = dep


    def __str__(self):
        return "Extension '%s' has failed dependency %s" % (self.ext.key, self.dep)


class Extension (object):
    """KeepNote Extension"""

    version = (1, 0)
    key = ""
    name = "untitled"
    description = "base extension"


    def __init__(self, app):
        
        self._app = app
        self._enabled = False
        self.__windows = set()

        self.__uis = set()


    def enable(self, enable):

        # check dependencies
        for dep in self.get_depends():
            if not self._app.dependency_satisfied(dep):
                raise DependencyException(self, dep)

        self._enabled = enable

        if enable:
            for window in self.__windows:
                if window not in self.__uis:
                    self.on_add_ui(window)
                    self.__uis.add(window)
        else:
            for window in self.__uis:
                self.on_remove_ui(window)
            self.__uis.clear()

        # call callback for app
        self._app.on_extension_enabled(self, enable)

        # call callback for enable event
        self.on_enabled(enable)

        # return whether the extension is enabled
        return self._enabled

    def is_enabled(self):
        """Returns True if extension is enabled"""
        return self._enabled

    def on_enabled(self, enabled):
        """Callback for when extension is enabled/disabled"""
        return True


    def get_depends(self):
        """
        Returns dependencies of extension

        Dependencies returned as a list of tuples (NAME, REL, VERSION)

        NAME is a string identify an extension (or 'keepnote' itself).
        VERSION is a tuple representing a version number.
           ex: the tuple (0, 6, 1) represents version 0.6.1
        REL is a string representing a relation.  Options are:
           '>='   the version must be greater than or equal to
           '>'    the version must be greater than
           '=='   the version must be exactly equal to
           '<='   the version must less than or equal to
           '<'    the version must be less than
           '!='   the version must not be equal to

        All dependencies must be met to enable an extension.  A extension
        name can appear more than once if several relations are required
        (such as specifying a range of valid version numbers).

        """

        return [("keepnote", ">=", (0, 6, 1))]

    #===============================
    # filesystem paths

    def get_base_dir(self, exist=True):
        """Returns the directory containing the extensions code"""
        path = self._app.get_extension_base_dir(self.key)
        if exist and not os.path.exists(path):
            os.makedirs(path)
        return path


    def get_data_dir(self, exist=True):
        """Returns the directory for storing data specific to this extension"""
        path = self._app.get_extension_data_dir(self.key)
        if exist and not os.path.exists(path):
            os.makedirs(path)
        return path

    def get_data_file(self, filename, exist=True):
        """
        Returns a full path to  a file within the extension's data directory
        """
        return os.path.join(self.get_data_dir(exist), filename)

    
    #================================
    # window interactions

    def on_new_window(self, window):
        """Initialize extension for a particular window"""

        if self._enabled:
            self.on_add_ui(window)
            self.__uis.add(window)
        self.__windows.add(window)


    def on_close_window(self, window):
        """Callback for when window is closed"""
     
        if window in self.__windows:
            if window in self.__uis:
                self.on_remove_ui(window)
                self.__uis.remove(window)
            self.__windows.remove(window)

    def get_windows(self):
        """Returns windows associated with extension"""
        return self.__windows
            

    #===============================
    # UI interaction

    def on_add_ui(self, window):
        pass

    def on_remove_ui(self, window):
        pass

    def on_add_options_ui(self, dialog):
        pass

    def on_remove_options_ui(self, dialog):
        pass

