import view.view_output
from unittest.mock import Mock

view.view_output.show_message = Mock()
view.view_output.show_warning = Mock()
view.view_output.show_error = Mock()
view.view_output.ask_confirmation = Mock(return_value=True)

import sys
# https://stackoverflow.com/questions/33225086/how-often-does-python-switch-threads
sys.setswitchinterval(0.0005)