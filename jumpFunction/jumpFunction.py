# -*- coding: utf-8 -*-
# @Author: wcq
# @Date:   2018-06-28 16:37:32
# @Last Modified by:   wcq
# @Last Modified time: 2018-06-29 12:39:58

import sublime
import sublime_plugin
import re
from itertools import zip_longest
from pprint import pprint
import os

class findNextBlockCommand(sublime_plugin.WindowCommand):
    def run(self, character=None):
        print('character : ', character)
        view = self.window.active_view()
        sel = view.sel()[0]
        prePos = sel
        for pos in view.find_all('(^[a-z])', sublime.IGNORECASE):
            if (pos.begin() > sel.begin()) and (prePos.begin() <= sel.begin()):
                view.show_at_center(pos)
                last_sel = view.sel()
                last_sel.clear()
                last_sel.add(pos)
            if pos != prePos:
                prePos = pos

class findPreBlockCommand(sublime_plugin.WindowCommand):
    def run(self, character=None):
        print('character : ', character)
        view = self.window.active_view()
        sel = view.sel()[0]
        prePos = sel
        for pos in view.find_all('(^[a-z])', sublime.IGNORECASE):
            if (pos.begin() >= sel.begin()) and (prePos.begin() < sel.begin()):
                view.show_at_center(prePos)
                last_sel = view.sel()
                last_sel.clear()
                last_sel.add(prePos)
            if pos != prePos:
                prePos = pos

class findNextFunctionCommand(sublime_plugin.WindowCommand):
    def run(self, character=None):
        print('character : ', character)
        view = self.window.active_view()
        sel = view.sel()[0]
        prePos = sel
        for pos in view.find_all('(^[a-z])|(def )', sublime.IGNORECASE):
            if (pos.begin() > sel.begin()) and (prePos.begin() <= sel.begin()):
                view.show_at_center(pos)
                last_sel = view.sel()
                last_sel.clear()
                last_sel.add(pos)
            if pos != prePos:
                prePos = pos

class findPreFunctionCommand(sublime_plugin.WindowCommand):
    def run(self, character=None):
        print('character : ', character)
        view = self.window.active_view()
        sel = view.sel()[0]
        prePos = sel
        for pos in view.find_all('(^[a-z])|(def )', sublime.IGNORECASE):
            if (pos.begin() >= sel.begin()) and (prePos.begin() < sel.begin()):
                view.show_at_center(prePos)
                last_sel = view.sel()
                last_sel.clear()
                last_sel.add(prePos)
            if pos != prePos:
                prePos = pos



