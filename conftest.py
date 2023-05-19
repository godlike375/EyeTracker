import sys
from unittest.mock import Mock

import eye_tracker.view.view_output
import eye_tracker.common.program
from eye_tracker.common.settings import settings, private_settings


eye_tracker.view.view_output.show_message = Mock()
eye_tracker.view.view_output.show_warning = Mock()
eye_tracker.view.view_output.show_error = Mock()
eye_tracker.view.view_output.ask_confirmation = Mock(return_value=True)
eye_tracker.common.program.exit_program = Mock(return_value=None)


settings.save = Mock(return_value=None)
settings.load = Mock(return_value=None)
private_settings.save = Mock(return_value=None)
private_settings.load = Mock(return_value=None)

# https://stackoverflow.com/questions/33225086/how-often-does-python-switch-threads
sys.setswitchinterval(0.0005)

from tests.fixtures import *