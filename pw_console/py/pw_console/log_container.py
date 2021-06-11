# Copyright 2021 The Pigweed Authors
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.
"""LogLine and LogContainer."""

import logging
import re
import sys
import time

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional

from prompt_toolkit.data_structures import Point
from prompt_toolkit.formatted_text import (
    ANSI,
    to_formatted_text,
    fragment_list_width,
)

from pw_console.utils import (
    get_line_height,
    human_readable_size,
)

_LOG = logging.getLogger(__package__)

_ANSI_SEQUENCE_REGEX = re.compile(r'\x1b[^m]*m')


@dataclass
class LogLine:
    """Class to hold a single log event."""
    record: logging.LogRecord
    formatted_log: str

    def time(self):
        """Return a datetime object for the log record."""
        return datetime.fromtimestamp(self.record.created)

    def get_fragments(self) -> List:
        """Return this log line as a list of FormattedText tuples."""
        # Manually make a FormattedText tuple, wrap in a list
        # return [('class:bottom_toolbar_colored_text', self.record.msg)]
        # Use ANSI, returns a list of FormattedText tuples.

        # fragments = [('[SetCursorPosition]', '')]
        # fragments += ANSI(self.formatted_log).__pt_formatted_text__()
        # return fragments

        # Add a trailing linebreak
        return ANSI(self.formatted_log + '\n').__pt_formatted_text__()


def create_empty_log_message():
    """Create an empty LogLine instance."""
    return LogLine(record=logging.makeLogRecord({}), formatted_log='')


class LogContainer(logging.Handler):
    """Class to hold many log events."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self):
        self.logs: deque = deque()
        self.byte_size: int = 0
        self.history_size: int = 1000000
        self.channel_counts: Dict = {}
        self.channel_formatted_prefix_widths = {}
        self.longest_channel_prefix_width = 0
        self._last_start_index = 0
        self._last_end_index = 0
        self._current_start_index = 0
        self._current_end_index = 0
        self.line_index = 0
        self._window_height = 20
        self._window_width = 80
        self._last_line_wrap_count = 0
        self._last_displayed_lines = []
        self.follow = True
        self.log_pane = None
        self.pt_application = None
        self._ui_update_frequency = 0.3
        self._last_ui_update_time = time.time()
        self.clear_logs()
        self.has_new_logs = True
        self.line_fragment_cache = None

        super().__init__()

    def get_current_line(self):
        """Return the currently selected log event index."""
        return self.line_index

    def clear_logs(self):
        """Erase all stored pane lines."""
        self.logs = deque()
        self.byte_size = 0
        self.channel_counts = {}
        self.channel_formatted_prefix_widths = {}
        self.line_index = 0

    def wrap_lines_enabled(self):
        """Get the parent log pane wrap lines setting."""
        if not self.log_pane:
            return False
        return self.log_pane.wrap_lines

    def toggle_follow(self):
        """Toggle auto line following."""
        self.follow = not self.follow
        if self.follow:
            self.scroll_to_bottom()

    def get_total_count(self):
        """Total size of the logs container."""
        return len(self.logs)

    def get_last_log_line_index(self):
        """Last valid index of the logs."""
        # Subtract 1 since self.logs is zero indexed.
        return len(self.logs) - 1

    def get_channel_counts(self):
        """Return the seen channel log counts for the conatiner."""
        return ', '.join([
            f'{name}: {count}' for name, count in self.channel_counts.items()
        ])

    def get_human_byte_size(self):
        """Estimate the size of logs in memory."""
        return human_readable_size(self.byte_size)

    def _append_log(self, record):
        """Add a new log event."""
        formatted_log = self.format(record)
        self.logs.append(LogLine(record=record, formatted_log=formatted_log))
        # Increment this logger count
        self.channel_counts[record.name] = self.channel_counts.get(
            record.name, 0) + 1

        # Save a formatted prefix width if this is a new logger channel name.
        if record.name not in self.channel_formatted_prefix_widths.keys():
            # Delete ANSI escape sequences.
            ansi_stripped_log = _ANSI_SEQUENCE_REGEX.sub('', formatted_log)
            # Save the width of the formatted portion of the log message.
            self.channel_formatted_prefix_widths[
                record.name] = len(ansi_stripped_log) - len(record.msg)
            # Set the max width of all known formats so far.
            self.longest_channel_prefix_width = max(
                self.channel_formatted_prefix_widths.values())

        self.byte_size += sys.getsizeof(self.logs[-1])
        if self.get_total_count() > self.history_size:
            self.byte_size -= sys.getsizeof(self.logs.popleft())

        self.has_new_logs = True
        if self.follow:
            self.scroll_to_bottom()

    def _update_prompt_toolkit_ui(self):
        """Update Prompt Toolkit UI if a certain amount of time has passed."""
        emit_time = time.time()
        # Has 500ms passed since last UI redraw?
        if emit_time > self._last_ui_update_time + self._ui_update_frequency:
            # Update last log time
            self._last_ui_update_time = emit_time

            # Trigger Prompt Toolkit UI redraw.
            # TODO(tonymd): Clean up this API
            console_app = self.log_pane.application
            if hasattr(console_app, 'application'):
                # Thread safe way of sending a repaint trigger to the input
                # event loop.
                console_app.application.invalidate()

    def log_content_changed(self):
        return self.has_new_logs

    def get_cursor_position(self) -> Optional[Point]:
        """Return the position of the cursor."""
        fragment = "[SetCursorPosition]"
        if not self.line_fragment_cache:
            return Point(0, 0)
        for row, line in enumerate(self.line_fragment_cache):
            column = 0
            for style_str, text, *_ in line:
                if fragment in style_str:
                    return Point(x=column, y=row)
                column += len(text)
        return Point(0, 0)

    def emit(self, record):
        """Process a new log record.

        This defines the logging.Handler emit() fuction which is called by
        logging.Handler.handle() We don't implement handle() as it is done in
        the parent class with thread safety and filters applied.
        """
        self._append_log(record)
        self._update_prompt_toolkit_ui()

    def scroll_to_top(self):
        """Move selected index to the beginning."""
        # Stop following so cursor doesn't jump back down to the bottom.
        self.follow = False
        self.line_index = 0

    def scroll_to_bottom(self):
        """Move selected index to the end."""
        # Don't change following state like scroll_to_top.
        self.line_index = max(0, self.get_last_log_line_index())

    def scroll(self, lines):
        """Scroll up or down by plus or minus lines.

        This method is only called by user keybindings.
        """
        # If the user starts scrolling, stop auto following.
        self.follow = False

        # If scrolling to an index below zero, set to zero.
        new_line_index = max(0, self.line_index + lines)
        # If past the end, set to the last index of self.logs.
        if new_line_index >= self.get_total_count():
            new_line_index = self.get_last_log_line_index()
        # Set the new selected line index.
        self.line_index = new_line_index

    def scroll_to_position(self, mouse_position: Point):
        """Set the selected log line to the mouse_position."""
        # If auto following don't move the cursor arbitrarily. That would stop
        # following and position the cursor incorrectly.
        if self.follow:
            return

        cursor_position = self.get_cursor_position()
        if cursor_position:
            scroll_amount = cursor_position.y - mouse_position.y
            self.scroll(-1 * scroll_amount)

    def scroll_up_one_page(self):
        """Move the selected log index up by one window height."""
        lines = 1
        if self._window_height > 0:
            lines = self._window_height
        self.scroll(-1 * lines)

    def scroll_down_one_page(self):
        """Move the selected log index down by one window height."""
        lines = 1
        if self._window_height > 0:
            lines = self._window_height
        self.scroll(lines)

    def scroll_down(self, lines=1):
        """Move the selected log index down by one or more lines."""
        self.scroll(lines)

    def scroll_up(self, lines=1):
        """Move the selected log index up by one or more lines."""
        self.scroll(-1 * lines)

    def get_log_window_indices(self,
                               available_width=None,
                               available_height=None):
        """Get start and end index."""
        self._last_start_index = self._current_start_index
        self._last_end_index = self._current_end_index

        starting_index = 0
        ending_index = self.line_index

        self._window_width = self.log_pane.current_log_pane_width
        self._window_height = self.log_pane.current_log_pane_height
        if available_width:
            self._window_width = available_width
        if available_height:
            self._window_height = available_height

        # If render info is available we use the last window height.
        if self._window_height > 0:
            # Window lines are zero indexed so subtract 1 from the height.
            max_window_row_index = self._window_height - 1

            starting_index = max(0, self.line_index - max_window_row_index)
            # Use the current_window_height if line_index is less
            ending_index = max(self.line_index, max_window_row_index)

        if ending_index > self.get_last_log_line_index():
            ending_index = self.get_last_log_line_index()

        # Save start and end index.
        self._current_start_index = starting_index
        self._current_end_index = ending_index
        self.has_new_logs = False

        return starting_index, ending_index

    def draw(self) -> List:
        """Return log lines as a list of FormattedText tuples."""
        # If we have no logs add one with at least a single space character for
        # the cursor to land on. Otherwise the cursor will be left on the line
        # above the log pane container.
        if self.get_total_count() == 0:
            # No style specified.
            return [('', ' \n')]

        starting_index, ending_index = self.get_log_window_indices()

        window_width = self._window_width
        total_used_lines = 0
        self.line_fragment_cache = deque()
        # Since range() is not inclusive use ending_index + 1.
        # for i in range(starting_index, ending_index + 1):
        # From the ending_index to the starting index in reverse:
        for i in range(ending_index, starting_index - 1, -1):
            # If we are past the last valid index.
            if i > self.get_last_log_line_index():
                break

            line_fragments = self.logs[i].get_fragments()

            # Get the width of this line.
            fragment_width = fragment_list_width(line_fragments)
            # Get the line height respecting line wrapping.
            line_height = 1
            if self.wrap_lines_enabled() and (fragment_width > window_width):
                line_height = get_line_height(
                    fragment_width, window_width,
                    self.longest_channel_prefix_width)

            # Keep track of how many lines is used
            used_lines = 0
            used_lines += line_height

            # Count the number of line breaks included in the log line.
            line_breaks = self.logs[i].record.msg.count('\n')
            used_lines += line_breaks

            # If this is the selected line apply a style class for highlighting.
            if i == self.line_index:
                # Set the cursor to this line
                line_fragments = [('[SetCursorPosition]', '')] + line_fragments
                # Compute the number of trailing empty characters

                # Calculate the number of spaces to add at the end.
                empty_characters = window_width - fragment_width

                # If wrapping is enabled the width of the line prefix needs to
                # be accounted for.
                if self.wrap_lines_enabled() and (fragment_width >
                                                  window_width):
                    total_width = line_height * window_width
                    content_width = (self.longest_channel_prefix_width *
                                     (line_height - 1) + fragment_width)
                    empty_characters = total_width - content_width

                if empty_characters > 0:
                    line_fragments[-1] = ('', ' ' * empty_characters + '\n')

                line_fragments = to_formatted_text(
                    line_fragments, style='class:selected-log-line')

            self.line_fragment_cache.appendleft(line_fragments)
            total_used_lines += used_lines
            # If we have used more lines than available, stop adding new ones.
            if total_used_lines > self._window_height:
                break

        fragments = []
        for line_fragments in self.line_fragment_cache:
            # Append all FormattedText tuples for this line.
            for fragment in line_fragments:
                fragments.append(fragment)

        # Strip off any trailing line breaks
        last_fragment = fragments[-1]
        fragments[-1] = (last_fragment[0], last_fragment[1].rstrip('\n'))

        return fragments

    def set_log_pane(self, log_pane):
        """Set the parent LogPane instance."""
        self.log_pane = log_pane
