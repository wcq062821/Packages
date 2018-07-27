# -*- coding: utf-8 -*-
# @Author: wcq
# @Date:   2018-05-14 11:23:16
# @Last Modified by:   wcq
# @Last Modified time: 2018-05-14 11:23:44

import sublime, sublime_plugin, os

class ExpandTabsOnSave(sublime_plugin.EventListener):
  def on_pre_save(self, view):
    if view.settings().get('expand_tabs_on_save') == 1:
      view.window().run_command('expand_tabs')