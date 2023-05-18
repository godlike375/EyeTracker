import eye_tracker.view.view_output
import eye_tracker.common.program
from unittest.mock import Mock

eye_tracker.view.view_output.show_message = Mock()
eye_tracker.view.view_output.show_warning = Mock()
eye_tracker.view.view_output.show_error = Mock()
eye_tracker.view.view_output.ask_confirmation = Mock(return_value=True)
eye_tracker.common.program.exit_program = Mock(return_value=None)

import sys
# https://stackoverflow.com/questions/33225086/how-often-does-python-switch-threads
sys.setswitchinterval(0.0005)