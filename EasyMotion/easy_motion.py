import sublime
import sublime_plugin
import re
from itertools import zip_longest
from pprint import pprint

REGEX_ESCAPE_CHARS = '\\+*()[]{}^$?|:].,'

# not a fan of using globals like this, but not sure if there's a better way with the plugin
# API that ST2 provides.  Tried attaching as fields to active_view, but didn't persist, I'm guessing
# it's just a representation of something that gets regenerated on demand so dynamic fields are transient
JUMP_GROUP_GENERATOR = None
CURRENT_JUMP_GROUP = None
SELECT_TEXT = False
COMMAND_MODE_WAS = False
JUMP_TARGET_SCOPE = 'string'


class JumpGroupGenerator:
    '''
       given a list of region jump targets matching the given character, can emit a series of
       JumpGroup dictionaries going forwards with next and backwards with previous
    '''
    def __init__(self, view, character, placeholder_chars, case_sensitive):
        self.view = view
        self.case_sensitive = case_sensitive
        self.placeholder_chars = placeholder_chars
        self.all_jump_targets = self.find_all_jump_targets_in_visible_region(character)
        self.interleaved_jump_targets = self.interleave_jump_targets_from_cursor()
        self.jump_target_index = 0
        self.jump_target_groups = self.create_jump_target_groups()
        self.jump_target_group_index = -1

    def determine_re_flags(self, character):
        if character == 'enter':
            return '(?m)'
        elif self.case_sensitive:
            return '(?i)'
        else:
            return ''

    def interleave_jump_targets_from_cursor(self):
        sel = self.view.sel()[0]  # multi select not supported, doesn't really make sense
        sel_begin = sel.begin()
        sel_end = sel.end()
        before = []
        after = []

        # split them into two lists radiating out from the cursor position
        for target in self.all_jump_targets:
            if target.begin() < sel_begin:
                # add to beginning of list so closest targets to cursor are first
                before.insert(0, target)
            elif target.begin() > sel_end:
                after.append(target)

        # now interleave the two lists together into one list
        return [target for targets in zip_longest(before, after) for target in targets if target is not None]

    def create_jump_target_groups(self):
        jump_target_groups = []

        while self.has_next_jump_target():
            jump_group = dict()

            for placeholder_char in self.placeholder_chars:
                if self.has_next_jump_target():
                    jump_group[placeholder_char] = self.interleaved_jump_targets[self.jump_target_index]
                    self.jump_target_index += 1
                else:
                    break

            jump_target_groups.append(jump_group)

        return jump_target_groups

    def has_next_jump_target(self):
        return self.jump_target_index < len(self.interleaved_jump_targets)

    def __len__(self):
        return len(self.jump_target_groups)

    def next(self):
        self.jump_target_group_index += 1

        if self.jump_target_group_index >= len(self.jump_target_groups) or self.jump_target_group_index < 0:
            self.jump_target_group_index = 0

        return self.jump_target_groups[self.jump_target_group_index]

    def previous(self):
        self.jump_target_group_index -= 1

        if self.jump_target_group_index < 0 or self.jump_target_group_index >= len(self.jump_target_groups):
            self.jump_target_group_index = len(self.jump_target_groups) - 1

        return self.jump_target_groups[self.jump_target_group_index]

    def find_all_jump_targets_in_visible_region(self, character):
        visible_region_begin = self.visible_region_begin()
        visible_text = self.visible_text()
        folded_regions = self.get_folded_regions(self.view)
        matching_regions = []
        #'(?i)' + character
        target_regexp = self.target_regexp(character)

        for char_at in (match.start() for match in re.finditer(target_regexp, visible_text)):
            char_point = char_at + visible_region_begin
            char_region = sublime.Region(char_point, char_point + 1)
            if not self.region_list_contains_region(folded_regions, char_region):
                matching_regions.append(char_region)

        return matching_regions

    def region_list_contains_region(self, region_list, region):
        for element_region in region_list:
            if element_region.contains(region):
                return True
        return False

    def visible_region_begin(self):
        return self.view.visible_region().begin()

    def visible_text(self):
        visible_region = self.view.visible_region()
        return self.view.substr(visible_region)

    def target_regexp(self, character):
        re_flags = self.determine_re_flags(character)
        if (REGEX_ESCAPE_CHARS.find(character) >= 0):
            return re_flags + '\\' + character
        elif character == "enter":
            return re_flags + "(?=^).|.(?=$)"
        else:
            return re_flags + character

    def get_folded_regions(self, view):
        '''
        No way in the API to get the folded regions without unfolding them first
        seems to be quick enough that you can't actually see them fold/unfold
        '''
        folded_regions = view.unfold(view.visible_region())
        view.fold(folded_regions)
        return folded_regions


class EasyMotionCommand(sublime_plugin.WindowCommand):
    winning_selection = None
    active_view = None

    def run(self, character=None, select_text=False):
        global JUMP_GROUP_GENERATOR, SELECT_TEXT, JUMP_TARGET_SCOPE
        sublime.status_message("EasyMotion: Jump to " + character)

        self.active_view = self.window.active_view()
        SELECT_TEXT = select_text

        settings = sublime.load_settings("EasyMotion.sublime-settings")
        placeholder_chars = settings.get('placeholder_chars', 'abcdefghijklmnopqrstuvwxyz01234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ')
        JUMP_TARGET_SCOPE = settings.get('jump_target_scope', 'string')
        case_sensitive = settings.get('case_sensitive', True)

        JUMP_GROUP_GENERATOR = JumpGroupGenerator(self.active_view, character, placeholder_chars, case_sensitive)

        if len(JUMP_GROUP_GENERATOR) > 0:
            self.start_easy_motion()
        else:
            sublime.status_message("EasyMotion: unable to find any instances of " + character + " in visible region")

    def start_easy_motion(self):
        self.activate_mode()
        self.window.run_command("show_jump_group")

    def activate_mode(self):
        global COMMAND_MODE_WAS
        self.active_view.settings().set('easy_motion_mode', True)
        # yes, this feels a little dirty to mess with the Vintage plugin, but there
        # doesn't appear to be any other way to tell it to not intercept keys, so turn it
        # off (if it's on) while we're running EasyMotion
        COMMAND_MODE_WAS = self.active_view.settings().get('command_mode')
        if (COMMAND_MODE_WAS):
            self.active_view.settings().set('command_mode', False)


class ShowJumpGroupCommand(sublime_plugin.WindowCommand):
    def run(self, next=True):
        self.active_view = self.window.active_view()
        self.show_jump_group(next)

    def show_jump_group(self, next=True):
        global JUMP_GROUP_GENERATOR, CURRENT_JUMP_GROUP

        if next:
            CURRENT_JUMP_GROUP = JUMP_GROUP_GENERATOR.next()
        else:
            CURRENT_JUMP_GROUP = JUMP_GROUP_GENERATOR.previous()

        self.activate_current_jump_group()

    def activate_current_jump_group(self):
        if self.active_view.get_regions("jump_match_regions") != []:
            self.active_view.erase_regions("jump_match_regions")
            self.window.run_command("undo")
            # self.view.window().run_command("undo_last_jump_targets")

        self.active_view.run_command('set_text_em')

        self.active_view.add_regions("jump_match_regions", list(CURRENT_JUMP_GROUP.values()), JUMP_TARGET_SCOPE, "dot")


class SetTextEmCommand(sublime_plugin.TextCommand):
    active_view = None
    edit = None

    def run(self, edit):
        self.edit = edit
        global CURRENT_JUMP_GROUP, JUMP_TARGET_SCOPE

        for placeholder_char in CURRENT_JUMP_GROUP.keys():
            self.view.replace(self.edit, CURRENT_JUMP_GROUP[placeholder_char], placeholder_char)


class UndoLastJumpTargets(sublime_plugin.WindowCommand):
    '''
       Sublime doesn't like it sometimes when we undo while inside of a text command, have that text command call out
       to this window command and run the undo
    '''
    def run(self):
        pprint("calling undo from UndoLastJumpTargets")
        self.window.run_command("undo")


class JumpTo(sublime_plugin.WindowCommand):
    def run(self, character=None):
        global COMMAND_MODE_WAS

        self.active_view = self.window.active_view()
        self.winning_selection = self.winning_selection_from(character)
        self.finish_easy_motion()
        self.active_view.settings().set('easy_motion_mode', False)
        if (COMMAND_MODE_WAS):
            self.active_view.settings().set('command_mode', True)

    def winning_selection_from(self, selection):
        global CURRENT_JUMP_GROUP, SELECT_TEXT
        winning_region = None
        if selection in CURRENT_JUMP_GROUP:
            winning_region = CURRENT_JUMP_GROUP[selection]

        if winning_region is not None:
            if SELECT_TEXT:
                for current_selection in self.active_view.sel():
                    if winning_region.begin() < current_selection.begin():
                        return sublime.Region(current_selection.end(), winning_region.begin())
                    else:
                        return sublime.Region(current_selection.begin(), winning_region.end())
            else:
                return sublime.Region(winning_region.begin(), winning_region.begin())

    def finish_easy_motion(self):
        '''
        We need to clean up after ourselves by restoring the view to it's original state, if the user did
        press a jump target that we've got saved, jump to it as the last action
        '''
        self.deactivate_current_jump_group()
        self.jump_to_winning_selection()

    def deactivate_current_jump_group(self):
        self.window.run_command("undo")
        self.active_view.erase_regions("jump_match_regions")

    def jump_to_winning_selection(self):
        if self.winning_selection is not None:
            self.active_view.run_command("jump_to_winning_selection", {"begin": self.winning_selection.begin(), "end": self.winning_selection.end()})


class DeactivateJumpTargets(sublime_plugin.WindowCommand):
    def run(self):
        active_view = self.window.active_view()
        active_view.erase_regions("jump_match_regions")
        self.window.run_command("undo")

        active_view.settings().set('easy_motion_mode', False)
        if (COMMAND_MODE_WAS):
            active_view.settings().set('command_mode', True)


class JumpToWinningSelection(sublime_plugin.TextCommand):
    def run(self, edit, begin, end):
        winning_region = sublime.Region(int(begin), int(end))
        sel = self.view.sel()
        sel.clear()
        sel.add(winning_region)
        self.view.show(winning_region)
